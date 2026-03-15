"""Conversation loop mixin for ChatUI.

Handles the agentic tool-calling loop and streaming response.

  • L1 Core Memory is updated from the user message at the start of every turn
    (goal detection + correction detection).
  • L1 active entities and error history are updated after each tool call.
  • Every tool exchange is scored for importance against the raw (uncompressed)
    tool output and written to the L2 Episodic Store if it meets the threshold,
    giving the agent durable recall across context window boundaries.
  • Stall-detection interrupt messages are persisted to history and the DB so
    the model's subsequent response has a valid preceding user message.
"""
from __future__ import annotations

from nbchat.core.utils import lazy_import

import json
import logging

_log = logging.getLogger("nbchat.compaction")


def _is_error_content(content: str) -> bool:
    """Return True if *content* contains common error signal keywords."""
    content_lower = (content or "").lower()
    return any(p in content_lower for p in (
        "error", "exception", "failed", "cannot", "traceback",
        "fatal", "unexpected", "invalid", "permission denied", "not found",
    ))


class ConversationMixin:
    """Mixed into ChatUI — expects self.history, self.task_log,
    self.system_prompt, self.model_name, self.session_id,
    self._stop_streaming, self._append, self._hard_trim,
    self._log_action, self._window, and all
    renderer/executor/chat_builder imports to be available."""

    def _process_conversation_turn(self) -> None:
        from nbchat.ui import chat_renderer as renderer
        from nbchat.ui import tool_executor as executor
        from nbchat.ui import chat_builder
        from nbchat.core import compressor as comp
        from nbchat.core import client as _client_mod
        db = lazy_import("nbchat.core.db")

        real_client = _client_mod.get_client()
        try:
            self._run_conversation_loop(
                real_client, db, renderer, executor, chat_builder, comp
            )
        except Exception as exc:
            _log.debug(f"_process_conversation_turn crashed: {type(exc).__name__}: {exc}", exc_info=True)
            self._append(renderer.render_assistant(
                f"Conversation loop stopped unexpectedly: {type(exc).__name__}: {exc}"
            ))

    def _run_conversation_loop(self, real_client, db, renderer, executor, chat_builder, comp) -> None:
        # ── L1: update goal from latest user message ──────────────────────
        # Done before building messages so the very first API call already
        # has fresh core memory injected via _window().
        try:
            last_user = next(
                (row[1] for row in reversed(self.history) if row[0] == "user"),
                None,
            )
            if last_user:
                self._update_l1_goal_from_user(last_user)
        except Exception as exc:
            _log.debug(f"L1 goal update failed: {exc}")

        # _window() returns (window_rows, effective_cut); only rows needed here.
        window, _cut = self._window()
        messages = chat_builder.build_messages(
            window, self.system_prompt, self.task_log
        )
        for msg in messages:
            msg.pop("reasoning_content", None)

        config = lazy_import("nbchat.core.config")
        STALL_TURNS = config.STALL_TURNS
        _recent_call_sets: list = []

        for turn in range(self.MAX_TOOL_TURNS + 1):
            if self._stop_streaming:
                break

            reasoning, content, tool_calls, finish_reason = self._stream_response(
                real_client, messages
            )

            if reasoning:
                # analysis rows are display-only; error_flag not meaningful here
                self.history.append(("analysis", reasoning, "", "", "", 0))
                db.log_message(self.session_id, "analysis", reasoning)

            if not tool_calls or finish_reason != "tool_calls":
                if content:
                    self.history.append(("assistant", content, "", "", "", 0))
                    db.log_message(self.session_id, "assistant", content)
                break

            if turn == self.MAX_TOOL_TURNS:
                warning = f"Maximum tool turns ({self.MAX_TOOL_TURNS}) reached."
                self._append(renderer.render_assistant(warning))
                self.history.append(("assistant", warning, "", "", "", 0))
                db.log_message(self.session_id, "assistant", warning)
                break

            # ── Stall detection ───────────────────────────────────────────
            turn_calls = frozenset(
                (tc["function"]["name"], tc["function"]["arguments"])
                for tc in tool_calls
            )
            _recent_call_sets.append(turn_calls)
            if len(_recent_call_sets) > STALL_TURNS:
                _recent_call_sets.pop(0)
            if len(_recent_call_sets) == STALL_TURNS and len(set(_recent_call_sets)) == 1:
                stall_msg = (
                    "You appear to be stuck in a loop — you have made the "
                    f"same tool calls {STALL_TURNS} turns in a row without "
                    "progressing. Stop repeating these calls. Review the "
                    "task log in the system prompt, identify what has already "
                    "been done, and take a concrete next step that you have "
                    "not yet attempted."
                )
                _log.debug("stall detected — injecting interrupt")
                # Persist so the DB doesn't contain an orphaned assistant
                # response with no preceding user message.
                self.history.append(("user", stall_msg, "", "", "", 0))
                db.log_message(self.session_id, "user", stall_msg)
                messages.append({"role": "user", "content": stall_msg})
                _recent_call_sets.clear()

            # ── Build assistant message for model history ─────────────────
            # content must be None (not "") when tool_calls are present.
            msg_for_model = {
                "role": "assistant",
                "content": content or None,
                "tool_calls": tool_calls,
            }
            messages.append(msg_for_model)

            storable_msg = {
                "role": "assistant",
                "content": content or None,
                "tool_calls": tool_calls,
            }
            full_msg_json = json.dumps(storable_msg)
            # assistant_full rows don't have a meaningful error_flag
            self.history.append(("assistant_full", "", "full", "full", full_msg_json, 0))
            db.log_row(self.session_id, "assistant_full", "", "full", "full", full_msg_json)

            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                tool_args = tc["function"]["arguments"]

                raw_result = executor.run_tool(tool_name, tool_args)
                self._append(renderer.render_tool(raw_result, tool_name, tool_args))

                compressed = comp.compress_tool_output(
                    tool_name, tool_args, raw_result,
                    model=self.model_name,
                    client=real_client,
                )

                model_result = (
                    f"[{tool_name}: no relevant output]"
                    if compressed.strip() == "NO_RELEVANT_OUTPUT"
                    else compressed
                )

                self._log_action(tool_name, tool_args, model_result)

                # Compute error_flag from raw output before compression may
                # have stripped error signals.
                error_flag = 1 if _is_error_content(raw_result) else 0
                self.history.append(("tool", raw_result, tc["id"], tool_name, tool_args, error_flag))
                db.log_tool_msg(self.session_id, tc["id"], tool_name, tool_args, raw_result)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": model_result,
                })

                # ── L1 + L2 update after each tool call ───────────────────
                # Score against raw_result so error signals are not missed if
                # the compressor stripped them from model_result.
                try:
                    exchange_msgs = [
                        msg_for_model,
                        {"role": "tool", "content": model_result},
                    ]
                    importance = self._importance_score(exchange_msgs, raw_result=raw_result)
                    self._write_exchange_to_episodic(
                        turn, tool_name, tool_args, model_result, importance
                    )
                    self._update_l1_from_exchange(tool_name, tool_args, model_result)
                except Exception as exc:
                    _log.debug(f"L1/L2 post-tool update failed: {exc}")

    def _stream_response(self, real_client, messages):
        from nbchat.ui import chat_renderer as renderer
        tools = lazy_import("nbchat.tools")

        reasoning_widget = None
        assistant_widget = None
        reasoning_accum = ""
        content_accum = ""
        tool_buffer: dict = {}
        finish_reason = None

        self._hard_trim(messages)
        _sanitize_messages(messages)

        try:
            stream = real_client.chat.completions.create(
                model=self.model_name, messages=messages,
                stream=True, tools=tools, max_tokens=4096,
            )
            for chunk in stream:
                if self._stop_streaming:
                    stream.close()
                    break
                choice = chunk.choices[0]
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
                delta = choice.delta

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        entry = tool_buffer.setdefault(tc.index, {
                            "id": tc.id, "type": "function",
                            "function": {"name": tc.function.name, "arguments": ""},
                        })
                        if tc.function.arguments:
                            entry["function"]["arguments"] += tc.function.arguments

                if getattr(delta, "reasoning_content", None):
                    if reasoning_widget is None:
                        reasoning_widget = renderer.render_placeholder("reasoning")
                        self._append(reasoning_widget)
                    reasoning_accum += delta.reasoning_content
                    reasoning_widget.value = renderer.render_reasoning(reasoning_accum).value

                if delta.content:
                    if assistant_widget is None:
                        assistant_widget = renderer.render_placeholder("assistant")
                        children = list(self.chat_history.children)
                        if reasoning_widget in children:
                            children.insert(children.index(reasoning_widget) + 1, assistant_widget)
                        else:
                            children.append(assistant_widget)
                        self.chat_history.children = children
                    content_accum += delta.content
                    assistant_widget.value = renderer.render_assistant(content_accum).value
        except Exception as exc:
            if "now finding less tool calls" in str(exc):
                _log.warning(
                    f"SDK diff error fired.\n"
                    f"  tool_buffer state: {json.dumps(tool_buffer, indent=2)}\n"
                    f"  finish_reason so far: {finish_reason}\n"
                    f"  content_accum length: {len(content_accum)}\n"
                    f"  reasoning_accum length: {len(reasoning_accum)}"
                )
                raise
            else:
                _log.debug(f"_stream_response failed: {type(exc).__name__}: {exc}", exc_info=True)
                raise

        tool_calls = [tool_buffer[i] for i in sorted(tool_buffer)] if tool_buffer else None

        if tool_calls:
            if assistant_widget is not None:
                assistant_widget.value = renderer.render_assistant_with_tools(
                    content_accum, tool_calls
                ).value
            else:
                assistant_widget = renderer.render_assistant_with_tools("", tool_calls)
                children = list(self.chat_history.children)
                if reasoning_widget in children:
                    children.insert(children.index(reasoning_widget) + 1, assistant_widget)
                else:
                    children.append(assistant_widget)
                self.chat_history.children = children
        elif assistant_widget is None and content_accum:
            assistant_widget = renderer.render_assistant(content_accum)
            self._append(assistant_widget)

        return reasoning_accum, content_accum, tool_calls, finish_reason


def _sanitize_messages(messages: list) -> None:
    """Normalize assistant messages for strict OpenAI-compat models.

    The OpenAI spec requires content=None (not "") when tool_calls are
    present on an assistant message.  Smaller models fail to emit
    structured tool calls on subsequent turns when they see content=""
    alongside tool_calls in their history — they express the next call
    as reasoning text instead.  This sanitizer fixes both freshly built
    messages and old DB rows reconstructed via assistant_full.
    """
    for m in messages:
        if m.get("role") == "assistant" and m.get("tool_calls") and not m.get("content"):
            m["content"] = None
"""Conversation loop mixin for ChatUI.

Handles the agentic tool-calling loop and streaming response.
"""
from __future__ import annotations

from nbchat.core.utils import lazy_import

import json
import logging

_log = logging.getLogger("nbchat.compaction")


class ConversationMixin:
    """Mixed into ChatUI — expects self.history, self.task_log,
    self.system_prompt, self.model_name, self.session_id,
    self._stop_streaming, self._append, self._hard_trim,
    self._log_action, self._window, self._seen_calls, and all
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
        messages = chat_builder.build_messages(
            self._window(), self.system_prompt, self.task_log
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
                self.history.append(("analysis", reasoning, "", "", ""))
                db.log_message(self.session_id, "analysis", reasoning)

            if not tool_calls or finish_reason != "tool_calls":
                if content:
                    self.history.append(("assistant", content, "", "", ""))
                    db.log_message(self.session_id, "assistant", content)
                break

            if turn == self.MAX_TOOL_TURNS:
                warning = f"⚠️ Maximum tool turns ({self.MAX_TOOL_TURNS}) reached."
                self._append(renderer.render_assistant(warning))
                self.history.append(("assistant", warning, "", "", ""))
                db.log_message(self.session_id, "assistant", warning)
                break

            # --- Stall detection ---
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
                messages.append({"role": "user", "content": stall_msg})
                _recent_call_sets.clear()

            # --- Build assistant message for model history ---
            # content must be None (not "") when tool_calls are present.
            # Strict OpenAI-compat models (especially smaller ones) mis-read
            # the conversation state when they see content="" + tool_calls and
            # emit subsequent tool calls as reasoning text instead of structured
            # output.
            msg_for_model = {
                "role": "assistant",
                "content": content or None,
                "tool_calls": tool_calls,
            }
            messages.append(msg_for_model)

            storable_msg = {"role": "assistant", "content": content or None, "tool_calls": tool_calls}
            full_msg_json = json.dumps(storable_msg)
            self.history.append(("assistant_full", "", "full", "full", full_msg_json))
            db.log_row(self.session_id, "assistant_full", "", "full", "full", full_msg_json)

            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                tool_args = tc["function"]["arguments"]
                call_key = (tool_name, tool_args)

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

                self._seen_calls[call_key] = model_result
                if len(self._seen_calls) > 200:
                    del self._seen_calls[next(iter(self._seen_calls))]

                self._log_action(tool_name, tool_args, model_result)
                self.history.append(("tool", raw_result, tc["id"], tool_name, tool_args))
                db.log_tool_msg(self.session_id, tc["id"], tool_name, tool_args, raw_result)
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": model_result})

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
            # The OpenAI SDK streaming validator raises APIError("Invalid diff:
            # now finding less tool calls!") when llama.cpp emits tool call
            # delta chunks in a format that appears inconsistent — this happens
            # specifically when thinking=False is active. By the time this fires
            # the tool_buffer is already fully populated, so treat it as a
            # normal end-of-stream rather than a hard failure.
            if "now finding less tool calls" in str(exc):
                _log.debug("suppressed SDK streaming diff error — tool_buffer complete")
            else:
                _log.debug(f"_stream_response failed: {type(exc).__name__}: {exc}", exc_info=True)
                raise

        tool_calls = [tool_buffer[i] for i in sorted(tool_buffer)] if tool_buffer else None

        if tool_calls:
            if assistant_widget is not None:
                assistant_widget.value = renderer.render_assistant_with_tools(content_accum, tool_calls).value
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
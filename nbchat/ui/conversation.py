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
  • compress_tool_output receives the session_id so the session-local lossless
    learning and repeat-read detection are active.

Output decoupling
-----------------
ConversationMixin does not reference ipywidgets or chat_renderer directly.
All UI side-effects are routed through five output hooks that default to
no-ops, enabling headless use by WhatsApp and any future channels:

    _on_stream_token(content)           called each chunk during LLM streaming
    _on_stream_reasoning(reasoning)     called each chunk of reasoning/thinking
    _on_tool_display(raw, name, args)   called after each tool execution
    _on_agent_message(text)             called for warnings / error notices
    _on_stream_complete(content, tcs)   called once after streaming finishes

ChatUI overrides all five with ipywidgets implementations.
WhatsAppAgent (and any future channel) inherits the no-op defaults and
captures the final response text via _on_stream_token / _on_stream_complete.
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
    """Mixed into ChatUI and headless channel agents.

    Required attributes on the host class:
        self.history, self.task_log, self.system_prompt, self.model_name,
        self.session_id, self._stop_streaming, self._tool_running,
        self._hard_trim, self._log_action, self._window, self.MAX_TOOL_TURNS
    """

    # ── Output hooks — override in subclasses for UI or channel output ────

    def _on_stream_token(self, content: str) -> None:
        """Called with accumulated assistant text after each streamed chunk.

        UI: update live assistant widget value.
        Headless: no-op — final text captured from _stream_response return value.
        """

    def _on_stream_reasoning(self, reasoning: str) -> None:
        """Called with accumulated reasoning/thinking text after each chunk.

        UI: update live reasoning widget value.
        Headless: no-op.
        """

    def _on_tool_display(self, raw_result: str, tool_name: str, tool_args: str) -> None:
        """Called after each tool execution with the raw (uncompressed) result.

        UI: render and append a tool-result widget.
        Headless: no-op — tool results are persisted to history/DB as normal.
        """

    def _on_agent_message(self, text: str) -> None:
        """Called when the loop needs to surface a notice to the user.

        Used for: max-tool-turns warning, unhandled exception notice.
        UI: render and append an assistant widget.
        Headless: no-op (text is also logged at debug level).
        """

    def _on_stream_complete(self, content: str, tool_calls: list | None) -> None:
        """Called once after streaming finishes with final accumulated state.

        UI: finalize the assistant widget (show tool-call display if present;
            append plain assistant widget when content arrived with no widget).
        Headless: no-op — content already captured via _on_stream_token.
        """

    # ── Passthrough hooks already overridden by ChatUI ────────────────────

    def _append(self, widget) -> None:
        """Append a widget to the chat panel.  No-op in headless mode."""

    def _refresh_monitoring_panel(self) -> None:
        """Refresh the monitoring sidebar widget.  No-op in headless mode."""

    # ── Conversation entry point ──────────────────────────────────────────

    def _process_conversation_turn(self) -> None:
        from nbchat.ui import tool_executor as executor
        from nbchat.ui import chat_builder
        from nbchat.core import compressor as comp
        from nbchat.core import client as _client_mod
        from nbchat.core import monitoring as mon
        db = lazy_import("nbchat.core.db")

        real_client = _client_mod.get_client()
        try:
            self._run_conversation_loop(
                real_client, db, executor, chat_builder, comp
            )
        except Exception as exc:
            msg = (
                f"Conversation loop stopped unexpectedly: "
                f"{type(exc).__name__}: {exc}"
            )
            _log.debug(msg, exc_info=True)
            mon.flush_session_monitor(self.session_id, db)
            self._on_agent_message(msg)

    def _run_conversation_loop(
        self, real_client, db, executor, chat_builder, comp
    ) -> None:
        from nbchat.core import monitoring as mon

        # ── L1: update goal from latest user message ──────────────────────
        try:
            last_user = next(
                (row[1] for row in reversed(self.history) if row[0] == "user"),
                None,
            )
            if last_user:
                self._update_l1_goal_from_user(last_user)
        except Exception as exc:
            _log.debug(f"L1 goal update failed: {exc}")

        window, _cut = self._window()
        messages = chat_builder.build_messages(
            window, self.system_prompt, self.task_log
        )
        for msg in messages:
            msg.pop("reasoning_content", None)

        monitor = mon.get_session_monitor(self.session_id)

        config = lazy_import("nbchat.core.config")
        STALL_TURNS = config.STALL_TURNS
        _recent_call_sets: list = []

        for turn in range(self.MAX_TOOL_TURNS + 1):
            if self._stop_streaming:
                mon.flush_session_monitor(self.session_id, db)
                break

            volatile_len = (
                len(messages[1]["content"])
                if len(messages) > 2 and messages[1].get("role") == "user"
                else 0
            )

            reasoning, content, tool_calls, finish_reason = self._stream_response(
                real_client, messages
            )

            try:
                monitor.record_llm_call(volatile_len)
            except Exception:
                pass

            if reasoning:
                self.history.append(("analysis", reasoning, "", "", "", 0))
                db.log_message(self.session_id, "analysis", reasoning)

            if not tool_calls or finish_reason != "tool_calls":
                if content:
                    self.history.append(("assistant", content, "", "", "", 0))
                    db.log_message(self.session_id, "assistant", content)
                mon.flush_session_monitor(self.session_id, db)
                self._refresh_monitoring_panel()
                break

            if turn == self.MAX_TOOL_TURNS:
                warning = f"Maximum tool turns ({self.MAX_TOOL_TURNS}) reached."
                self._on_agent_message(warning)
                self.history.append(("assistant", warning, "", "", "", 0))
                db.log_message(self.session_id, "assistant", warning)
                mon.flush_session_monitor(self.session_id, db)
                break

            # ── Stall detection ───────────────────────────────────────────
            turn_calls = frozenset(
                (tc["function"]["name"], tc["function"]["arguments"])
                for tc in tool_calls
            )
            _recent_call_sets.append(turn_calls)
            if len(_recent_call_sets) > STALL_TURNS:
                _recent_call_sets.pop(0)
            if (
                len(_recent_call_sets) == STALL_TURNS
                and len(set(_recent_call_sets)) == 1
            ):
                stall_msg = (
                    "You appear to be stuck in a loop — you have made the "
                    f"same tool calls {STALL_TURNS} turns in a row without "
                    "progressing. Stop repeating these calls. Review the "
                    "task log in the system prompt, identify what has already "
                    "been done, and take a concrete next step that you have "
                    "not yet attempted."
                )
                _log.debug("stall detected — injecting interrupt")
                self.history.append(("user", stall_msg, "", "", "", 0))
                db.log_message(self.session_id, "user", stall_msg)
                messages.append({"role": "user", "content": stall_msg})
                _recent_call_sets.clear()

            # ── Build assistant message for model history ─────────────────
            msg_for_model = {
                "role": "assistant",
                "content": content or None,
                "tool_calls": tool_calls,
            }
            messages.append(msg_for_model)

            full_msg_json = json.dumps({
                "role": "assistant",
                "content": content or None,
                "tool_calls": tool_calls,
            })
            self.history.append(
                ("assistant_full", "", "full", "full", full_msg_json, 0)
            )
            db.log_row(
                self.session_id, "assistant_full", "", "full", "full", full_msg_json
            )

            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                tool_args = tc["function"]["arguments"]

                self._tool_running = True
                try:
                    raw_result = executor.run_tool(tool_name, tool_args)
                finally:
                    self._tool_running = False

                self._on_tool_display(raw_result, tool_name, tool_args)

                compressed = comp.compress_tool_output(
                    tool_name,
                    tool_args,
                    raw_result,
                    model=self.model_name,
                    client=real_client,
                    session_id=self.session_id,
                )

                model_result = (
                    f"[{tool_name}: no relevant output]"
                    if compressed.strip() == "NO_RELEVANT_OUTPUT"
                    else compressed
                )

                self._log_action(tool_name, tool_args, model_result)

                error_flag = 1 if _is_error_content(raw_result) else 0
                self.history.append(
                    ("tool", raw_result, tc["id"], tool_name, tool_args, error_flag)
                )
                db.log_tool_msg(
                    self.session_id, tc["id"], tool_name, tool_args, raw_result
                )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": model_result,
                })

                # ── L1 + L2 update ────────────────────────────────────────
                try:
                    exchange_msgs = [
                        msg_for_model,
                        {"role": "tool", "content": model_result},
                    ]
                    importance = self._importance_score(
                        exchange_msgs, raw_result=raw_result
                    )
                    self._write_exchange_to_episodic(
                        turn, tool_name, tool_args, model_result, importance
                    )
                    self._update_l1_from_exchange(tool_name, tool_args, model_result)
                except Exception as exc:
                    _log.debug(f"L1/L2 post-tool update failed: {exc}")

                # ── Monitoring ────────────────────────────────────────────
                try:
                    comp_stats = comp.get_compression_stats().get(tool_name, {})
                    last_strategy = next(
                        iter(comp_stats.get("strategies", {})), ""
                    )
                    monitor.record_tool_call(
                        tool_name=tool_name,
                        was_compressed=len(compressed) < len(raw_result),
                        had_error=bool(error_flag),
                        strategy=last_strategy,
                        input_chars=len(raw_result),
                        output_chars=len(compressed),
                    )
                    if compressed.strip() == "NO_RELEVANT_OUTPUT":
                        monitor.record_no_output(tool_name)
                except Exception:
                    pass

                self._refresh_monitoring_panel()

    # ── Streaming ─────────────────────────────────────────────────────────

    def _stream_response(self, real_client, messages):
        """Run one LLM completion, fire output hooks during streaming.

        Does not reference ipywidgets or chat_renderer.

        Returns
        -------
        (reasoning_accum, content_accum, tool_calls, finish_reason)
        """
        tools = lazy_import("nbchat.tools")
        config = lazy_import("nbchat.core.config")

        reasoning_accum = ""
        content_accum = ""
        tool_buffer: dict = {}
        finish_reason = None

        self._hard_trim(messages)
        _sanitize_messages(messages)

        try:
            stream = real_client.chat.completions.create(
                model=self.model_name, messages=messages,
                stream=True, tools=tools, max_tokens=config.MAX_TOOL_OUTPUT_CHARS,
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
                    reasoning_accum += delta.reasoning_content
                    self._on_stream_reasoning(reasoning_accum)

                if delta.content:
                    content_accum += delta.content
                    self._on_stream_token(content_accum)

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
                _log.debug(
                    f"_stream_response failed: {type(exc).__name__}: {exc}",
                    exc_info=True,
                )
                raise

        tool_calls = (
            [tool_buffer[i] for i in sorted(tool_buffer)]
            if tool_buffer else None
        )

        # Notify subclass that streaming is complete with final state.
        # UI subclass uses this to finalize the assistant widget display.
        self._on_stream_complete(content_accum, tool_calls)

        return reasoning_accum, content_accum, tool_calls, finish_reason


def _sanitize_messages(messages: list) -> None:
    """Normalize assistant messages for strict OpenAI-compat models.

    The OpenAI spec requires content=None (not "") when tool_calls are
    present on an assistant message.  Smaller models fail to emit structured
    tool calls on subsequent turns when they see content="" alongside
    tool_calls in their history.  This sanitizer fixes both freshly built
    messages and old DB rows reconstructed via assistant_full.
    """
    for m in messages:
        if m.get("role") == "assistant" and m.get("tool_calls") and not m.get("content"):
            m["content"] = None
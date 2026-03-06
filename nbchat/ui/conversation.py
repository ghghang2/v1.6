"""Conversation loop mixin for ChatUI.

Handles the agentic tool-calling loop and streaming response.
"""
from __future__ import annotations

from nbchat.core.utils import lazy_import

import json
import logging
from typing import List

_log = logging.getLogger("nbchat.compaction")


class ConversationMixin:
    """Mixed into ChatUI — expects self.history, self.task_log,
    self.system_prompt, self.model_name, self.session_id,
    self._stop_streaming, self._append, self._hard_trim,
    self._log_action, self._window, and all renderer/executor/
    chat_builder imports to be available."""

    def _process_conversation_turn(self) -> None:
        from nbchat.ui import chat_renderer as renderer
        from nbchat.ui import tool_executor as executor
        from nbchat.ui import chat_builder
        from nbchat.core import compressor as comp
        from nbchat.core import client as _client_mod
        db = lazy_import("nbchat.core.db")  # noqa: F821

        real_client = _client_mod.get_client()

        messages = chat_builder.build_messages(
            self._window(), self.system_prompt, self.task_log
        )
        for msg in messages:
            msg.pop("reasoning_content", None)

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

            # --- tool-calling turn ---
            full_msg = {
                "role": "assistant",
                "content": content,
                "reasoning_content": reasoning,
                "tool_calls": tool_calls,
            }
            # Strip reasoning_content before sending to model — it is an
            # output-only field and can be thousands of tokens per step.
            msg_for_model = {k: v for k, v in full_msg.items()
                             if k != "reasoning_content"}
            messages.append(msg_for_model)
            self.history.append(
                ("assistant_full", "", "full", "full", json.dumps(full_msg))
            )
            db.log_message(self.session_id, "assistant", content)

            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                tool_args = tc["function"]["arguments"]

                # Run the tool.
                raw_result = executor.run_tool(tool_name, tool_args)

                # Render immediately with raw output so the UI is responsive.
                # The model receives the compressed version.
                self._append(renderer.render_tool(raw_result, tool_name, tool_args))

                # Compress asynchronously — this is a blocking call but
                # the UI already shows the raw result above.
                compressed = comp.compress_tool_output(
                    tool_name, tool_args, raw_result,
                    model=self.model_name,
                    client=real_client,
                )

                if compressed.strip() == "NO_RELEVANT_OUTPUT":
                    model_result = f"[{tool_name}: no relevant output]"
                else:
                    model_result = compressed

                self._log_action(tool_name, tool_args, model_result)

                # Store raw result in history/DB (full fidelity for UI).
                # Send compressed result to the model only.
                self.history.append(
                    ("tool", raw_result, tc["id"], tool_name, tool_args)
                )
                db.log_tool_msg(
                    self.session_id, tc["id"], tool_name, tool_args, raw_result
                )
                messages.append(
                    {"role": "tool", "tool_call_id": tc["id"], "content": model_result}
                )

    def _stream_response(self, client, messages):
        from nbchat.ui import chat_renderer as renderer
        tools = lazy_import("nbchat.tools")  # noqa: F821

        reasoning_widget = None
        assistant_widget = None
        reasoning_accum = ""
        content_accum = ""
        tool_buffer: dict = {}
        finish_reason = None

        # Hard gate — mathematically prevents context overflow.
        self._hard_trim(messages)

        stream = client.chat.completions.create(
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
                        children.insert(
                            children.index(reasoning_widget) + 1, assistant_widget
                        )
                    else:
                        children.append(assistant_widget)
                    self.chat_history.children = children
                content_accum += delta.content
                assistant_widget.value = renderer.render_assistant(content_accum).value

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    entry = tool_buffer.setdefault(tc.index, {
                        "id": tc.id, "type": "function",
                        "function": {"name": tc.function.name, "arguments": ""},
                    })
                    if tc.function.arguments:
                        entry["function"]["arguments"] += tc.function.arguments

        tool_calls = (
            [tool_buffer[i] for i in sorted(tool_buffer)] if tool_buffer else None
        )

        if tool_calls:
            if assistant_widget is not None:
                assistant_widget.value = renderer.render_assistant_with_tools(
                    content_accum, tool_calls
                ).value
            else:
                assistant_widget = renderer.render_assistant_with_tools("", tool_calls)
                children = list(self.chat_history.children)
                if reasoning_widget in children:
                    children.insert(
                        children.index(reasoning_widget) + 1, assistant_widget
                    )
                else:
                    children.append(assistant_widget)
                self.chat_history.children = children
        elif assistant_widget is None and content_accum:
            assistant_widget = renderer.render_assistant(content_accum)
            self._append(assistant_widget)

        return reasoning_accum, content_accum, tool_calls, finish_reason
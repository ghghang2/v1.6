"""Utility for converting chat history into OpenAI API message format."""
from __future__ import annotations

import json
from typing import List, Dict, Tuple


def build_messages(
    history: List[Tuple[str, str, str, str, str]],
    system_prompt: str,
    task_log: List[str] | None = None,
) -> List[Dict[str, str]]:
    """Build OpenAI messages from internal chat history.

    Parameters
    ----------
    history:
        List of tuples ``(role, content, tool_id, tool_name, tool_args)``.
        Should already be pre-windowed to the last N user turns.
    system_prompt:
        The system message to prepend.
    task_log:
        Optional list of recent action strings maintained by ChatUI.
        When provided they are appended to the system prompt so the model
        always knows what it has been doing even when old messages are
        outside the window.
    """
    system_content = system_prompt
    if task_log:
        entries = "\n".join(f"  {e}" for e in task_log[-20:])
        system_content = (
            system_prompt
            + "\n\n[RECENT ACTION LOG — what has been done so far]\n"
            + entries
            + "\n[END ACTION LOG]"
        )

    messages: List[Dict[str, str]] = [{"role": "system", "content": system_content}]

    for role, content, tool_id, tool_name, tool_args in history:
        if role == "user":
            messages.append({"role": "user", "content": content})
        elif role == "assistant":
            if tool_id:
                messages.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": [{
                        "id": tool_id,
                        "type": "function",
                        "function": {"name": tool_name, "arguments": tool_args},
                    }],
                })
            else:
                messages.append({"role": "assistant", "content": content})
        elif role == "assistant_full":
            try:
                full_msg = json.loads(tool_args)
                messages.append(full_msg)
            except Exception:
                messages.append({"role": "assistant", "content": content})
        elif role == "system":
            messages.append({"role": "system", "content": content})
        elif role == "tool":
            messages.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "content": content,
            })
        # "analysis" rows are reasoning traces — UI display only, not sent to model.

    return messages


__all__ = ["build_messages"]
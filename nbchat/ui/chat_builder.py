"""Utility for converting chat history into OpenAI API message format."""
from __future__ import annotations

import json
from typing import List, Dict, Tuple
import logging

_log = logging.getLogger("nbchat.compaction")

def build_messages(
    history: List[Tuple[str, str, str, str, str, int]],
    system_prompt: str,
    task_log: List[str] | None = None,
) -> List[Dict]:
    """Build OpenAI messages from internal chat history.

    Parameters
    ----------
    history:
        List of canonical 6-tuples:
        ``(role, content, tool_id, tool_name, tool_args, error_flag)``.
        Should already be pre-windowed (via _window()) to the last N user turns.
    system_prompt:
        The system message to prepend.
    task_log:
        Optional list of recent action strings maintained by ChatUI.
        Appended to the system prompt so the model always knows what it
        has been doing even when old messages are outside the window.

    Notes
    -----
    Many local-model servers (llama.cpp, Ollama, …) enforce via their Jinja
    chat template that the *system* role may only appear as the very first
    message.  Injecting additional ``{"role": "system"}`` entries mid-list
    raises a 500 "System message must be at the beginning" error.

    The context manager injects L1 Core Memory, L2 Episodic context, and
    per-turn prior-context summaries as ``("system", …)`` rows at the front
    of the windowed history.  Rather than emitting each as a separate system
    message, this function collects *all* system-role rows that appear in
    *history* before the first non-system row and folds them into a single
    ``messages[0]`` system block.  Any system row that appears after
    conversation content (which should not happen in normal operation but
    could surface in legacy DB rows) is converted to a user-role context
    note so the constraint is never violated.

    ``analysis`` rows are reasoning traces — display-only, never sent to the
    model.  They are silently skipped here.
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

    # Collect any leading system rows from history and merge them into the
    # base system prompt before the first user/assistant/tool message.
    extra_system_parts: List[str] = []
    conversation_started = False
    non_system_history: List[Tuple] = []

    for row in history:
        role = row[0]
        content = row[1]
        if role == "system" and not conversation_started:
            # Leading system row — merge into messages[0].
            extra_system_parts.append(content)
        else:
            if role != "system":
                conversation_started = True
            if role == "system":
                # System row appearing after conversation content — demote to
                # a labelled user context note to satisfy the server constraint.
                non_system_history.append(
                    ("_context_note", content, row[2], row[3], row[4], row[5])
                )
            else:
                non_system_history.append(row)

    if extra_system_parts:
        system_content = system_content + "\n\n" + "\n\n".join(extra_system_parts)

    messages: List[Dict] = [{"role": "system", "content": system_content}]

    for row in non_system_history:
        # Canonical 6-tuple: (role, content, tool_id, tool_name, tool_args, error_flag)
        # error_flag is used by the UI and importance scorer but is not sent to the model.
        role, content, tool_id, tool_name, tool_args, _error_flag = row

        if role == "user":
            messages.append({"role": "user", "content": content})

        elif role == "_context_note":
            # Demoted mid-conversation system row — surface as a user message
            # so the model still sees the context without violating the
            # single-system-message constraint.
            messages.append({"role": "user", "content": f"[CONTEXT NOTE]\n{content}"})

        elif role == "assistant":
            if tool_id:
                messages.append({
                    "role": "assistant",
                    "content": content or None,
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
                full_msg.pop("reasoning_content", None)
                if full_msg.get("tool_calls") and not full_msg.get("content"):
                    full_msg["content"] = None
                messages.append(full_msg)
            except Exception:
                messages.append({"role": "assistant", "content": content})

        elif role == "tool":
            messages.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "content": content,
            })

        # "analysis" rows are reasoning traces — display-only, not sent to model.

    return messages


__all__ = ["build_messages"]
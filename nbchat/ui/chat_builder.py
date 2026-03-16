"""Utility for converting chat history into OpenAI API message format.

KV-cache alignment
------------------
Local inference servers (llama.cpp, vLLM, …) reuse KV cache for any
token-sequence prefix that matches a previous request.  The longest
stable prefix produces the best cache hit rate.

Previous implementation appended the task log, L1 core memory, L2
episodic block, and prior-context summaries directly to
``messages[0]["content"]``.  Because all of these change on every turn,
``messages[0]`` was never identical across calls → zero cache hits on the
system prompt, which is the longest and most expensive block to recompute.

This revision keeps ``messages[0]["content"]`` equal to exactly
``system_prompt``, unmodified.  The volatile context (task log, L1, L2,
prior summaries) is emitted as a synthetic user turn at ``messages[1]``
with a clear ``[SESSION CONTEXT]`` label, followed by a minimal assistant
acknowledgement at ``messages[2]``.  The actual conversation starts at
``messages[3]``.

Result:
  • ``messages[0]`` is token-identical on every call → full cache hit on
    the entire system prompt.
  • ``messages[3..]`` (stable conversation history) is token-identical
    between turns where no new tool calls have completed → cache hit on
    all prior exchanges.
  • Only ``messages[1]`` (volatile context) and the new tail of the
    conversation (latest assistant + tool results + new user message) are
    re-evaluated each turn.
"""
from __future__ import annotations

import json
from typing import List, Dict, Tuple
import logging

_log = logging.getLogger("nbchat.compaction")

# Label used for the synthetic volatile-context user turn.
_CTX_LABEL = "[SESSION CONTEXT — updated each turn]"
# Minimal assistant acknowledgement after the context turn.
_CTX_ACK = "Context received."


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
        Should already be pre-windowed (via _window()) to the last N user
        turns.  Leading ``("system", …)`` rows (L1/L2/prior context blocks
        injected by ContextMixin._window()) are extracted and placed into
        the volatile context turn rather than messages[0].
    system_prompt:
        The static system message.  Written verbatim to ``messages[0]``
        and never modified — this is the contract that enables KV caching.
    task_log:
        Optional list of recent action strings maintained by ChatUI.
        Included in the volatile context turn (messages[1]) so the model
        always knows what it has been doing even when old messages are
        outside the window.

    Message layout
    --------------
    messages[0]  {"role": "system",    "content": system_prompt}  <- static
    messages[1]  {"role": "user",      "content": "[SESSION CONTEXT]..."}  <- volatile
    messages[2]  {"role": "assistant", "content": "Context received."}     <- volatile
    messages[3+] actual conversation turns (user / assistant / tool)

    messages[1] and messages[2] are omitted when there is no volatile
    content (empty task_log and no leading system rows in history), keeping
    the message list minimal for fresh sessions.

    Notes
    -----
    Many local-model servers (llama.cpp, Ollama, ...) enforce via their Jinja
    chat template that the *system* role may only appear as the very first
    message.  This function never emits more than one system-role message.
    Any ``("system", …)`` rows that appear *after* conversation content
    (which should not occur in normal operation but may surface in legacy DB
    rows) are demoted to user-role ``[CONTEXT NOTE]`` messages.

    ``("analysis", …)`` rows are reasoning traces — display-only, never
    sent to the model.
    """
    # ── messages[0]: static system prompt, NEVER modified ─────────────────
    # Keeping this token-identical on every call is the contract for KV cache
    # prefix hits.  Nothing is appended here.
    messages: List[Dict] = [{"role": "system", "content": system_prompt}]

    # ── Separate leading system rows from conversation content ─────────────
    # ContextMixin._window() prepends L1/L2/prior as ("system", …) rows at
    # the front of the history list.  We extract them here and fold them into
    # the volatile context turn rather than messages[0].
    extra_system_parts: List[str] = []
    conversation_started = False
    non_system_history: List[Tuple] = []

    for row in history:
        role = row[0]
        content = row[1]
        if role == "system" and not conversation_started:
            extra_system_parts.append(content)
        else:
            if role != "system":
                conversation_started = True
            if role == "system":
                # System row after conversation has started — demote to a
                # labelled user context note to satisfy the single-system-
                # message constraint.
                non_system_history.append(
                    ("_context_note", content, row[2], row[3], row[4], row[5])
                )
            else:
                non_system_history.append(row)

    # ── messages[1/2]: volatile context turn ──────────────────────────────
    # Assemble task log + L1/L2/prior blocks.  Emitted as a synthetic
    # user turn so that messages[0] stays static.
    volatile_parts: List[str] = []
    if task_log:
        entries = "\n".join(f"  {e}" for e in task_log[-20:])
        volatile_parts.append(
            "[RECENT ACTION LOG — what has been done so far]\n"
            + entries
            + "\n[END ACTION LOG]"
        )
    volatile_parts.extend(extra_system_parts)

    if volatile_parts:
        messages.append({
            "role": "user",
            "content": _CTX_LABEL + "\n\n" + "\n\n".join(volatile_parts),
        })
        messages.append({
            "role": "assistant",
            "content": _CTX_ACK,
        })

    # ── messages[3+]: actual conversation ─────────────────────────────────
    for row in non_system_history:
        # Canonical 6-tuple: (role, content, tool_id, tool_name, tool_args, error_flag)
        # error_flag is used by the UI and importance scorer; not sent to model.
        role, content, tool_id, tool_name, tool_args, _error_flag = row

        if role == "user":
            messages.append({"role": "user", "content": content})

        elif role == "_context_note":
            # Demoted mid-conversation system row — surface as a labelled
            # user message so the model still sees the context.
            messages.append({
                "role": "user",
                "content": f"[CONTEXT NOTE]\n{content}",
            })

        elif role == "assistant":
            if tool_id:
                messages.append({
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": [{
                        "id": tool_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": tool_args,
                        },
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
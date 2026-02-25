"""Compaction Engine
===================

This module implements :class:`~nbchat.compaction.CompactionEngine`, a small
utility used by the :class:`~nbchat.ui.chat_ui.ChatUI` to keep the number of
tokens that are sent to the language model under a user defined limit.

The engine is intentionally lightweight – it does not depend on any heavy
third‑party tokenisation libraries.  Instead, a very small heuristic is used
(`len(text)//3`) which is sufficient for the Llama‑based models used in the
project.

The public API of the engine consists of three methods:

``should_compact(history)``
    Return ``True`` if the estimated number of tokens in *history* exceeds a
percentage of the configured :py:data:`threshold`.

``compact_history(history)``
    Replace the older part of *history* with a single *compacted* message that
contains a summary of the discarded portion.  The method keeps the last
``tail_messages`` entries untouched.

``total_tokens(history)``
    Return an approximate token count for *history*.

The implementation is intentionally easy to understand and test – all logic is
contained inside this module and the class.
"""
from __future__ import annotations

import sys
import threading
from typing import List, Tuple

from nbchat.ui.chat_builder import build_messages
from nbchat.core.client import get_client


class CompactionEngine:
    """A lightweight engine for keeping chat history within token limits.

    Parameters
    ----------
    threshold: int
        The maximum number of tokens that the chat history is allowed to
        contain before a compaction is triggered.
    tail_messages: int, default=5
        Number of the most recent history rows that should be kept verbatim.
    summary_prompt: str, default=None
        Prompt that is passed to the summarisation model.  If ``None`` a
        default prompt that asks for key decisions, file paths, tool calls and
        next steps is used.
    summary_model: str, default=None
        The identifier of the model to use for summarisation.  If ``None`` the
        model specified in :mod:`nbchat.core.config` is used.
    system_prompt: str, default=""
        Optional system prompt that is used when building the message list
        for the summariser.
    """

    def __init__(self, threshold: int, tail_messages: int = 5,
                 summary_prompt: str = None, summary_model: str = None,
                 system_prompt: str = ""):
        self.threshold = threshold
        self.tail_messages = tail_messages
        self.summary_prompt = summary_prompt or (
            "Summarize the conversation history above. Focus on:\n"
            "1. Key decisions made\n"
            "2. Important file paths and edits\n"
            "3. Tool calls and their outcomes (summarize large outputs)\n"
            "4. Next steps planned\n"
            "Keep it concise but preserve essential context."
        )
        self.summary_model = summary_model
        self.system_prompt = system_prompt
        self._cache: dict = {}
        self._cache_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Token estimation
    # ------------------------------------------------------------------

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 3)

    def total_tokens(self, history: List[Tuple[str, str, str, str, str]]) -> int:
        """Estimate total tokens across all history entries.

        Counts content + tool_args for every row. For ``assistant_full``
        rows the payload is entirely in ``tool_args`` (a JSON blob); for
        ``analysis`` rows it is in ``content``. Both fields are always
        counted so no role is accidentally free.
        """
        total = 0
        for role, content, tool_id, tool_name, tool_args in history:
            msg_hash = hash((content, tool_args))
            with self._cache_lock:
                if msg_hash in self._cache:
                    total += self._cache[msg_hash]
                    continue

            tokens = self._estimate_tokens(content) + (
                self._estimate_tokens(tool_args) if tool_args else 0
            )
            with self._cache_lock:
                self._cache[msg_hash] = tokens
            total += tokens
        return total

    def should_compact(self, history: List[Tuple[str, str, str, str, str]]) -> bool:
        # Don't compact if the history is already in a compacted state
        # (starts with a compacted row and is short) — prevents infinite loops.
        if history and history[0][0] == "compacted" and len(history) <= self.tail_messages + 1:
            return False
        tokens = self.total_tokens(history)
        trigger = int(self.threshold * 0.75)
        print(
            f"[compaction] token estimate: {tokens} / {self.threshold} (trigger={trigger})",
            file=sys.stderr,
        )
        return tokens >= trigger

    # ------------------------------------------------------------------
    # Compaction
    # ------------------------------------------------------------------

    def compact_history(
        self, history: List[Tuple[str, str, str, str, str]]
    ) -> List[Tuple[str, str, str, str, str]]:
        """Summarize the older portion of history, keeping the tail intact.

        Strategy
        --------
        1. Split history into ``older`` (to be summarised) and ``tail``
           (kept verbatim).
        2. ``tail_start`` is nudged backwards so it never lands in the
           middle of a logical turn (tool result / analysis / full-msg).
        3. Build API messages from ``older`` using the real system prompt
           so the model has full context, then append the summary request.
        4. Return ``[compacted_row] + tail``.
        """
        print(
            f"[compaction] compact_history called, history len={len(history)}, "
            f"tail_messages={self.tail_messages}",
            file=sys.stderr,
        )

        if len(history) <= self.tail_messages:
            print("[compaction] history too short to compact", file=sys.stderr)
            return history

        tail_start = len(history) - self.tail_messages

        # The ONLY safe split point is a ``user`` message — the llama.cpp
        # Jinja template requires every ``tool`` result to be preceded by an
        # assistant message with a tool_call, so we must never let ``tail``
        # begin with a tool/analysis/assistant_full row.  Walking back to the
        # nearest ``user`` row guarantees the tail starts a complete exchange.
        while tail_start > 0 and history[tail_start][0] != "user":
            tail_start -= 1

        if tail_start <= 0:
            print("[compaction] no user-message boundary found, skipping", file=sys.stderr)
            return history

        # Guard: older must be at least 2 rows so there is something to summarise.
        if tail_start < 2:
            print(
                f"[compaction] older slice too small ({tail_start} rows), skipping",
                file=sys.stderr,
            )
            return history

        older = history[:tail_start]
        tail = history[tail_start:]

        print(
            f"[compaction] older={len(older)} rows, tail={len(tail)} rows",
            file=sys.stderr,
        )

        # Build messages from the older slice, using the real system prompt
        # so the summariser has full context.
        messages = build_messages(older, self.system_prompt)

        # Strip reasoning_content — it is an output-only field and will
        # cause errors or be silently dropped by most inference servers.
        for msg in messages:
            msg.pop("reasoning_content", None)

        # Append the summarisation instruction as a user turn.
        messages.append({"role": "user", "content": self.summary_prompt})

        print(
            f"[compaction] sending {len(messages)} messages to summariser",
            file=sys.stderr,
        )

        try:
            client = get_client()
            response = client.chat.completions.create(
                model=self.summary_model,
                messages=messages,
                max_tokens=4096,
            )
        except Exception as e:
            raise RuntimeError(f"Summarization failed: {e}") from e

        summary_text = response.choices[0].message.content
        print(
            f"[compaction] summary produced ({len(summary_text)} chars): "
            f"{summary_text[:120]}...",
            file=sys.stderr,
        )

        # Invalidate token cache — history shape has changed.
        with self._cache_lock:
            self._cache.clear()

        return [("compacted", summary_text, "", "", "")] + list(tail)


__all__ = ["CompactionEngine"]
"""Context management mixin for ChatUI.

Three mechanisms keep messages within the model's context limit:
  1. Sliding window   — only the last WINDOW_TURNS user turns enter the window.
  2. Prior context    — turns that slid off are summarized per-turn by an LLM
                        and injected as a single system row so the model retains
                        full awareness of earlier goals, corrections, and outcomes.
  3. Hard trim        — enforced immediately before every API call as a last
                        resort, dropping oldest tool-exchange pairs atomically.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import List, Optional, Tuple

from nbchat.core.utils import lazy_import

_log = logging.getLogger("nbchat.compaction")
_Row = Tuple[str, str, str, str, str]

# Prompt sent to the LLM to summarize a single user turn.
_SUMMARY_PROMPT = (
    "Summarise this conversation segment in 2–4 sentences. "
    "Include: what the user asked, which tools were called and their key outcomes, "
    "and the final state or result. Be factual and concrete. No preamble."
)

# Truncate individual tool results to this length before sending to summarizer
# to avoid blowing the summarizer's own context.
_SUMMARIZER_TOOL_CHARS = 2_000


class ContextMixin:
    """Mixed into ChatUI.

    Expects the following attributes on the host class:
      self.history, self.task_log, self.system_prompt, self.model_name,
      self.session_id, self._turn_summary_cache, self.WINDOW_TURNS
    """

    # ------------------------------------------------------------------
    # Sliding window
    # ------------------------------------------------------------------

    def _window(self) -> List[_Row]:
        """Return the bounded slice of history sent to the model.

        History before the window cut is summarized per user-turn and
        prepended as a synthetic system row, giving the model full
        awareness of earlier goals, corrections, and outcomes without
        the raw token cost of old tool output.
        """
        config = lazy_import("nbchat.core.config")
        MAX_WINDOW_ROWS = config.MAX_WINDOW_ROWS

        # Walk backward to find the cut point (oldest kept user turn).
        user_count = 0
        cut = 0
        for i in range(len(self.history) - 1, -1, -1):
            if self.history[i][0] == "user":
                user_count += 1
                if user_count == self.WINDOW_TURNS:
                    cut = i
                    break

        window = list(self.history[cut:])

        # Apply hard row cap, snapping forward to the nearest user row.
        if len(window) > MAX_WINDOW_ROWS:
            start = len(window) - MAX_WINDOW_ROWS
            while start < len(window) and window[start][0] != "user":
                start += 1
            if start < len(window):
                window = window[start:]

        # Prepend a prior-context summary for everything before the cut.
        if cut > 0:
            prior = self._build_prior_context(self.history[:cut])
            if prior:
                window = [("system", prior, "", "", "")] + window

        return window

    # ------------------------------------------------------------------
    # Per-turn summarization
    # ------------------------------------------------------------------

    def _build_prior_context(self, prior_rows: List[_Row]) -> Optional[str]:
        """Return a compact natural-language block covering all prior turns."""
        units = _group_by_user_turn(prior_rows)
        if not units:
            return None

        lines = []
        for i, unit in enumerate(units, 1):
            user_row = next((r for r in unit if r[0] == "user"), None)
            user_text = user_row[1][:200] if user_row else "(no user message)"
            summary = self._get_turn_summary(unit)
            lines.append(f'Turn {i} — User: "{user_text}"\n  {summary}')

        return "[Prior session context — earlier turns summarized]\n" + "\n".join(lines)

    def _get_turn_summary(self, unit: List[_Row]) -> str:
        """Return a cached summary for *unit*, generating via LLM on first call."""
        # Stable hash: sha1 of concatenated content + tool_args for each row.
        key = hashlib.sha1(
            "".join(r[1] + r[4] for r in unit).encode()
        ).hexdigest()

        cached = self._turn_summary_cache.get(key)
        if cached:
            return cached

        summary = self._call_summarizer(unit)
        self._turn_summary_cache[key] = summary

        db = lazy_import("nbchat.core.db")
        db.save_turn_summaries(self.session_id, self._turn_summary_cache)
        return summary

    def _call_summarizer(self, unit: List[_Row]) -> str:
        """Call the model to produce a 2–4 sentence summary of *unit*."""
        from nbchat.core import client as _client_mod
        from nbchat.ui.chat_builder import build_messages

        # Truncate large tool outputs so the summarizer call stays cheap.
        trimmed = [
            (role,
             content[:_SUMMARIZER_TOOL_CHARS] if role == "tool" else content,
             tid, tname, targs)
            for role, content, tid, tname, targs in unit
        ]

        messages = build_messages(trimmed, self.system_prompt)
        for m in messages:
            m.pop("reasoning_content", None)
        # Strip dangling tool_calls — API rejects an assistant message with
        # tool_calls if no matching tool results follow.
        if messages and messages[-1].get("role") == "assistant":
            messages[-1].pop("tool_calls", None)
            if not messages[-1].get("content"):
                messages.pop()

        messages.append({"role": "user", "content": _SUMMARY_PROMPT})

        try:
            resp = _client_mod.get_client().chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=256,
            )
            summary = resp.choices[0].message.content.strip()
            _log.debug(f"turn summary ({len(summary)} chars): {summary[:80]}…")
            return summary
        except Exception as exc:
            _log.debug(f"summarizer failed: {exc} — using fallback")
            user_text = next((r[1][:100] for r in unit if r[0] == "user"), "")
            tool_hint = next(
                (r[1].split("\n")[0][:80] for r in unit if r[0] == "tool"), ""
            )
            return f"(summary unavailable) User: {user_text}. {tool_hint}"

    # ------------------------------------------------------------------
    # Hard trim — last resort before every API call
    # ------------------------------------------------------------------

    def _hard_trim(self, messages: list) -> None:
        """Drop oldest tool-exchange pairs until messages fit the token budget.

        An exchange = one assistant-with-tool-calls + all immediately following
        tool-result messages.  Always dropped atomically to preserve the
        invariant that every tool message has a preceding assistant tool_call.

        messages[0] = system prompt.
        messages[1] = prior-context system row (or first user message).
        Both are protected by starting the exchange scan at index 2.
        """
        config = lazy_import("nbchat.core.config")
        limit = int(config.CONTEXT_TOKEN_THRESHOLD * 0.85)
        MAX_EXCHANGES = config.MAX_EXCHANGES
        KEEP_RECENT = config.KEEP_RECENT_EXCHANGES

        def est(msg: dict) -> int:
            content = msg.get("content") or ""
            tcs = msg.get("tool_calls") or []
            tc_text = "".join(tc.get("function", {}).get("arguments", "") for tc in tcs)
            return max(1, (len(content) + len(tc_text)) // 3)

        def total() -> int:
            return sum(est(m) for m in messages)

        def get_exchanges() -> list:
            result = []
            i = 2  # protect system (0) and prior-context/first-user (1)
            while i < len(messages):
                m = messages[i]
                if m.get("role") == "assistant" and m.get("tool_calls"):
                    end = i + 1
                    while end < len(messages) and messages[end].get("role") == "tool":
                        end += 1
                    result.append((i, end))
                    i = end
                else:
                    i += 1
            return result

        # Pass 1: hard cap on exchange count (prevents cascade on long sessions).
        while True:
            exchanges = get_exchanges()
            if len(exchanges) <= MAX_EXCHANGES:
                break
            s, e = exchanges[0]
            _log.debug(f"_hard_trim: cap drop [{s}:{e}], {len(exchanges)} exchanges")
            del messages[s:e]

        # Pass 2: token-budget drops, keeping the most recent KEEP_RECENT exchanges.
        while total() > limit:
            exchanges = get_exchanges()
            droppable = exchanges[:-KEEP_RECENT] if len(exchanges) > KEEP_RECENT else []
            if not droppable:
                break
            s, e = droppable[0]
            dropped = [messages[s + j].get("content", "")[:80]
                       for j in range(1, e - s)
                       if messages[s + j].get("role") == "tool"]
            if dropped and messages[0].get("role") == "system":
                messages[0]["content"] += f"\n[earlier: {' | '.join(dropped)}]"
            _log.debug(f"_hard_trim: budget drop [{s}:{e}], total={total()}")
            del messages[s:e]

        # Pass 3: last resort — truncate the largest individual tool result.
        while total() > limit:
            tool_indices = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
            if not tool_indices:
                break
            largest = max(tool_indices, key=lambda i: len(messages[i].get("content", "")))
            original = messages[largest].get("content", "")
            if len(original) <= 200:
                break
            messages[largest]["content"] = (
                original[:200] + f"\n[...truncated {len(original) - 200} chars...]"
            )
            _log.debug(f"_hard_trim: truncated tool result [{largest}] {len(original)}→200")

    # ------------------------------------------------------------------
    # Task log
    # ------------------------------------------------------------------

    def _log_action(self, tool_name: str, tool_args: str, result: str) -> None:
        """Append one line to the running task log for this tool call."""
        db = lazy_import("nbchat.core.db")
        try:
            args_obj = json.loads(tool_args)
            hint = next(
                (str(v)[:60] for v in args_obj.values() if isinstance(v, str)),
                tool_args[:60],
            )
        except Exception:
            hint = tool_args[:60]

        first_line = result.split("\n")[0][:120]
        if first_line.strip() == "NO_RELEVANT_OUTPUT":
            first_line = "(no relevant output)"

        entry = f"{tool_name}({hint}) → {first_line}"
        self.task_log.append(entry)
        if len(self.task_log) > 30:
            self.task_log = self.task_log[-30:]
        db.save_task_log(self.session_id, self.task_log)
        _log.debug(f"task_log: {entry}")


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _group_by_user_turn(rows: List[_Row]) -> List[List[_Row]]:
    """Split *rows* into per-user-turn groups.

    Each group starts with a user row and contains all subsequent
    assistant/tool/analysis rows up to (but not including) the next user row.
    """
    units: List[List[_Row]] = []
    current: List[_Row] = []
    for row in rows:
        if row[0] == "user" and current:
            units.append(current)
            current = [row]
        else:
            current.append(row)
    if current:
        units.append(current)
    return units
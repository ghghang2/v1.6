"""Context management mixin for ChatUI.

Five mechanisms keep messages within the model's context limit and preserve
awareness across ultra-long agentic loops:

  1. L0 Sliding window   — only the last WINDOW_TURNS user turns enter the
                           hot buffer verbatim.
  2. L1 Core Memory      — typed persistent slots (goal, constraints, active
                           entities, error history, last user correction)
                           injected as a dedicated system block on every call.
  3. L2 Episodic store   — append-only SQLite log of tool exchanges, tagged
                           with entity refs and importance scores.  Relevant
                           entries are retrieved and injected before the window.
  4. Prior context       — turns that slid off are summarized per-turn by an
                           LLM using a structured GOAL/ENTITIES/RATIONALE
                           format and injected as a system block.
  5. Importance-scored hard trim — exchanges are scored before eviction;
                           those above L2_WRITE_THRESHOLD are persisted to
                           the L2 episodic store before being dropped from
                           the hot context.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import List, Optional, Tuple

from nbchat.core.utils import lazy_import

_log = logging.getLogger("nbchat.compaction")
_Row = Tuple[str, str, str, str, str]

# ── Tuning knobs ──────────────────────────────────────────────────────────────
# Minimum importance score to persist an exchange to L2 before eviction.
L2_WRITE_THRESHOLD = 3.5
# Max episodic entries injected per API call.
L2_RETRIEVAL_LIMIT = 5
# Minimum importance score for L2 entries retrieved by importance (not entity match).
L2_MIN_IMPORTANCE_FOR_RETRIEVAL = 3.0
# How many active entities to keep in L1 core memory.
CORE_MEMORY_ACTIVE_ENTITIES_LIMIT = 20
# How many recent error strings to keep in L1.
CORE_MEMORY_ERROR_HISTORY_LIMIT = 5
# Chars of tool output passed to the summariser.
_SUMMARIZER_TOOL_CHARS = 2_000
# Keywords that signal a user correction.
_CORRECTION_KEYWORDS = (
    "actually", "wait,", "no,", "wrong", "instead", "correct",
    "not that", "stop,", "that's not", "don't do", "undo",
)

# ── Prompts ───────────────────────────────────────────────────────────────────
_STRUCTURED_SUMMARY_PROMPT = (
    "Analyse this conversation segment and output EXACTLY three labelled lines.\n"
    "GOAL: <one sentence — what the user was trying to accomplish in this segment>\n"
    "ENTITIES: <pipe-separated entity state changes, e.g. "
    "'file:report.py created | api:/users → 404 | task:login done'. "
    "Use 'none' if there are no meaningful entity changes.>\n"
    "RATIONALE: <one sentence — the key action taken and whether it achieved "
    "the expected outcome>\n"
    "Be factual and concrete. Output exactly three lines with the exact labels "
    "GOAL:, ENTITIES:, RATIONALE: — no preamble, no extra lines."
)


# ── Module-level helpers ──────────────────────────────────────────────────────

def _parse_structured_summary(text: str) -> dict:
    """Parse a GOAL/ENTITIES/RATIONALE structured summary into a dict."""
    result: dict = {"goal": "", "entities": [], "rationale": ""}
    for line in text.strip().splitlines():
        if line.startswith("GOAL:"):
            result["goal"] = line[5:].strip()
        elif line.startswith("ENTITIES:"):
            raw = line[9:].strip()
            if raw.lower() != "none":
                result["entities"] = [e.strip() for e in raw.split("|") if e.strip()]
        elif line.startswith("RATIONALE:"):
            result["rationale"] = line[10:].strip()
    return result


def _extract_entities(text: str) -> List[str]:
    """Extract entity references (file paths, API paths, URLs) from *text*.

    Returns a deduplicated list capped at 10 entries.
    """
    entities: List[str] = []
    # Source-code and config file paths
    for m in re.finditer(
        r'\b[\w\-./]+\.(?:py|js|ts|jsx|tsx|json|yaml|yml|txt|md|html|'
        r'css|sh|env|cfg|ini|toml|sql|csv|lock|log)\b',
        text,
    ):
        entities.append(m.group())
    # API / URL paths  (e.g. /api/v1/users)
    for m in re.finditer(r'(?<!\w)/[a-z][a-z0-9_/\-]{2,40}', text):
        entities.append("api:" + m.group()[:50])
    # Bare hostnames from URLs
    for m in re.finditer(r'https?://([^/\s"\']{4,60})', text):
        entities.append("url:" + m.group(1))
    # Deduplicate preserving insertion order, cap at 10
    seen: set = set()
    result: List[str] = []
    for e in entities:
        if e not in seen:
            seen.add(e)
            result.append(e)
        if len(result) >= 10:
            break
    return result


def _group_by_user_turn(rows: List[_Row]) -> List[List[_Row]]:
    """Split *rows* into per-user-turn groups."""
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


# ── Mixin ─────────────────────────────────────────────────────────────────────

class ContextMixin:
    """Mixed into ChatUI.

    Expects the following attributes on the host class:
      self.history, self.task_log, self.system_prompt, self.model_name,
      self.session_id, self._turn_summary_cache, self.WINDOW_TURNS
    """

    # ── Importance scoring ────────────────────────────────────────────────────

    @staticmethod
    def _importance_score(exchange_msgs: list) -> float:
        """Score a tool exchange (list of message dicts) from 0.0–10.0.

        Higher score = retain longer under trim pressure.
        Boosts exchanges marked with error_flag for protection.
        """
        score = 1.0
        has_error_flag = False
        for msg in exchange_msgs:
            content = (msg.get("content") or "").lower()
            role = msg.get("role", "")
            # Check for explicit error_flag indicator in message
            if msg.get("error_flag") == 1 or "error_flag" in msg:
                has_error_flag = True
                break
            if any(k in content for k in ("error", "exception", "failed", "cannot", "traceback")):
                score += 3.0
            if role == "user" and any(
                k in content for k in ("correct", "wrong", "actually", "instead", "don't")
            ):
                score += 2.5
            if role == "tool" and any(
                k in content for k in ("success", "completed", "done", "created", "written")
            ):
                score += 1.5
            # Long tool results are often structurally important
            if role == "tool" and len(content) > 500:
                score += 0.5
        # Boost score for exchanges with error_flag (additional 5.0 points)
        if has_error_flag:
            score += 5.0
        return min(score, 10.0)

    # ── L1 Core Memory ────────────────────────────────────────────────────────

    def _get_l1_block(self) -> Optional[str]:
        """Return the L1 Core Memory system block, or None if empty."""
        try:
            db = lazy_import("nbchat.core.db")
            cm = db.get_core_memory(self.session_id)
        except Exception:
            return None
        if not cm:
            return None

        parts: List[str] = []
        if cm.get("goal"):
            parts.append(f"Goal: {cm['goal']}")
        if cm.get("constraints"):
            try:
                c = json.loads(cm["constraints"])
                if c:
                    parts.append(f"Constraints: {'; '.join(c)}")
            except Exception:
                if cm["constraints"]:
                    parts.append(f"Constraints: {cm['constraints']}")
        if cm.get("active_entities"):
            try:
                e = json.loads(cm["active_entities"])
                if e:
                    parts.append(f"Active entities: {', '.join(e[:15])}")
            except Exception:
                pass
        if cm.get("error_history"):
            try:
                eh = json.loads(cm["error_history"])
                if eh:
                    parts.append(f"Recent errors: {' | '.join(eh[-3:])}")
            except Exception:
                pass
        if cm.get("last_correction"):
            parts.append(f"Last user correction: {cm['last_correction']}")

        if not parts:
            return None
        return (
            "[CORE MEMORY — persistent task state]\n"
            + "\n".join(parts)
            + "\n[END CORE MEMORY]"
        )

    def _update_l1_goal_from_user(self, user_message: str) -> None:
        """Update L1 goal (and optionally last_correction) from a user message."""
        try:
            db = lazy_import("nbchat.core.db")
            lower = user_message.lower()
            updates: dict = {"goal": user_message[:300]}
            if any(
                lower.startswith(kw) or f" {kw} " in lower
                for kw in _CORRECTION_KEYWORDS
            ):
                updates["last_correction"] = user_message[:300]
            db.update_core_memory(self.session_id, updates)
        except Exception as exc:
            _log.debug(f"_update_l1_goal_from_user failed: {exc}")

    def _update_l1_from_exchange(
        self, tool_name: str, tool_args: str, result: str
    ) -> None:
        """Update L1 active entities and error history after a tool call."""
        try:
            db = lazy_import("nbchat.core.db")
            cm = db.get_core_memory(self.session_id) or {}

            new_entities = _extract_entities(tool_args + " " + result)
            try:
                existing = json.loads(cm.get("active_entities", "[]"))
            except Exception:
                existing = []
            # Merge new entities at the front (most recent = most relevant)
            merged = list(dict.fromkeys(new_entities + existing))
            merged = merged[:CORE_MEMORY_ACTIVE_ENTITIES_LIMIT]
            updates: dict = {"active_entities": json.dumps(merged)}

            lower_result = result.lower()
            if any(
                k in lower_result
                for k in ("error", "exception", "failed", "cannot", "traceback")
            ):
                first_line = result.split("\n")[0][:120]
                try:
                    errors = json.loads(cm.get("error_history", "[]"))
                except Exception:
                    errors = []
                errors.append(first_line)
                updates["error_history"] = json.dumps(
                    errors[-CORE_MEMORY_ERROR_HISTORY_LIMIT:]
                )

            db.update_core_memory(self.session_id, updates)
        except Exception as exc:
            _log.debug(f"_update_l1_from_exchange failed: {exc}")

    # ── L2 Episodic Store ─────────────────────────────────────────────────────

    def _get_l2_block(self, active_entities: List[str]) -> Optional[str]:
        """Return the L2 Episodic Context block, or None if no entries match."""
        try:
            db = lazy_import("nbchat.core.db")
            entries: List[dict] = []
            seen_ids: set = set()

            # 1) Entity-match retrieval
            if active_entities:
                matched = db.query_episodic_by_entities(
                    self.session_id, active_entities, limit=L2_RETRIEVAL_LIMIT
                )
                for e in matched:
                    seen_ids.add(e["id"])
                    entries.append(e)

            # 2) Top-importance fill if under limit
            if len(entries) < L2_RETRIEVAL_LIMIT:
                remaining = L2_RETRIEVAL_LIMIT - len(entries)
                top = db.query_episodic_top_importance(
                    self.session_id,
                    min_score=L2_MIN_IMPORTANCE_FOR_RETRIEVAL,
                    limit=remaining + len(seen_ids),
                )
                for e in top:
                    if e["id"] not in seen_ids:
                        entries.append(e)
                        seen_ids.add(e["id"])
                        if len(entries) >= L2_RETRIEVAL_LIMIT:
                            break
        except Exception as exc:
            _log.debug(f"_get_l2_block query failed: {exc}")
            return None

        if not entries:
            return None

        lines: List[str] = []
        for e in entries:
            entity_str = ""
            try:
                refs = json.loads(e.get("entity_refs", "[]"))
                if refs:
                    entity_str = f" [{', '.join(refs[:5])}]"
            except Exception:
                pass
            lines.append(
                f"• {e['action_type']}: {e['outcome_summary']}"
                f"{entity_str} (importance: {e['importance_score']:.1f})"
            )

        return (
            "[RELEVANT PAST EVENTS — retrieved from episodic memory]\n"
            + "\n".join(lines)
            + "\n[END EPISODIC CONTEXT]"
        )

    def _write_exchange_to_episodic(
        self,
        turn: int,
        tool_name: str,
        tool_args: str,
        result: str,
        importance: float,
    ) -> None:
        """Persist a tool exchange to L2 if it meets the importance threshold."""
        if importance < L2_WRITE_THRESHOLD:
            return
        try:
            db = lazy_import("nbchat.core.db")
            entities = _extract_entities(tool_args + " " + result)
            outcome = result.split("\n")[0][:200]
            db.append_episodic(
                session_id=self.session_id,
                turn_id=turn,
                action_type=tool_name,
                entity_refs=json.dumps(entities),
                outcome_summary=outcome,
                importance_score=importance,
            )
        except Exception as exc:
            _log.debug(f"_write_exchange_to_episodic failed: {exc}")

    # ── Sliding window ────────────────────────────────────────────────────────

    def _window(self) -> List[_Row]:
        """Return the bounded slice of history sent to the model.

        Prepends up to three context system rows:
          1. L1 Core Memory block  (always, if non-empty)
          2. L2 Episodic context   (conditional on active entities / importance)
          3. Structured prior context summaries (if turns slid off)
        """
        config = lazy_import("nbchat.core.config")
        MAX_WINDOW_ROWS = config.MAX_WINDOW_ROWS

        # ── Sliding window cut ──
        user_count = 0
        cut = 0
        for i in range(len(self.history) - 1, -1, -1):
            if self.history[i][0] == "user":
                user_count += 1
                if user_count == self.WINDOW_TURNS:
                    cut = i
                    break

        window = list(self.history[cut:])

        if len(window) > MAX_WINDOW_ROWS:
            start = len(window) - MAX_WINDOW_ROWS
            while start < len(window) and window[start][0] != "user":
                start += 1
            if start < len(window):
                window = window[start:]

        # ── Build context prefix ──
        prefix: List[_Row] = []

        # L1 Core Memory
        l1_block = self._get_l1_block()
        if l1_block:
            prefix.append(("system", l1_block, "", "", ""))

        # L2 Episodic retrieval (use active entities from L1 to guide query)
        try:
            db = lazy_import("nbchat.core.db")
            cm = db.get_core_memory(self.session_id) or {}
            active_entities = json.loads(cm.get("active_entities", "[]"))
        except Exception:
            active_entities = []
        l2_block = self._get_l2_block(active_entities)
        if l2_block:
            prefix.append(("system", l2_block, "", "", ""))

        # Structured prior context summaries
        if cut > 0:
            prior = self._build_prior_context(self.history[:cut])
            if prior:
                prefix.append(("system", prior, "", "", ""))

        return prefix + window

    # ── Per-turn structured summarisation ────────────────────────────────────

    def _build_prior_context(self, prior_rows: List[_Row]) -> Optional[str]:
        """Return a structured summary block covering all prior turns."""
        units = _group_by_user_turn(prior_rows)
        if not units:
            return None

        lines: List[str] = []
        for i, unit in enumerate(units, 1):
            user_row = next((r for r in unit if r[0] == "user"), None)
            user_text = user_row[1][:200] if user_row else "(no user message)"
            raw_summary = self._get_turn_summary(unit)
            parsed = _parse_structured_summary(raw_summary)

            line = f'Turn {i} — User: "{user_text}"'
            if parsed["goal"]:
                line += f"\n  Goal: {parsed['goal']}"
            if parsed["entities"]:
                line += f"\n  Entities: {' | '.join(parsed['entities'])}"
            if parsed["rationale"]:
                line += f"\n  Outcome: {parsed['rationale']}"
            # Graceful fallback: old-format (unstructured) cached summaries
            if not any([parsed["goal"], parsed["entities"], parsed["rationale"]]):
                line += f"\n  {raw_summary}"
            lines.append(line)

        return (
            "[PRIOR SESSION CONTEXT — earlier turns summarized]\n"
            + "\n".join(lines)
            + "\n[END PRIOR CONTEXT]"
        )

    def _get_turn_summary(self, unit: List[_Row]) -> str:
        """Return a cached summary for *unit*, generating via LLM on first call."""
        key = hashlib.sha1(
            "".join(r[1] + r[4] for r in unit).encode()
        ).hexdigest()

        cached = self._turn_summary_cache.get(key)
        if cached:
            return cached

        summary = self._call_summarizer(unit)
        self._turn_summary_cache[key] = summary

        try:
            db = lazy_import("nbchat.core.db")
            db.save_turn_summaries(self.session_id, self._turn_summary_cache)
        except Exception:
            pass
        return summary

    def _call_summarizer(self, unit: List[_Row]) -> str:
        """Call the model to produce a structured GOAL/ENTITIES/RATIONALE summary."""
        from nbchat.core import client as _client_mod
        from nbchat.ui.chat_builder import build_messages

        trimmed = [
            (
                role,
                content[:_SUMMARIZER_TOOL_CHARS] if role == "tool" else content,
                tid, tname, targs,
            )
            for role, content, tid, tname, targs in unit
        ]

        messages = build_messages(trimmed, self.system_prompt)
        for m in messages:
            m.pop("reasoning_content", None)
        if messages and messages[-1].get("role") == "assistant":
            messages[-1].pop("tool_calls", None)
            if not messages[-1].get("content"):
                messages.pop()

        messages.append({"role": "user", "content": _STRUCTURED_SUMMARY_PROMPT})

        try:
            resp = _client_mod.get_client().chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=256,
            )
            summary = resp.choices[0].message.content.strip()
            _log.debug(f"turn summary ({len(summary)} chars): {summary[:80]}...")
            return summary
        except Exception as exc:
            _log.debug(f"summarizer failed: {exc} — using fallback")
            user_text = next((r[1][:100] for r in unit if r[0] == "user"), "")
            tool_hint = next(
                (r[1].split("\n")[0][:80] for r in unit if r[0] == "tool"), ""
            )
            return (
                f"GOAL: (summary unavailable) {user_text}\n"
                f"ENTITIES: none\n"
                f"RATIONALE: {tool_hint}"
            )

    # ── Importance-scored hard trim ───────────────────────────────────────────

    def _hard_trim(self, messages: list) -> None:
        """Drop least-important tool-exchange pairs until messages fit the budget.

        Before evicting an exchange whose importance score meets L2_WRITE_THRESHOLD,
        the exchange is persisted to the L2 episodic store so the information is
        never permanently lost.

        messages[0] = system prompt.
        messages[1] = first context/user row (protected).
        Exchange scan starts at index 2.
        """
        config = lazy_import("nbchat.core.config")
        limit = int(config.CONTEXT_TOKEN_THRESHOLD * 0.85)
        MAX_EXCHANGES = config.MAX_EXCHANGES
        KEEP_RECENT = config.KEEP_RECENT_EXCHANGES

        def est(msg: dict) -> int:
            content = msg.get("content") or ""
            tcs = msg.get("tool_calls") or []
            tc_text = "".join(
                tc.get("function", {}).get("arguments", "") for tc in tcs
            )
            return max(1, (len(content) + len(tc_text)) // 2)

        def total() -> int:
            return sum(est(m) for m in messages)

        def get_exchanges() -> List[Tuple[int, int]]:
            result = []
            i = 2  # protect system (0) and prior-context/first-user (1)
            while i < len(messages):
                if messages[i].get("role") == "assistant" and messages[i].get("tool_calls"):
                    end = i + 1
                    while end < len(messages) and messages[end].get("role") == "tool":
                        end += 1
                    result.append((i, end))
                    i = end
                else:
                    i += 1
            return result

        def drop_least_important(exchanges: List[Tuple[int, int]]) -> None:
            scored = [
                (self._importance_score(messages[s:e]), s, e)
                for s, e in exchanges
            ]
            scored.sort(key=lambda x: x[0])
            score, s, e = scored[0]

            # ── L2 write-before-drop ──
            if score >= L2_WRITE_THRESHOLD:
                # Resolve tool name from the assistant message's first tool call
                action_name = ""
                tc_list = messages[s].get("tool_calls") or []
                if tc_list:
                    action_name = tc_list[0].get("function", {}).get("name", "")
                # Resolve tool args
                tc_args = ""
                if tc_list:
                    tc_args = tc_list[0].get("function", {}).get("arguments", "")
                # Collect tool results
                for j in range(s + 1, e):
                    if messages[j].get("role") == "tool":
                        result_text = messages[j].get("content", "")
                        entities = _extract_entities(tc_args + " " + result_text)
                        outcome = result_text.split("\n")[0][:200]
                        try:
                            db = lazy_import("nbchat.core.db")
                            db.append_episodic(
                                session_id=self.session_id,
                                turn_id=0,
                                action_type=action_name or "unknown",
                                entity_refs=json.dumps(entities),
                                outcome_summary=outcome,
                                importance_score=score,
                            )
                            _log.debug(
                                f"_hard_trim: saved to L2 [{action_name}] "
                                f"score={score:.1f}"
                            )
                        except Exception as exc:
                            _log.debug(f"_hard_trim L2 write failed: {exc}")

            # ── Summarise evicted content into system row ──
            dropped = [
                messages[s + j].get("content", "")[:80]
                for j in range(1, e - s)
                if messages[s + j].get("role") == "tool"
            ]
            if dropped and messages[0].get("role") == "system":
                messages[0]["content"] += f"\n[earlier: {' | '.join(dropped)}]"

            _log.debug(f"_hard_trim: drop [{s}:{e}] score={score:.1f}")
            del messages[s:e]

        # Pass 1: hard cap on exchange count.
        while True:
            exchanges = get_exchanges()
            if len(exchanges) <= MAX_EXCHANGES:
                break
            drop_least_important(exchanges)

        # Pass 2: token-budget drops, keeping KEEP_RECENT most recent exchanges.
        while total() > limit:
            exchanges = get_exchanges()
            droppable = (
                exchanges[:-KEEP_RECENT] if len(exchanges) > KEEP_RECENT else []
            )
            if not droppable:
                break
            drop_least_important(droppable)
            _log.debug(f"_hard_trim: after budget drop total={total()}")

        # Pass 3: last resort — truncate the largest individual tool result.
        while total() > limit:
            tool_indices = [
                i for i, m in enumerate(messages) if m.get("role") == "tool"
            ]
            if not tool_indices:
                break
            largest = max(
                tool_indices, key=lambda i: len(messages[i].get("content", ""))
            )
            original = messages[largest].get("content", "")
            if len(original) <= 200:
                break
            messages[largest]["content"] = (
                original[:200] + f"\n[...truncated {len(original) - 200} chars...]"
            )
            _log.debug(f"_hard_trim: truncated [{largest}] {len(original)}→200")

    # ── Task log ─────────────────────────────────────────────────────────────

    def _log_action(self, tool_name: str, tool_args: str, result: str) -> None:
        """Append one line to the running task log for this tool call."""
        try:
            db = lazy_import("nbchat.core.db")
        except Exception:
            return
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

        entry = f"{tool_name}({hint}) -> {first_line}"
        self.task_log.append(entry)
        if len(self.task_log) > 30:
            self.task_log = self.task_log[-30:]
        db.save_task_log(self.session_id, self.task_log)
        _log.debug(f"task_log: {entry}")
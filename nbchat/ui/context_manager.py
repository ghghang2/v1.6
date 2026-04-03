"""Context management mixin for ChatUI.

Five mechanisms keep messages within the model's context limit and preserve
awareness across ultra-long agentic loops:

  1. Token-budget sliding window — walk backward through history accumulating
                           token estimates until CTX_SIZE * headroom is
                           reached.  No row or turn caps: the budget alone
                           governs what fits.
  2. L1 Core Memory      — typed persistent slots (goal, constraints, active
                           entities, error history, last user correction)
                           injected as a dedicated system block on every call.
  3. L2 Episodic store   — append-only SQLite log of tool exchanges, tagged
                           with entity refs and importance scores.  Relevant
                           entries are retrieved and injected before the window.
  4. Prior context       — turns that slid off are summarized per-turn by an
                           LLM using a structured GOAL/ENTITIES/RATIONALE
                           format and injected as a system block.  Summaries
                           are computed asynchronously so they never block the
                           next API call.
  5. Importance-scored hard trim — exchanges are scored before eviction;
                           those above the adaptive write threshold are
                           persisted to the L2 episodic store before being
                           dropped from the hot context.

Adaptive thresholds:
  ImportanceTracker maintains a rolling sorted window of observed importance
  scores per session and derives L2 write / retrieval thresholds as
  percentiles of that distribution.  This removes sensitivity to absolute
  score calibration and adapts to the session's actual signal distribution.

Eliminated manual knobs (now derived):
  WINDOW_TURNS, MAX_WINDOW_ROWS, MAX_EXCHANGES, KEEP_RECENT_EXCHANGES,
  L2_WRITE_THRESHOLD, L2_MIN_IMPORTANCE_FOR_RETRIEVAL.

Retained knobs (have clear semantic meaning):
  CTX_SIZE, CONTEXT_HEADROOM, PERSIST_FRACTION, L2_RETRIEVAL_LIMIT,
  SUMMARIZER_TOOL_CHARS, CORE_MEMORY_* limits.

Row shape (canonical 6-tuple, used throughout):
    (role: str, content: str, tool_id: str, tool_name: str, tool_args: str, error_flag: int)
"""
from __future__ import annotations

import bisect
import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

from nbchat.core.utils import lazy_import
from nbchat.core import config

_log = logging.getLogger("nbchat.compaction")

# Canonical history row type — must match db.load_history column order.
_Row = Tuple[str, str, str, str, str, int]

# ── Retained tuning knobs ─────────────────────────────────────────────────────
# Max episodic entries injected per API call.
L2_RETRIEVAL_LIMIT = config.L2_RETRIEVAL_LIMIT
# How many active entities to keep in L1 core memory.
CORE_MEMORY_ACTIVE_ENTITIES_LIMIT = config.CORE_MEMORY_ACTIVE_ENTITIES_LIMIT
# How many recent error strings to keep in L1.
CORE_MEMORY_ERROR_HISTORY_LIMIT = config.CORE_MEMORY_ERROR_HISTORY_LIMIT
# Chars of tool output passed to the summariser.
_SUMMARIZER_TOOL_CHARS = config.SUMMARIZER_TOOL_CHARS
# Token reserve for prefix blocks (L1 + L2 + prior context).  Static estimate;
# errs on the side of leaving more room for prefix injection.
_PREFIX_TOKEN_RESERVE = getattr(config, "PREFIX_TOKEN_RESERVE", 2000)

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

# ── Module-level async executor ───────────────────────────────────────────────
# Shared across all ChatUI instances; daemon threads die with the process.
_summarizer_executor = ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="nbchat-summarizer"
)


# ── Adaptive importance tracker ───────────────────────────────────────────────

class ImportanceTracker:
    """Per-session rolling percentile tracker for importance scores.

    Derives L2 write and retrieval thresholds from the observed distribution
    of importance scores in this session, removing sensitivity to absolute
    score calibration.

    Pure-Python implementation: uses bisect.insort for O(log n) insertion
    into a sorted list, giving O(1) quantile reads by index.

    Parameters
    ----------
    persist_fraction:
        Top fraction of exchanges (by importance) to persist to L2.
        0.40 means the top 40% of observed scores trigger an L2 write.
    window:
        Rolling window size.  Older scores are discarded (FIFO by insertion).
    """
    _COLD_WRITE = 2.5       # used until enough data is collected
    _COLD_RETRIEVAL = 3.0
    _COLD_MIN = 10          # minimum observations before adapting

    def __init__(self, persist_fraction: float = 0.40, window: int = 200):
        self._sorted: List[float] = []   # sorted ascending
        self._fifo: List[float] = []     # insertion order for eviction
        self._maxlen = window
        self._persist_fraction = persist_fraction

    def record(self, score: float) -> None:
        """Record a new importance score, evicting the oldest if at capacity."""
        if len(self._fifo) >= self._maxlen:
            oldest = self._fifo.pop(0)
            idx = bisect.bisect_left(self._sorted, oldest)
            if idx < len(self._sorted) and self._sorted[idx] == oldest:
                self._sorted.pop(idx)
        bisect.insort(self._sorted, score)
        self._fifo.append(score)

    def _quantile(self, q: float) -> float:
        n = len(self._sorted)
        if n == 0:
            return self._COLD_WRITE
        idx = max(0, min(n - 1, int(q * n)))
        return self._sorted[idx]

    @property
    def write_threshold(self) -> float:
        """Score at the (1 - persist_fraction) quantile — adaptive L2 gate.

        Floored at _COLD_WRITE so plain tool calls (base score 2.0) never
        flood L2 when the session is dominated by low-importance exchanges.
        The floor activates once enough data is collected (>= _COLD_MIN).
        """
        if len(self._sorted) < self._COLD_MIN:
            return self._COLD_WRITE
        return max(self._COLD_WRITE, self._quantile(1.0 - self._persist_fraction))

    @property
    def retrieval_threshold(self) -> float:
        """Score at the 70th percentile — adaptive L2 retrieval floor."""
        if len(self._sorted) < self._COLD_MIN:
            return self._COLD_RETRIEVAL
        return self._quantile(0.70)

    def state_dict(self) -> dict:
        """Snapshot for observability logging."""
        return {
            "n": len(self._sorted),
            "write_threshold": round(self.write_threshold, 2),
            "retrieval_threshold": round(self.retrieval_threshold, 2),
            "min": round(self._sorted[0], 2) if self._sorted else None,
            "max": round(self._sorted[-1], 2) if self._sorted else None,
        }


# ── Module-level helpers ──────────────────────────────────────────────────────

def _est_tokens(row: _Row) -> int:
    """Estimate token count for one history row without a tokenizer.

    Calibrated divisors (chars per token):
      tool output  — mixed JSON/text/code:  2.5
      prose/user   — natural language:      4.0
      other        — assistant/system:      4.0

    These are conservative (slightly over-estimate) to leave headroom.
    Accuracy is within ~20% of tiktoken on representative chat data.
    """
    role, content, _, _, tool_args, _ = row
    chars = len(content or "") + len(tool_args or "")
    divisor = 2.5 if role == "tool" else 4.0
    return max(1, int(chars / divisor))


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
    for m in re.finditer(
        r'\b[\w\-./]+\.(?:py|js|ts|jsx|tsx|json|yaml|yml|txt|md|html|'
        r'css|sh|env|cfg|ini|toml|sql|csv|lock|log)\b',
        text,
    ):
        entities.append(m.group())
    for m in re.finditer(r'(?<!\w)/[a-z][a-z0-9_/\-]{2,40}', text):
        entities.append("api:" + m.group()[:50])
    for m in re.finditer(r'https?://([^/\s"\']{4,60})', text):
        entities.append("url:" + m.group(1))
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
      self.session_id, self._turn_summary_cache, self._summary_futures,
      self._importance_tracker
    """

    # ── Observability ─────────────────────────────────────────────────────────

    def _log_context_event(self, event_type: str, payload: dict) -> None:
        """Append one structured event to the context_events log."""
        try:
            db = lazy_import("nbchat.core.db")
            db.log_context_event(self.session_id, event_type, payload)
        except Exception as exc:
            _log.debug(f"_log_context_event({event_type}) failed: {exc}")

    # ── Importance scoring ────────────────────────────────────────────────────

    @staticmethod
    def _importance_score(exchange_msgs: list, raw_result: str = "") -> float:
        """Score a tool exchange (list of message dicts) from 0.0–10.0.

        Parameters
        ----------
        exchange_msgs:
            API-format message dicts for the exchange (assistant call + tool
            result(s)).  May contain compressed content.
        raw_result:
            The uncompressed tool output string.  Used to detect error signals
            before compression may have stripped them.  Pass "" when not
            available (e.g. during hard-trim where only API dicts are present).
        """
        score = 1.0

        raw_lower = raw_result.lower()
        if any(k in raw_lower for k in ("error", "exception", "failed", "cannot", "traceback")):
            score += 3.0

        has_tool_result = False
        for msg in exchange_msgs:
            content = (msg.get("content") or "").lower()
            role = msg.get("role", "")

            if role == "tool":
                has_tool_result = True
                if any(k in content for k in ("error", "exception", "failed", "cannot", "traceback")):
                    score += 1.5
                if any(k in content for k in ("success", "completed", "done", "created", "written")):
                    score += 1.5
                if len(content) > 500:
                    score += 0.5

            if role == "user" and any(
                k in content for k in ("correct", "wrong", "actually", "instead", "don't")
            ):
                score += 2.5

        if has_tool_result:
            score += 1.0

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
            # Check startswith, interior, and end-of-string positions.
            if any(
                lower.startswith(kw)
                or f" {kw} " in lower
                or lower.endswith(f" {kw}")
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

            if active_entities:
                matched = db.query_episodic_by_entities(
                    self.session_id, active_entities, limit=L2_RETRIEVAL_LIMIT
                )
                for e in matched:
                    seen_ids.add(e["id"])
                    entries.append(e)

            if len(entries) < L2_RETRIEVAL_LIMIT:
                remaining = L2_RETRIEVAL_LIMIT - len(entries)
                top = db.query_episodic_top_importance(
                    self.session_id,
                    min_score=self._importance_tracker.retrieval_threshold,
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
        """Persist a tool exchange to L2 if it meets the adaptive threshold."""
        # Always record score so threshold adapts even for non-persisted events.
        self._importance_tracker.record(importance)
        threshold = self._importance_tracker.write_threshold

        self._log_context_event("L2_CANDIDATE", {
            "tool": tool_name,
            "importance": round(importance, 2),
            "threshold": round(threshold, 2),
            "persisted": importance >= threshold,
            "tracker": self._importance_tracker.state_dict(),
        })

        if importance < threshold:
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

    # ── Token-budget sliding window ───────────────────────────────────────────

    def _window(self) -> Tuple[List[_Row], int]:
        """Return (window_rows, effective_cut).

        window_rows: prefix context rows + token-budget-bounded history slice,
            all as canonical 6-tuples, ready for build_messages.
        effective_cut: number of self.history rows excluded from the window.
            Used by _render_history for the "N earlier messages omitted" notice
            and by _build_prior_context to know exactly which rows to summarize.

        Token-budget walkback replaces the former WINDOW_TURNS / MAX_WINDOW_ROWS
        knobs.  Analysis rows (display-only reasoning traces) are excluded from
        budget accounting but included in the returned window.

        Prefix blocks injected before the window (in order):
          1. L1 Core Memory block  (always, if non-empty)
          2. L2 Episodic context   (conditional on active entities / importance)
          3. Structured prior context summaries (if turns slid off)
        """
        budget = (
            int(config.CTX_SIZE * getattr(config, "CONTEXT_HEADROOM", 0.82))
            - _PREFIX_TOKEN_RESERVE
        )

        # ── Token-budget walkback ────────────────────────────────────────────
        tokens = 0
        cut = 0
        for i in range(len(self.history) - 1, -1, -1):
            row = self.history[i]
            if row[0] == "analysis":
                continue  # display-only; excluded from budget
            row_tokens = _est_tokens(row)
            if tokens + row_tokens > budget:
                # Advance forward to the nearest user-turn boundary so we
                # never orphan the tail of an exchange.
                j = i + 1
                while j < len(self.history) and self.history[j][0] != "user":
                    j += 1
                cut = j
                break
            tokens += row_tokens

        # Safety: always keep at least the most recent user turn.
        last_user = next(
            (i for i in range(len(self.history) - 1, -1, -1)
             if self.history[i][0] == "user"),
            0,
        )
        cut = min(cut, last_user)

        window = list(self.history[cut:])
        effective_cut = cut

        # ── Build context prefix ─────────────────────────────────────────────
        prefix: List[_Row] = []

        l1_block = self._get_l1_block()
        if l1_block:
            prefix.append(("system", l1_block, "", "", "", 0))

        try:
            db = lazy_import("nbchat.core.db")
            cm = db.get_core_memory(self.session_id) or {}
            active_entities = json.loads(cm.get("active_entities", "[]"))
        except Exception:
            active_entities = []
        l2_block = self._get_l2_block(active_entities)
        if l2_block:
            prefix.append(("system", l2_block, "", "", "", 0))

        if effective_cut > 0:
            prior = self._build_prior_context(self.history[:effective_cut])
            if prior:
                prefix.append(("system", prior, "", "", "", 0))

        # ── Prefetch summaries for evicted turns (non-blocking) ───────────────
        if effective_cut > 0:
            self._prefetch_summaries(self.history[:effective_cut])

        # ── Observability ─────────────────────────────────────────────────────
        self._log_context_event("WINDOW_COMPUTED", {
            "history_len": len(self.history),
            "effective_cut": effective_cut,
            "window_rows": len(window),
            "estimated_tokens": tokens,
            "budget": budget,
            "prefix_blocks": len(prefix),
            "tracker": self._importance_tracker.state_dict(),
        })

        return prefix + window, effective_cut

    # ── Per-turn structured summarisation ────────────────────────────────────

    def _prefetch_summaries(self, prior_rows: List[_Row]) -> None:
        """Submit async summarization futures for evicted turns not yet cached."""
        units = _group_by_user_turn(prior_rows)
        for unit in units:
            key = hashlib.sha1(
                "".join(r[1] + r[4] for r in unit).encode()
            ).hexdigest()
            if key not in self._turn_summary_cache and key not in self._summary_futures:
                future = _summarizer_executor.submit(self._call_summarizer, unit)
                self._summary_futures[key] = future
                _log.debug(f"prefetch_summaries: submitted {key[:8]}")

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
            if not any([parsed["goal"], parsed["entities"], parsed["rationale"]]):
                line += f"\n  {raw_summary}"
            lines.append(line)

        return (
            "[PRIOR SESSION CONTEXT — earlier turns summarized]\n"
            + "\n".join(lines)
            + "\n[END PRIOR CONTEXT]"
        )

    def _get_turn_summary(self, unit: List[_Row]) -> str:
        """Return summary for *unit*, using async future if available.

        Priority:
          1. In-memory cache (already computed)
          2. Completed future → promote to cache
          3. Pending future → return fallback (will promote on next window call)
          4. Not submitted → submit now, return fallback
        """
        key = hashlib.sha1(
            "".join(r[1] + r[4] for r in unit).encode()
        ).hexdigest()

        if key in self._turn_summary_cache:
            return self._turn_summary_cache[key]

        future = self._summary_futures.get(key)
        if future is not None:
            if future.done():
                try:
                    summary = future.result()
                except Exception as exc:
                    _log.debug(f"summary future {key[:8]} failed: {exc}")
                    summary = self._fallback_summary(unit)
                self._turn_summary_cache[key] = summary
                del self._summary_futures[key]
                self._persist_summary_cache()
                self._log_context_event("SUMMARY_GENERATED", {
                    "key": key[:8],
                    "length": len(summary),
                    "source": "async_future",
                })
                return summary
            # Still running — fallback this turn, will promote next time
            return self._fallback_summary(unit)

        # Not submitted yet — submit and return fallback for this turn
        self._summary_futures[key] = _summarizer_executor.submit(
            self._call_summarizer, unit
        )
        return self._fallback_summary(unit)

    def _fallback_summary(self, unit: List[_Row]) -> str:
        """Minimal summary used while async summarizer is pending."""
        user_text = next((r[1][:100] for r in unit if r[0] == "user"), "")
        tool_hint = next(
            (r[1].split("\n")[0][:80] for r in unit if r[0] == "tool"), ""
        )
        return (
            f"GOAL: (summary pending) {user_text}\n"
            f"ENTITIES: none\n"
            f"RATIONALE: {tool_hint}"
        )

    def _persist_summary_cache(self) -> None:
        try:
            db = lazy_import("nbchat.core.db")
            db.save_turn_summaries(self.session_id, self._turn_summary_cache)
        except Exception:
            pass

    def _call_summarizer(self, unit: List[_Row]) -> str:
        """Call the model to produce a structured GOAL/ENTITIES/RATIONALE summary.

        Runs in a thread-pool worker; must be thread-safe (no widget access).
        """
        from nbchat.core import client as _client_mod
        from nbchat.ui.chat_builder import build_messages

        trimmed: List[_Row] = [
            (
                role,
                content[:_SUMMARIZER_TOOL_CHARS] if role == "tool" else content,
                tid, tname, targs, ef,
            )
            for role, content, tid, tname, targs, ef in unit
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
                max_tokens=512,
            )
            summary = resp.choices[0].message.content.strip()
            _log.debug(f"turn summary ({len(summary)} chars): {summary[:80]}...")
            return summary
        except Exception as exc:
            _log.debug(f"summarizer failed: {exc} — using fallback")
            return self._fallback_summary(unit)

    # ── Importance-scored hard trim ───────────────────────────────────────────

    def _hard_trim(self, messages: list) -> None:
        """Drop least-important tool-exchange pairs until messages fit the budget.

        Before evicting an exchange whose importance score meets the adaptive
        write threshold, the exchange is persisted to the L2 episodic store.

        messages[0] = system prompt.
        messages[1] = first context/user row (protected).
        Exchange scan starts at index 2.
        """
        limit = int(
            config.CTX_SIZE
            * getattr(config, "CONTEXT_HEADROOM", 0.82)
            * 0.85   # additional safety margin inside hard trim
        )
        KEEP_RECENT = getattr(config, "KEEP_RECENT_EXCHANGES", 5)

        def est(msg: dict) -> int:
            content = msg.get("content") or ""
            tcs = msg.get("tool_calls") or []
            tc_text = "".join(
                tc.get("function", {}).get("arguments", "") for tc in tcs
            )
            # Use same calibrated divisor as _est_tokens
            chars = len(content) + len(tc_text)
            return max(1, int(chars / 2.5))

        def total() -> int:
            return sum(est(m) for m in messages)

        def get_exchanges() -> List[Tuple[int, int]]:
            result = []
            i = 2
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

            # Record score in tracker so threshold evolves even during trim.
            self._importance_tracker.record(score)
            threshold = self._importance_tracker.write_threshold

            persisted = False
            if score >= threshold:
                action_name = ""
                tc_list = messages[s].get("tool_calls") or []
                if tc_list:
                    action_name = tc_list[0].get("function", {}).get("name", "")
                tc_args = ""
                if tc_list:
                    tc_args = tc_list[0].get("function", {}).get("arguments", "")
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
                            persisted = True
                        except Exception as exc:
                            _log.debug(f"_hard_trim L2 write failed: {exc}")

            # Append a one-line note to the (in-memory) system prompt.
            dropped = [
                messages[s + j].get("content", "")[:80]
                for j in range(1, e - s)
                if messages[s + j].get("role") == "tool"
            ]
            if dropped and messages[0].get("role") == "system":
                messages[0]["content"] += f"\n[earlier: {' | '.join(dropped)}]"

            self._log_context_event("EXCHANGE_EVICTED", {
                "score": round(score, 2),
                "threshold": round(threshold, 2),
                "persisted_to_l2": persisted,
                "msg_range": [s, e],
                "total_tokens_before": total(),
            })
            _log.debug(f"_hard_trim: drop [{s}:{e}] score={score:.1f} persisted={persisted}")
            del messages[s:e]

        # Pass 1: token-budget drops, keeping KEEP_RECENT most recent exchanges.
        while total() > limit:
            exchanges = get_exchanges()
            droppable = (
                exchanges[:-KEEP_RECENT] if len(exchanges) > KEEP_RECENT else []
            )
            if not droppable:
                break
            drop_least_important(droppable)
            _log.debug(f"_hard_trim: after budget drop total={total()}")

        # Pass 2: last resort — truncate the largest individual tool result.
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
            self._log_context_event("TOOL_OUTPUT_TRUNCATED", {
                "msg_index": largest,
                "original_len": len(original),
                "truncated_to": 200,
            })
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
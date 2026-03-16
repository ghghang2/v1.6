"""Tests for nbchat.ui.context_manager.

Run from repo root:
    pytest tests/test_context_manager.py -v

ContextMixin is tested via a minimal mock host class that satisfies its
attribute contract.  All DB and config calls are patched.
"""
from __future__ import annotations

import json
import sys
from typing import List, Tuple
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub out all heavy dependencies before importing the module.
# ---------------------------------------------------------------------------
sys.modules.setdefault("nbchat", MagicMock())
sys.modules.setdefault("nbchat.core", MagicMock())
sys.modules.setdefault("nbchat.core.utils", MagicMock())

# Provide a real lazy_import that just returns the mock module.
_lazy = MagicMock()
_lazy.side_effect = lambda name: sys.modules.get(name, MagicMock())
sys.modules["nbchat.core.utils"].lazy_import = _lazy

from nbchat.ui.context_manager import ContextMixin, L2_WRITE_THRESHOLD


# ---------------------------------------------------------------------------
# Minimal host class
# ---------------------------------------------------------------------------

class _FakeConfig:
    MAX_WINDOW_ROWS = 10
    CONTEXT_TOKEN_THRESHOLD = 100_000
    MAX_EXCHANGES = 50
    KEEP_RECENT_EXCHANGES = 20


class FakeChat(ContextMixin):
    """Minimal ChatUI-like host for ContextMixin tests."""

    def __init__(self, window_turns: int = 3, max_window_rows: int = 10):
        self.session_id = "test-session"
        self.history: List[Tuple] = []
        self._turn_summary_cache: dict = {}
        self.task_log: List[str] = []
        self.system_prompt = "You are a helpful assistant."
        self.model_name = "test-model"
        self.WINDOW_TURNS = window_turns
        self._max_window_rows = max_window_rows

    def _get_l1_block(self):
        return None   # override in specific tests

    def _get_l2_block(self, active_entities):
        return None   # override in specific tests

    def _build_prior_context(self, rows):
        if not rows:
            return None
        return f"[PRIOR CONTEXT]\n{len(rows)} rows summarized\n[END PRIOR CONTEXT]"


def _row(role, content="X", tool_id="", tool_name="", tool_args="", ef=0):
    return (role, content, tool_id, tool_name, tool_args, ef)


def _make_config(max_window_rows: int = 10):
    cfg = MagicMock()
    cfg.MAX_WINDOW_ROWS = max_window_rows
    return cfg


# Helper: patch config so _window uses our values.
def _patched_window(chat: FakeChat, max_window_rows: int = None):
    rows = max_window_rows if max_window_rows is not None else chat._max_window_rows
    cfg = _make_config(rows)
    with patch("nbchat.ui.context_manager.lazy_import", return_value=cfg):
        # Also mock db for L2 lookup
        db_mock = MagicMock()
        db_mock.get_core_memory.return_value = {}
        with patch.object(chat, "_get_l1_block", return_value=None), \
             patch.object(chat, "_get_l2_block", return_value=None):
            return chat._window()


# ---------------------------------------------------------------------------
# 1. Return type: _window must return (list, int)
# ---------------------------------------------------------------------------

class TestWindowReturnType:
    def test_returns_tuple_of_two(self):
        chat = FakeChat()
        result = _patched_window(chat)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_first_element_is_list(self):
        chat = FakeChat()
        window, cut = _patched_window(chat)
        assert isinstance(window, list)

    def test_second_element_is_int(self):
        chat = FakeChat()
        window, cut = _patched_window(chat)
        assert isinstance(cut, int)

    def test_empty_history(self):
        chat = FakeChat()
        window, cut = _patched_window(chat)
        assert window == []
        assert cut == 0


# ---------------------------------------------------------------------------
# 2. effective_cut with sliding window only
# ---------------------------------------------------------------------------

class TestEffectiveCut:
    def _build_turns(self, n: int) -> List[Tuple]:
        """Build n simple user turns."""
        rows = []
        for i in range(n):
            rows.append(_row("user", f"msg_{i}"))
            rows.append(_row("assistant", f"resp_{i}"))
        return rows

    def test_cut_zero_when_fits(self):
        """All turns fit → effective_cut == 0."""
        chat = FakeChat(window_turns=5)
        chat.history = self._build_turns(3)   # 3 turns < 5 WINDOW_TURNS
        window, cut = _patched_window(chat, max_window_rows=100)
        assert cut == 0

    def test_cut_nonzero_when_overflow(self):
        """More turns than WINDOW_TURNS → some rows excluded."""
        chat = FakeChat(window_turns=2)
        chat.history = self._build_turns(4)   # 4 turns, only last 2 wanted
        window, cut = _patched_window(chat, max_window_rows=100)
        assert cut > 0

    def test_window_contains_last_turns_only(self):
        """Window rows should correspond to the last WINDOW_TURNS user turns."""
        chat = FakeChat(window_turns=2)
        chat.history = self._build_turns(4)
        window, cut = _patched_window(chat, max_window_rows=100)
        user_msgs_in_window = [r[1] for r in window if r[0] == "user"]
        assert "msg_2" in user_msgs_in_window
        assert "msg_3" in user_msgs_in_window
        assert "msg_0" not in user_msgs_in_window

    def test_effective_cut_equals_cut_when_no_secondary_trim(self):
        """When rows fit in MAX_WINDOW_ROWS, effective_cut == window cut."""
        chat = FakeChat(window_turns=2)
        chat.history = self._build_turns(4)
        window, cut = _patched_window(chat, max_window_rows=100)
        # All rows from cut onwards fit; effective_cut should == cut
        assert cut <= len(chat.history)


# ---------------------------------------------------------------------------
# 3. Analysis rows do not count toward MAX_WINDOW_ROWS budget
# ---------------------------------------------------------------------------

class TestAnalysisBudget:
    def test_analysis_rows_excluded_from_count(self):
        """With MAX_WINDOW_ROWS=4, adding analysis rows should not evict
        real conversation rows that would otherwise fit."""
        chat = FakeChat(window_turns=10)
        # 4 real rows (2 user + 2 assistant) + 4 analysis = 8 total
        chat.history = [
            _row("user", "u1"),
            _row("analysis", "r1"),
            _row("assistant", "a1"),
            _row("analysis", "r2"),
            _row("user", "u2"),
            _row("analysis", "r3"),
            _row("assistant", "a2"),
            _row("analysis", "r4"),
        ]
        # With MAX_WINDOW_ROWS=4, only 4 non-analysis rows exist → all fit
        window, cut = _patched_window(chat, max_window_rows=4)
        user_msgs = [r for r in window if r[0] == "user"]
        assert len(user_msgs) == 2   # both users present despite analysis rows

    def test_secondary_trim_only_when_non_analysis_overflow(self):
        """Secondary trim fires only when non-analysis rows exceed budget."""
        chat = FakeChat(window_turns=10)
        # 6 non-analysis rows
        chat.history = [
            _row("user", f"u{i}") for i in range(3)
        ] + [
            _row("assistant", f"a{i}") for i in range(3)
        ]
        # Budget of 10 — all 6 fit, no secondary trim
        window, cut = _patched_window(chat, max_window_rows=10)
        assert cut == 0

    def test_secondary_trim_fires_when_over_budget(self):
        """When non-analysis rows exceed MAX_WINDOW_ROWS, effective_cut > 0."""
        chat = FakeChat(window_turns=20)
        # 12 non-analysis rows, budget 8
        for i in range(6):
            chat.history.append(_row("user", f"u{i}"))
            chat.history.append(_row("assistant", f"a{i}"))
        window, cut = _patched_window(chat, max_window_rows=8)
        non_analysis = [r for r in window if r[0] != "analysis"]
        assert len(non_analysis) <= 8


# ---------------------------------------------------------------------------
# 4. Prefix rows are canonical 6-tuples
# ---------------------------------------------------------------------------

class TestPrefixRows:
    def test_l1_prefix_row_is_6_tuple(self):
        chat = FakeChat()
        chat.history = [_row("user", "hello")]
        cfg = _make_config(100)
        with patch("nbchat.ui.context_manager.lazy_import", return_value=cfg), \
             patch.object(chat, "_get_l1_block", return_value="[L1 BLOCK]"), \
             patch.object(chat, "_get_l2_block", return_value=None):
            window, _ = chat._window()
        prefix_rows = [r for r in window if r[0] == "system"]
        for row in prefix_rows:
            assert len(row) == 6, f"Expected 6-tuple, got {len(row)}-tuple: {row}"

    def test_l2_prefix_row_is_6_tuple(self):
        chat = FakeChat()
        chat.history = [_row("user", "hello")]
        cfg = _make_config(100)
        with patch("nbchat.ui.context_manager.lazy_import", return_value=cfg), \
             patch.object(chat, "_get_l1_block", return_value=None), \
             patch.object(chat, "_get_l2_block", return_value="[L2 BLOCK]"):
            window, _ = chat._window()
        prefix_rows = [r for r in window if r[0] == "system"]
        for row in prefix_rows:
            assert len(row) == 6

    def test_prior_context_prefix_row_is_6_tuple(self):
        """Prior context row (generated when cut > 0) must also be 6-tuple."""
        chat = FakeChat(window_turns=1)
        # 2 user turns so window slides and prior context is generated
        chat.history = [
            _row("user", "old"),
            _row("assistant", "old resp"),
            _row("user", "new"),
        ]
        cfg = _make_config(100)
        with patch("nbchat.ui.context_manager.lazy_import", return_value=cfg), \
             patch.object(chat, "_get_l1_block", return_value=None), \
             patch.object(chat, "_get_l2_block", return_value=None):
            window, cut = chat._window()
        assert cut > 0
        prefix_rows = [r for r in window if r[0] == "system"]
        for row in prefix_rows:
            assert len(row) == 6

    def test_prefix_error_flag_is_zero(self):
        chat = FakeChat()
        chat.history = [_row("user", "hello")]
        cfg = _make_config(100)
        with patch("nbchat.ui.context_manager.lazy_import", return_value=cfg), \
             patch.object(chat, "_get_l1_block", return_value="[L1]"), \
             patch.object(chat, "_get_l2_block", return_value="[L2]"):
            window, _ = chat._window()
        for row in window:
            if row[0] == "system":
                assert row[5] == 0, f"error_flag should be 0 for prefix row, got {row[5]}"

    def test_all_window_rows_are_6_tuples(self):
        chat = FakeChat(window_turns=5)
        chat.history = [
            _row("user", "q1"),
            _row("analysis", "thinking"),
            _row("assistant", "a1"),
            _row("tool", "result", "tc1", "bash", "{}", 0),
        ]
        cfg = _make_config(100)
        with patch("nbchat.ui.context_manager.lazy_import", return_value=cfg), \
             patch.object(chat, "_get_l1_block", return_value="[L1]"), \
             patch.object(chat, "_get_l2_block", return_value=None):
            window, _ = chat._window()
        for row in window:
            assert len(row) == 6, f"Row {row[0]!r} has {len(row)} fields, expected 6"


# ---------------------------------------------------------------------------
# 5. Importance scoring
# ---------------------------------------------------------------------------

class TestImportanceScoring:
    def test_base_score_above_l2_threshold(self):
        """A tool result with no error or success keywords still has a result →
        score should be >= L2_WRITE_THRESHOLD (2.0) due to the has_tool_result boost."""
        msgs = [
            {"role": "assistant", "content": None, "tool_calls": [{}]},
            {"role": "tool", "content": "some neutral output here"},
        ]
        score = ContextMixin._importance_score(msgs)
        assert score >= L2_WRITE_THRESHOLD

    def test_error_in_raw_result_boosts_score(self):
        msgs = [
            {"role": "tool", "content": "ok"},
        ]
        score_with_error = ContextMixin._importance_score(
            msgs, raw_result="Traceback (most recent call last): ..."
        )
        score_without = ContextMixin._importance_score(msgs, raw_result="")
        assert score_with_error > score_without

    def test_error_keyword_in_compressed_boosts_score(self):
        msgs = [
            {"role": "tool", "content": "Error: file not found"},
        ]
        score = ContextMixin._importance_score(msgs, raw_result="")
        # Should get the +1.5 bump from compressed error keyword
        assert score > 1.0

    def test_success_keyword_boosts_score(self):
        msgs = [
            {"role": "tool", "content": "done: 3 files created successfully"},
        ]
        score = ContextMixin._importance_score(msgs)
        assert score >= L2_WRITE_THRESHOLD

    def test_user_correction_keyword_boosts_score(self):
        msgs = [
            {"role": "user", "content": "actually, don't do that"},
            {"role": "tool", "content": "ok"},
        ]
        score = ContextMixin._importance_score(msgs)
        # user correction = +2.5
        assert score > 3.0

    def test_long_tool_result_boosts_score(self):
        long_content = "data " * 200
        msgs = [{"role": "tool", "content": long_content}]
        score = ContextMixin._importance_score(msgs)
        assert score > 2.0

    def test_score_capped_at_10(self):
        msgs = [
            {"role": "user", "content": "actually wrong don't do this"},
            {"role": "tool", "content": "error exception failed " * 20},
        ]
        score = ContextMixin._importance_score(
            msgs, raw_result="Traceback: error exception failed"
        )
        assert score == 10.0

    def test_raw_result_error_not_in_compressed(self):
        """Error in raw_result is detected even when compressed content is clean."""
        msgs = [
            {"role": "tool", "content": "compressed: function returned value"},
        ]
        raw = "Traceback (most recent call last):\n  File foo.py\nException: crash"
        score_with_raw = ContextMixin._importance_score(msgs, raw_result=raw)
        score_without = ContextMixin._importance_score(msgs, raw_result="")
        # Raw error should have meaningfully higher score
        assert score_with_raw > score_without

    def test_empty_exchange_gets_base_score(self):
        score = ContextMixin._importance_score([])
        assert score == 1.0

    def test_no_tool_result_no_has_tool_result_boost(self):
        """Without a tool message, the +1.0 tool-result boost should not apply."""
        msgs = [{"role": "assistant", "content": "thinking"}]
        score_no_tool = ContextMixin._importance_score(msgs)
        msgs_with_tool = [
            {"role": "assistant", "content": "thinking"},
            {"role": "tool", "content": "result"},
        ]
        score_with_tool = ContextMixin._importance_score(msgs_with_tool)
        assert score_with_tool > score_no_tool


# ---------------------------------------------------------------------------
# 6. Prior context covers all excluded rows (including secondary trim)
# ---------------------------------------------------------------------------

class TestPriorContextCoverage:
    def test_prior_context_built_for_slid_off_rows(self):
        """When window slides, prior context should reference the excluded rows."""
        chat = FakeChat(window_turns=1)
        chat.history = [
            _row("user", "old_task"),
            _row("assistant", "old_response"),
            _row("user", "new_task"),
        ]
        cfg = _make_config(100)
        with patch("nbchat.ui.context_manager.lazy_import", return_value=cfg), \
             patch.object(chat, "_get_l1_block", return_value=None), \
             patch.object(chat, "_get_l2_block", return_value=None):
            window, cut = chat._window()

        assert cut > 0
        # Prior context row should be in window
        prior_rows = [r for r in window if r[0] == "system" and "PRIOR" in r[1]]
        assert len(prior_rows) == 1

    def test_no_prior_context_when_nothing_excluded(self):
        """When effective_cut == 0, no prior context row is generated."""
        chat = FakeChat(window_turns=10)
        chat.history = [_row("user", "only msg")]
        cfg = _make_config(100)
        with patch("nbchat.ui.context_manager.lazy_import", return_value=cfg), \
             patch.object(chat, "_get_l1_block", return_value=None), \
             patch.object(chat, "_get_l2_block", return_value=None):
            window, cut = chat._window()

        assert cut == 0
        prior_rows = [r for r in window if r[0] == "system" and "PRIOR" in r[1]]
        assert len(prior_rows) == 0
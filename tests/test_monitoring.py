"""Tests for nbchat.core.monitoring.

Run from repo root:
    pytest tests/test_monitoring.py -v

All file I/O is mocked or uses tmp_path.  No real llama.cpp server needed.
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Stub heavy dependencies ────────────────────────────────────────────────

from nbchat.core.monitoring import (
    SessionMonitor,
    get_session_monitor,
    flush_session_monitor,
    parse_last_completion_metrics,
    merge_into_global,
    get_global_report,
    suggest_config,
    format_report,
    _empty_global,
    _LOW_SIM_THRESHOLD,
    _HIGH_INVALIDATION_THRESHOLD,
    _REREAD_RATE_THRESHOLD,
    _ERROR_COMPRESSION_THRESHOLD,
    _LLM_FAILURE_THRESHOLD,
    _POOR_RATIO_THRESHOLD,
    _NO_OUTPUT_THRESHOLD,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_log(tmp_path: Path, completion_block: str) -> Path:
    """Write a fake llama.cpp log containing one completion block."""
    log = tmp_path / "llama_server.log"
    log.write_text(completion_block)
    return log


# Realistic log block for a cache-hit turn (task 142 from the real log).
_CACHE_HIT_BLOCK = """\
srv  update_slots: all slots are idle
srv  params_from_: Chat format: peg-constructed
slot get_availabl: id  0 | task -1 | selected slot by LCP similarity, sim_best = 0.984 (> 0.100 thold), f_keep = 1.000
slot launch_slot_: id  0 | task 142 | processing task, is_child = 0
slot update_slots: id  0 | task 142 | new prompt, n_ctx_slot = 65536, n_keep = 0, task.n_tokens = 2039
slot update_slots: id  0 | task 142 | n_tokens = 2007, memory_seq_rm [2007, end)
slot init_sampler: id  0 | task 142 | init sampler, took 0.42 ms, tokens: text = 2039, total = 2039
slot update_slots: id  0 | task 142 | created context checkpoint 2 of 8 (pos_min = 2006, pos_max = 2006, n_tokens = 2007, size = 50.251 MiB)
slot update_slots: id  0 | task 142 | prompt processing done, n_tokens = 2039, batch.n_tokens = 32
slot print_timing: id  0 | task 142 |
prompt eval time =     136.22 ms /    32 tokens (    4.26 ms per token,   234.92 tokens per second)
"""

# Log block for a cache-bust turn (task 429 from the real log).
_CACHE_BUST_BLOCK = """\
srv  update_slots: all slots are idle
slot get_availabl: id  0 | task -1 | selected slot by LCP similarity, sim_best = 0.653 (> 0.100 thold), f_keep = 0.711
slot launch_slot_: id  0 | task 429 | processing task, is_child = 0
slot update_slots: id  0 | task 429 | new prompt, n_ctx_slot = 65536, n_keep = 0, task.n_tokens = 2760
slot update_slots: id  0 | task 429 | restored context checkpoint (pos_min = 1357, pos_max = 1357, n_tokens = 1358, size = 50.251 MiB)
slot update_slots: id  0 | task 429 | erased invalidated context checkpoint (pos_min = 2006, pos_max = 2006, n_tokens = 2007, n_swa = 1, size = 50.251 MiB)
slot update_slots: id  0 | task 429 | erased invalidated context checkpoint (pos_min = 2110, pos_max = 2110, n_tokens = 2111, n_swa = 1, size = 50.251 MiB)
slot update_slots: id  0 | task 429 | erased invalidated context checkpoint (pos_min = 2249, pos_max = 2249, n_tokens = 2250, n_swa = 1, size = 50.251 MiB)
slot update_slots: id  0 | task 429 | n_tokens = 1358, memory_seq_rm [1358, end)
slot update_slots: id  0 | task 429 | prompt processing done, n_tokens = 2760, batch.n_tokens = 1402
slot print_timing: id  0 | task 429 |
prompt eval time =    1957.33 ms /  1402 tokens (    1.40 ms per token,   716.28 tokens per second)
"""

# First turn: no LCP line (LRU selection).
_FIRST_TURN_BLOCK = """\
slot get_availabl: id  0 | task -1 | selected slot by LRU, t_last = -1
slot update_slots: id  0 | task 0 | prompt processing done, n_tokens = 1870, batch.n_tokens = 1870
prompt eval time =    2577.56 ms /  1870 tokens (    1.38 ms per token,   725.49 tokens per second)
"""


# ── 1. Log parsing ─────────────────────────────────────────────────────────

class TestLogParsing:
    def test_absent_log_returns_invalid(self, tmp_path):
        m = parse_last_completion_metrics(tmp_path / "nonexistent.log")
        assert m.valid is False

    def test_empty_log_returns_invalid(self, tmp_path):
        log = tmp_path / "llama_server.log"
        log.write_text("")
        m = parse_last_completion_metrics(log)
        assert m.valid is False

    def test_cache_hit_sim_best(self, tmp_path):
        log = _make_log(tmp_path, _CACHE_HIT_BLOCK)
        m = parse_last_completion_metrics(log)
        assert m.valid is True
        assert abs(m.sim_best - 0.984) < 0.001

    def test_cache_hit_f_keep(self, tmp_path):
        log = _make_log(tmp_path, _CACHE_HIT_BLOCK)
        m = parse_last_completion_metrics(log)
        assert abs(m.f_keep - 1.000) < 0.001

    def test_cache_hit_new_tokens(self, tmp_path):
        log = _make_log(tmp_path, _CACHE_HIT_BLOCK)
        m = parse_last_completion_metrics(log)
        assert m.new_tokens == 32
        assert m.total_tokens == 2039

    def test_cache_hit_rate(self, tmp_path):
        log = _make_log(tmp_path, _CACHE_HIT_BLOCK)
        m = parse_last_completion_metrics(log)
        expected = (2039 - 32) / 2039
        assert abs(m.cache_hit_rate - expected) < 0.001

    def test_cache_hit_no_invalidations(self, tmp_path):
        log = _make_log(tmp_path, _CACHE_HIT_BLOCK)
        m = parse_last_completion_metrics(log)
        assert m.checkpoints_erased == 0
        assert m.checkpoint_restored is False

    def test_cache_hit_prompt_ms_per_token(self, tmp_path):
        log = _make_log(tmp_path, _CACHE_HIT_BLOCK)
        m = parse_last_completion_metrics(log)
        assert abs(m.prompt_ms_per_token - 4.26) < 0.01

    def test_cache_bust_sim_best(self, tmp_path):
        log = _make_log(tmp_path, _CACHE_BUST_BLOCK)
        m = parse_last_completion_metrics(log)
        assert abs(m.sim_best - 0.653) < 0.001

    def test_cache_bust_checkpoints_erased(self, tmp_path):
        log = _make_log(tmp_path, _CACHE_BUST_BLOCK)
        m = parse_last_completion_metrics(log)
        assert m.checkpoints_erased == 3

    def test_cache_bust_checkpoint_restored(self, tmp_path):
        log = _make_log(tmp_path, _CACHE_BUST_BLOCK)
        m = parse_last_completion_metrics(log)
        assert m.checkpoint_restored is True

    def test_cache_bust_new_tokens(self, tmp_path):
        log = _make_log(tmp_path, _CACHE_BUST_BLOCK)
        m = parse_last_completion_metrics(log)
        assert m.new_tokens == 1402

    def test_first_turn_no_sim(self, tmp_path):
        log = _make_log(tmp_path, _FIRST_TURN_BLOCK)
        m = parse_last_completion_metrics(log)
        assert m.sim_best == 0.0   # no LCP line
        assert m.total_tokens == 1870
        assert m.new_tokens == 1870
        assert m.cache_hit_rate == 0.0

    def test_parses_last_completion_in_multi_block_log(self, tmp_path):
        """When log contains multiple completions, only the last is parsed."""
        content = _CACHE_HIT_BLOCK + "\n" + _CACHE_BUST_BLOCK
        log = _make_log(tmp_path, content)
        m = parse_last_completion_metrics(log)
        # Should get the BUST block (last)
        assert abs(m.sim_best - 0.653) < 0.001
        assert m.checkpoints_erased == 3


# ── 2. SessionMonitor accumulation ────────────────────────────────────────

class TestSessionMonitor:
    def _mon(self, sid="test-sess") -> SessionMonitor:
        return SessionMonitor(sid)

    def test_empty_report(self):
        m = self._mon()
        r = m.get_session_report()
        assert r["cache"]["turn_count"] == 0
        assert r["tools"] == {}
        assert r["warnings"] == []

    def test_record_llm_call_increments_turn_count(self, tmp_path):
        m = self._mon()
        with patch("nbchat.core.monitoring._LOG_PATH", tmp_path / "no.log"):
            m.record_llm_call(100)
            m.record_llm_call(110)
        r = m.get_session_report()
        assert r["cache"]["turn_count"] == 2

    def test_volatile_len_tracked(self, tmp_path):
        m = self._mon()
        with patch("nbchat.core.monitoring._LOG_PATH", tmp_path / "no.log"):
            m.record_llm_call(200)
            m.record_llm_call(220)
        r = m.get_session_report()
        assert r["cache"]["avg_volatile_len"] == 210

    def test_volatile_delta_tracked(self, tmp_path):
        m = self._mon()
        with patch("nbchat.core.monitoring._LOG_PATH", tmp_path / "no.log"):
            m.record_llm_call(0)     # first call: delta = |0 - 0| = 0
            m.record_llm_call(100)   # delta = 100
            m.record_llm_call(150)   # delta = 50
        r = m.get_session_report()
        # sum_delta = 0 + 100 + 50 = 150, avg = 150/3 = 50
        assert r["cache"]["avg_volatile_delta"] == 50

    def test_cache_metrics_from_log(self, tmp_path):
        log = _make_log(tmp_path, _CACHE_HIT_BLOCK)
        m = self._mon()
        with patch("nbchat.core.monitoring._LOG_PATH", log):
            m.record_llm_call(100)
        r = m.get_session_report()
        assert r["cache"]["avg_sim_best"] == pytest.approx(0.984, abs=0.001)

    def test_low_sim_turn_counted(self, tmp_path):
        log = _make_log(tmp_path, _CACHE_BUST_BLOCK)
        m = self._mon()
        with patch("nbchat.core.monitoring._LOG_PATH", log):
            m.record_llm_call(100)
        r = m.get_session_report()
        assert r["cache"]["low_sim_rate"] == 1.0

    def test_cache_invalidation_counted(self, tmp_path):
        log = _make_log(tmp_path, _CACHE_BUST_BLOCK)
        m = self._mon()
        with patch("nbchat.core.monitoring._LOG_PATH", log):
            m.record_llm_call(100)
        r = m.get_session_report()
        assert r["cache"]["cache_invalidation_rate"] == 1.0

    def test_record_tool_call_basic(self, tmp_path):
        m = self._mon()
        m.record_tool_call("bash", was_compressed=True, had_error=False)
        r = m.get_session_report()
        t = r["tools"]["bash"]
        assert t["calls"] == 1
        assert t["compressed_calls"] == 1

    def test_record_tool_call_uncompressed(self):
        m = self._mon()
        m.record_tool_call("bash", was_compressed=False, had_error=False)
        r = m.get_session_report()
        assert r["tools"]["bash"]["compressed_calls"] == 0

    def test_error_after_compression_tracked(self):
        m = self._mon()
        m.record_tool_call("read_file", was_compressed=True, had_error=True)
        m.record_tool_call("read_file", was_compressed=True, had_error=False)
        r = m.get_session_report()
        # 1 error out of 2 compressed = 0.5
        assert r["tools"]["read_file"]["error_after_compression_rate"] == pytest.approx(0.5)

    def test_error_not_counted_when_not_compressed(self):
        m = self._mon()
        m.record_tool_call("bash", was_compressed=False, had_error=True)
        r = m.get_session_report()
        assert r["tools"]["bash"]["error_after_compression_rate"] == 0.0

    def test_lossless_learned_strategy_counted(self):
        m = self._mon()
        m.record_tool_call("search", was_compressed=True, had_error=False,
                           strategy="lossless_learned")
        r = m.get_session_report()
        assert r["tools"]["search"]["reread_rate"] == pytest.approx(1.0)

    def test_llm_failure_strategy_counted(self):
        m = self._mon()
        m.record_tool_call("api", was_compressed=True, had_error=False,
                           strategy="headtail_llm_fallback")
        r = m.get_session_report()
        assert r["tools"]["api"]["llm_failure_rate"] == pytest.approx(1.0)

    def test_compression_ratio_tracked(self):
        m = self._mon()
        m.record_tool_call("read_file", was_compressed=True, had_error=False,
                           input_chars=1000, output_chars=400)
        r = m.get_session_report()
        assert r["tools"]["read_file"]["avg_ratio"] == pytest.approx(0.4)

    def test_no_output_recorded(self):
        m = self._mon()
        m.record_tool_call("list_dir", was_compressed=True, had_error=False)
        m.record_no_output("list_dir")
        r = m.get_session_report()
        assert r["tools"]["list_dir"]["no_output_rate"] == pytest.approx(0.5)

    def test_multiple_tools_independent(self):
        m = self._mon()
        m.record_tool_call("bash", was_compressed=True, had_error=False)
        m.record_tool_call("read_file", was_compressed=False, had_error=False)
        r = m.get_session_report()
        assert "bash" in r["tools"]
        assert "read_file" in r["tools"]
        assert r["tools"]["bash"]["calls"] == 1
        assert r["tools"]["read_file"]["calls"] == 1


# ── 3. Warning detection ───────────────────────────────────────────────────

class TestWarningDetection:
    def _report_with_cache(self, avg_sim=0.9, invalidation_rate=0.1,
                           turn_count=10) -> dict:
        m = SessionMonitor("warn-test")
        with patch("nbchat.core.monitoring.parse_last_completion_metrics") as mock_parse:
            mock_m = MagicMock()
            mock_m.valid = True
            mock_m.sim_best = avg_sim
            mock_m.checkpoints_erased = 1 if invalidation_rate > 0.5 else 0
            mock_parse.return_value = mock_m
            for _ in range(turn_count):
                m.record_llm_call(100)
        return m.get_session_report()

    def test_low_sim_warning_fires(self):
        r = self._report_with_cache(avg_sim=0.5, turn_count=10)
        assert any("sim_best" in w for w in r["warnings"])

    def test_low_sim_warning_suppressed_below_min_turns(self):
        r = self._report_with_cache(avg_sim=0.5, turn_count=3)
        assert not any("sim_best" in w for w in r["warnings"])

    def test_no_low_sim_warning_above_threshold(self):
        r = self._report_with_cache(avg_sim=0.95, turn_count=10)
        assert not any("sim_best" in w for w in r["warnings"])

    def test_high_invalidation_warning_fires(self):
        r = self._report_with_cache(avg_sim=0.9, invalidation_rate=0.9,
                                    turn_count=10)
        assert any("invalidat" in w for w in r["warnings"])

    def test_reread_warning_fires(self):
        m = SessionMonitor("warn-tool")
        for _ in range(5):
            m.record_tool_call("search", was_compressed=True, had_error=False,
                               strategy="lossless_learned")
        r = m.get_session_report()
        assert any("reread" in w for w in r["warnings"])

    def test_reread_warning_suppressed_below_min_calls(self):
        m = SessionMonitor("warn-tool2")
        m.record_tool_call("search", was_compressed=True, had_error=False,
                           strategy="lossless_learned")
        r = m.get_session_report()
        # Only 1 call — below min threshold of 3
        assert not any("reread" in w for w in r["warnings"])

    def test_error_after_compression_warning_fires(self):
        m = SessionMonitor("warn-err")
        for _ in range(5):
            m.record_tool_call("api", was_compressed=True, had_error=True)
        r = m.get_session_report()
        assert any("error_after_compression" in w for w in r["warnings"])

    def test_llm_failure_warning_fires(self):
        m = SessionMonitor("warn-llm")
        for _ in range(5):
            m.record_tool_call("api", was_compressed=True, had_error=False,
                               strategy="headtail_llm_fallback")
        r = m.get_session_report()
        assert any("llm_failure" in w or "LLM" in w for w in r["warnings"])


# ── 4. Global stats merge ──────────────────────────────────────────────────

class TestGlobalMerge:
    def _session_data(self, tool_calls=5, reread=1, errors=0) -> dict:
        return {
            "cache": {
                "turn_count": 10,
                "sum_sim_best": 8.5,
                "low_sim_turns": 1,
                "cache_invalidations": 2,
                "sum_volatile_delta": 500,
            },
            "tools": {
                "bash": {
                    "calls": tool_calls,
                    "compressed_calls": tool_calls,
                    "reread_triggers": reread,
                    "error_after_compression": errors,
                    "no_output_count": 0,
                    "llm_failure_count": 0,
                    "total_input_chars": 10000,
                    "total_output_chars": 3000,
                }
            },
        }

    def test_sessions_seen_increments(self):
        g = _empty_global()
        g = merge_into_global(g, self._session_data())
        g = merge_into_global(g, self._session_data())
        assert g["sessions_seen"] == 2

    def test_cache_fields_accumulate(self):
        g = _empty_global()
        g = merge_into_global(g, self._session_data())
        g = merge_into_global(g, self._session_data())
        assert g["cache"]["turn_count"] == 20
        assert abs(g["cache"]["sum_sim_best"] - 17.0) < 0.01
        assert g["cache"]["cache_invalidations"] == 4

    def test_tool_fields_accumulate(self):
        g = _empty_global()
        g = merge_into_global(g, self._session_data(tool_calls=5, reread=1))
        g = merge_into_global(g, self._session_data(tool_calls=3, reread=2))
        t = g["tools"]["bash"]
        assert t["calls"] == 8
        assert t["reread_triggers"] == 3

    def test_new_tool_added_on_merge(self):
        g = _empty_global()
        session = {
            "cache": {"turn_count": 1, "sum_sim_best": 0.9,
                      "low_sim_turns": 0, "cache_invalidations": 0,
                      "sum_volatile_delta": 0},
            "tools": {"new_tool": {
                "calls": 1, "compressed_calls": 1,
                "reread_triggers": 0, "error_after_compression": 0,
                "no_output_count": 0, "llm_failure_count": 0,
                "total_input_chars": 100, "total_output_chars": 50,
            }},
        }
        g = merge_into_global(g, session)
        assert "new_tool" in g["tools"]

    def test_merge_is_pure(self):
        """merge_into_global must not mutate either argument."""
        g = _empty_global()
        s = self._session_data()
        g_copy = json.loads(json.dumps(g))
        s_copy = json.loads(json.dumps(s))
        merge_into_global(g, s)
        assert g == g_copy
        assert s == s_copy


# ── 5. get_global_report ──────────────────────────────────────────────────

class TestGlobalReport:
    def _global_with_data(self) -> dict:
        g = _empty_global()
        for _ in range(3):
            s = {
                "cache": {
                    "turn_count": 10,
                    "sum_sim_best": 9.0,
                    "low_sim_turns": 1,
                    "cache_invalidations": 2,
                    "sum_volatile_delta": 300,
                },
                "tools": {
                    "bash": {
                        "calls": 10, "compressed_calls": 8,
                        "reread_triggers": 2, "error_after_compression": 1,
                        "no_output_count": 1, "llm_failure_count": 1,
                        "total_input_chars": 10000, "total_output_chars": 5000,
                    }
                },
            }
            g = merge_into_global(g, s)
        return g

    def test_avg_sim_best_computed(self):
        g = self._global_with_data()
        r = get_global_report(g)
        # 27.0 / 30 turns = 0.9
        assert r["cache"]["avg_sim_best"] == pytest.approx(0.9, abs=0.001)

    def test_low_sim_rate_computed(self):
        g = self._global_with_data()
        r = get_global_report(g)
        # 3 low_sim_turns / 30 = 0.1
        assert r["cache"]["low_sim_rate"] == pytest.approx(0.1, abs=0.001)

    def test_tool_avg_ratio_computed(self):
        g = self._global_with_data()
        r = get_global_report(g)
        # 15000 / 30000 = 0.5
        assert r["tools"]["bash"]["avg_ratio"] == pytest.approx(0.5, abs=0.001)

    def test_tool_reread_rate_computed(self):
        g = self._global_with_data()
        r = get_global_report(g)
        # 6 / 30 = 0.2
        assert r["tools"]["bash"]["reread_rate"] == pytest.approx(0.2, abs=0.001)

    def test_suggestions_present(self):
        g = self._global_with_data()
        r = get_global_report(g)
        assert "suggestions" in r

    def test_sessions_seen_in_report(self):
        g = self._global_with_data()
        r = get_global_report(g)
        assert r["cache"]["sessions_seen"] == 3


# ── 6. Config suggestions ──────────────────────────────────────────────────

class TestConfigSuggestions:
    def _cache(self, avg_sim=0.9, inv_rate=0.1, turns=50) -> dict:
        return {
            "turn_count": turns,
            "sessions_seen": 5,
            "avg_sim_best": avg_sim,
            "low_sim_rate": 1 - avg_sim,
            "cache_invalidation_rate": inv_rate,
            "avg_volatile_delta": 100,
        }

    def _tool(self, calls=20, reread=0, err_comp=0, avg_ratio=0.5,
              llm_fail=0, no_out=0) -> dict:
        return {
            "calls": calls,
            "compressed_calls": calls,
            "avg_ratio": avg_ratio,
            "reread_rate": reread / max(calls, 1),
            "error_after_compression_rate": err_comp / max(calls, 1),
            "llm_failure_rate": llm_fail / max(calls, 1),
            "no_output_rate": no_out / max(calls, 1),
        }

    def test_reread_triggers_always_keep_suggestion(self):
        cache = self._cache()
        tools = {"web_search": self._tool(calls=20, reread=5)}
        suggestions = suggest_config(cache, tools)
        targets = [s["target"] for s in suggestions]
        assert any("ALWAYS_KEEP" in t and "web_search" in t for t in targets)

    def test_reread_suggestion_is_high_priority(self):
        cache = self._cache()
        tools = {"web_search": self._tool(calls=20, reread=5)}
        suggestions = suggest_config(cache, tools)
        for s in suggestions:
            if "web_search" in s["target"]:
                assert s["priority"] == "high"

    def test_error_after_compression_triggers_suggestion(self):
        cache = self._cache()
        tools = {"api_call": self._tool(calls=20, err_comp=4)}
        suggestions = suggest_config(cache, tools)
        targets = [s["target"] for s in suggestions]
        assert any("api_call" in t for t in targets)

    def test_poor_ratio_triggers_low_priority_suggestion(self):
        cache = self._cache()
        tools = {"list_dir": self._tool(calls=20, avg_ratio=0.92)}
        suggestions = suggest_config(cache, tools)
        low = [s for s in suggestions if s["priority"] == "low"
               and "list_dir" in s["target"]]
        assert low

    def test_low_sim_triggers_task_log_suggestion(self):
        cache = self._cache(avg_sim=0.5, turns=50)
        suggestions = suggest_config(cache, {})
        assert any("TASK_LOG" in s["target"] or "entity" in s["target"]
                   for s in suggestions)

    def test_low_sim_suggestion_high_priority(self):
        cache = self._cache(avg_sim=0.5, turns=50)
        suggestions = suggest_config(cache, {})
        high = [s for s in suggestions if s["priority"] == "high"]
        assert high

    def test_low_sim_suppressed_under_20_turns(self):
        cache = self._cache(avg_sim=0.5, turns=10)
        suggestions = suggest_config(cache, {})
        assert not any("TASK_LOG" in s.get("target", "") for s in suggestions)

    def test_high_invalidation_triggers_window_suggestion(self):
        cache = self._cache(inv_rate=0.5, turns=50)
        suggestions = suggest_config(cache, {})
        assert any("WINDOW" in s["target"] for s in suggestions)

    def test_llm_failure_triggers_command_tool_suggestion(self):
        cache = self._cache()
        tools = {"flaky_api": self._tool(calls=20, llm_fail=6)}
        suggestions = suggest_config(cache, tools)
        assert any("COMMAND_TOOLS" in s["target"] for s in suggestions)

    def test_no_output_triggers_review_suggestion(self):
        cache = self._cache()
        tools = {"health_check": self._tool(calls=20, no_out=10)}
        suggestions = suggest_config(cache, tools)
        assert any("health_check" in s["target"] for s in suggestions)

    def test_insufficient_calls_no_suggestion(self):
        cache = self._cache()
        # Only 5 calls — below threshold of 10
        tools = {"rare_tool": self._tool(calls=5, reread=4)}
        suggestions = suggest_config(cache, tools)
        assert not any("rare_tool" in s["target"] for s in suggestions)

    def test_suggestions_sorted_by_priority(self):
        cache = self._cache(avg_sim=0.5, turns=50)
        tools = {
            "bash": self._tool(calls=20, reread=5),            # high
            "list_dir": self._tool(calls=20, avg_ratio=0.95),  # low
        }
        suggestions = suggest_config(cache, tools)
        priorities = [s["priority"] for s in suggestions]
        order = {"high": 0, "medium": 1, "low": 2}
        assert all(
            order[priorities[i]] <= order[priorities[i + 1]]
            for i in range(len(priorities) - 1)
        )

    def test_no_suggestions_for_clean_session(self):
        cache = self._cache(avg_sim=0.95, inv_rate=0.05, turns=50)
        tools = {"bash": self._tool(calls=20, reread=0, err_comp=0, avg_ratio=0.4)}
        suggestions = suggest_config(cache, tools)
        assert suggestions == []


# ── 7. flush_session_monitor ──────────────────────────────────────────────

class TestFlushSessionMonitor:
    def test_flush_merges_into_global(self):
        sid = "flush-test-sess"
        m = get_session_monitor(sid)
        with patch("nbchat.core.monitoring.parse_last_completion_metrics") as mp:
            mp.return_value = MagicMock(valid=False)
            m.record_llm_call(100)
        m.record_tool_call("bash", was_compressed=True, had_error=False)

        db = MagicMock()
        db.load_global_monitoring_stats.return_value = None
        db.save_global_monitoring_stats = MagicMock()

        flush_session_monitor(sid, db)

        db.save_global_monitoring_stats.assert_called_once()
        saved = db.save_global_monitoring_stats.call_args[0][0]
        assert saved["sessions_seen"] == 1
        assert saved["tools"]["bash"]["calls"] == 1

    def test_flush_removes_monitor_from_registry(self):
        sid = "flush-remove-test"
        get_session_monitor(sid)   # ensure it exists
        db = MagicMock()
        db.load_global_monitoring_stats.return_value = None
        db.save_global_monitoring_stats = MagicMock()
        flush_session_monitor(sid, db)
        # Getting monitor again should create a fresh one
        m2 = get_session_monitor(sid)
        assert m2.get_session_report()["cache"]["turn_count"] == 0

    def test_flush_unknown_session_noop(self):
        db = MagicMock()
        db.load_global_monitoring_stats.return_value = None
        # Should not raise
        flush_session_monitor("nonexistent-session-xyz", db)
        db.save_global_monitoring_stats.assert_not_called()

    def test_flush_merges_with_existing_global(self):
        existing = _empty_global()
        existing["sessions_seen"] = 5
        existing["cache"]["turn_count"] = 100

        sid = "flush-merge-test"
        m = get_session_monitor(sid)
        with patch("nbchat.core.monitoring.parse_last_completion_metrics") as mp:
            mp.return_value = MagicMock(valid=False)
            for _ in range(3):
                m.record_llm_call(0)

        db = MagicMock()
        db.load_global_monitoring_stats.return_value = existing
        db.save_global_monitoring_stats = MagicMock()

        flush_session_monitor(sid, db)

        saved = db.save_global_monitoring_stats.call_args[0][0]
        assert saved["sessions_seen"] == 6
        assert saved["cache"]["turn_count"] == 103


# ── 8. Thread safety ──────────────────────────────────────────────────────

class TestThreadSafety:
    def test_concurrent_record_tool_calls(self):
        """Multiple threads recording tool calls must not corrupt counts."""
        m = SessionMonitor("thread-test")
        n_threads = 10
        calls_per_thread = 50

        def worker():
            with patch("nbchat.core.monitoring.parse_last_completion_metrics") as mp:
                mp.return_value = MagicMock(valid=False)
                for _ in range(calls_per_thread):
                    m.record_tool_call("bash", was_compressed=True, had_error=False)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        r = m.get_session_report()
        assert r["tools"]["bash"]["calls"] == n_threads * calls_per_thread

    def test_concurrent_llm_calls_and_reads(self, tmp_path):
        """record_llm_call and get_session_report can run concurrently."""
        m = SessionMonitor("thread-test-2")
        errors: list = []

        def writer():
            with patch("nbchat.core.monitoring._LOG_PATH", tmp_path / "no.log"):
                for _ in range(20):
                    m.record_llm_call(100)

        def reader():
            for _ in range(20):
                try:
                    m.get_session_report()
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []


# ── 9. format_report ──────────────────────────────────────────────────────

class TestFormatReport:
    def test_format_session_report(self):
        m = SessionMonitor("fmt-test")
        r = m.get_session_report()
        text = format_report(r)
        assert isinstance(text, str)
        assert "fmt-test" in text

    def test_format_includes_warnings(self):
        m = SessionMonitor("fmt-warn")
        for _ in range(5):
            m.record_tool_call("bash", was_compressed=True, had_error=False,
                               strategy="lossless_learned")
        r = m.get_session_report()
        text = format_report(r)
        assert "⚠" in text

    def test_format_global_report(self):
        g = _empty_global()
        g["sessions_seen"] = 3
        g["cache"]["turn_count"] = 30
        r = get_global_report(g)
        text = format_report(r)
        assert "Global" in text or "sessions" in text

    def test_format_includes_suggestions(self):
        cache = {
            "turn_count": 50, "sessions_seen": 5,
            "avg_sim_best": 0.5, "low_sim_rate": 0.5,
            "cache_invalidation_rate": 0.1, "avg_volatile_delta": 100,
        }
        tools: dict = {}
        r = {"cache": cache, "tools": tools,
             "suggestions": suggest_config(cache, tools)}
        text = format_report(r)
        assert "[HIGH]" in text or "HIGH" in text
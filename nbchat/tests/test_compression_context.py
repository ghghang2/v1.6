"""Tests for nbchat compression and context management.

Covers:
- nbchat/core/compressor.py: compress_tool_output and helpers
- nbchat/ui/context_manager.py: context budget, importance, trimming
"""
import json
import sys
import textwrap
from pathlib import Path
from unittest import mock

import pytest

# Ensure the repo root is on sys.path so imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nbchat.core import compressor as comp
from nbchat.core import config
from nbchat.ui.context_manager import (
    ImportanceTracker,
    _est_tokens,
    _extract_entities,
    _group_by_user_turn,
    _parse_structured_summary,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_compressor():
    """Reset compressor session state and stats before each test."""
    comp._sessions.clear()
    comp._stats.clear()
    yield
    comp._sessions.clear()
    comp._stats.clear()


@pytest.fixture
def mock_client():
    """Return a mock OpenAI client with a chat.completions.create method."""
    client = mock.MagicMock()
    client.chat.completions.create.return_value = mock.MagicMock(
        choices=[mock.MagicMock(message=mock.MagicMock(content="Summary"))]
    )
    return client


# ---------------------------------------------------------------------------
# Helper constants
# ---------------------------------------------------------------------------

MAX_CHARS = config.MAX_TOOL_OUTPUT_CHARS  # 32768


def _make_long_text(n_chars):
    """Generate a string of approximately n_chars."""
    unit = "x" * 100
    return (unit * (n_chars // 100 + 1))[:n_chars]


# ===========================================================================
# 1. Compressor: Passthrough
# ===========================================================================

class TestCompressorPassthrough:
    """When tool output <= MAX_TOOL_OUTPUT_CHARS, it should pass through unchanged."""

    def test_exact_boundary(self):
        result = "a" * MAX_CHARS
        out = comp.compress_tool_output("read_file", '{"path":"f.txt"}', result,
                                         model="test", client=None, session_id="s1")
        assert out == result
        assert comp._stats["read_file"]["strategy"] == {"passthrough": 1}

    def test_below_boundary(self):
        result = "a" * (MAX_CHARS - 1)
        out = comp.compress_tool_output("cat", '{"file":"b.txt"}', result,
                                         model="test", client=None, session_id="s2")
        assert out == result

    def test_above_boundary_is_compressed(self):
        result = "a" * (MAX_CHARS + 1)
        out = comp.compress_tool_output("cat", '{"file":"b.txt"}', result,
                                         model="test", client=None, session_id="s3")
        assert out != result  # must be compressed

# ===========================================================================
# 2. Compressor: Lossless mode (repeated tool+key)
# ===========================================================================

class TestCompressorLossless:
    """Second occurrence of same tool+key should be lossless (head+tail)."""

    def test_lossless_learned_on_second_call(self):
        long_result = _make_long_text(MAX_CHARS + 100)
        tool_args = '{"path":"/tmp/test.txt"}'

        # First call: should use head+tail (not yet learned)
        out1 = comp.compress_tool_output("read_file", tool_args, long_result,
                                          model="test", client=None, session_id="sess")
        assert out1 != long_result
        assert "..." in out1

        # Second call: should be lossless
        out2 = comp.compress_tool_output("read_file", tool_args, long_result,
                                          model="test", client=None, session_id="sess")
        assert out2 != long_result
        assert "..." in out2

        # Verify the tool was marked lossless
        state = comp._sess("sess")
        assert "read_file" in state["lossless"]

    def test_lossless_headtail_format(self):
        long_result = _make_long_text(MAX_CHARS + 200)
        tool_args = '{"path":"/tmp/test.txt"}'
        out = comp.compress_tool_output("read_file", tool_args, long_result,
                                         model="test", client=None, session_id="sess2")
        # Should contain the omitted marker
        assert "chars omitted" in out or "..." in out
        # Should start with original content
        assert out.startswith(long_result[:MAX_CHARS // 2])

# ===========================================================================
# 3. Compressor: Syntax-aware skeletons
# ===========================================================================

class TestCompressorSkeletons:
    """Structured files should get syntax-aware skeleton extraction."""

    def test_python_skeleton(self):
        source = textwrap.dedent('''\
            import os
            import sys

            class MyClass:
                """A docstring."""
                def method(self):
                    pass

            def main():
                print("hello")
        ''')
        result = source + ("\n" * 500)  # pad to exceed MAX_CHARS
        out = comp.compress_tool_output("read_file", '{"path":"test.py"}', result,
                                         model="test", client=None, session_id="s1")
        assert "[Python skeleton" in out
        assert "import os" in out
        assert "class MyClass:" in out
        assert '"""A docstring."""' in out
        assert "..." in out  # method body replaced

    def test_json_skeleton(self):
        data = {k: f"value_{i}" * 50 for i, k in enumerate(range(50))}
        result = json.dumps(data, indent=2) + "\n" * 100
        out = comp.compress_tool_output("read_file", '{"path":"data.json"}', result,
                                         model="test", client=None, session_id="s2")
        assert "[JSON object" in out
        # Should contain truncated keys
        assert "..." in out

    def test_yaml_skeleton(self):
        result = "key1: value1\nkey2: value2\n" + ("  nested: deep\n" * 500)
        out = comp.compress_tool_output("read_file", '{"path":"config.yaml"}', result,
                                         model="test", client=None, session_id="s3")
        assert "[YAML" in out
        assert "key1:" in out

    def test_js_skeleton(self):
        result = "function foo() {}\nclass Bar {\n  method() {}\n}\n" + ("x\n" * 500)
        out = comp.compress_tool_output("read_file", '{"path":"app.js"}', result,
                                         model="test", client=None, session_id="s4")
        assert "[JS/TS skeleton" in out
        assert "function foo" in out

    def test_unstructured_file_falls_back_to_headtail(self):
        result = "a" * (MAX_CHARS + 100)
        out = comp.compress_tool_output("read_file", '{"path":"data.csv"}', result,
                                         model="test", client=None, session_id="s5")
        # CSV is not a structured ext, so should use head+tail
        assert "chars omitted" in out or "..." in out

# ===========================================================================
# 4. Compressor: Command tools
# ===========================================================================

class TestCompressorCommandTools:
    """Command tools should use head+tail truncation."""

    def test_run_command_truncated(self):
        result = _make_long_text(MAX_CHARS + 500)
        out = comp.compress_tool_output("run_command", '{"cmd":"ls -la"}', result,
                                         model="test", client=None, session_id="s1")
        assert "..." in out
        assert "chars omitted" in out or "..." in out

    def test_bash_truncated(self):
        result = _make_long_text(MAX_CHARS + 500)
        out = comp.compress_tool_output("bash", '{"cmd":"cat /etc/passwd"}', result,
                                         model="test", client=None, session_id="s2")
        assert "..." in out

# ===========================================================================
# 5. Compressor: LLM summarisation
# ===========================================================================

class TestCompressorLLM:
    """Non-file, non-command tools should trigger LLM summarisation."""

    def test_llm_summarisation_called(self, mock_client):
        result = _make_long_text(MAX_CHARS + 200)
        out = comp.compress_tool_output("get_weather", '{"city":"London"}', result,
                                         model="test", client=mock_client, session_id="s1")
        mock_client.chat.completions.create.assert_called_once()
        assert out == "Summary"

    def test_llm_fallback_to_headtail_on_error(self, mock_client):
        mock_client.chat.completions.create.side_effect = Exception("network error")
        result = _make_long_text(MAX_CHARS + 200)
        out = comp.compress_tool_output("get_weather", '{"city":"Paris"}', result,
                                         model="test", client=mock_client, session_id="s2")
        assert "..." in out or "chars omitted" in out

    def test_no_relevant_output(self, mock_client):
        mock_client.chat.completions.create.return_value = mock.MagicMock(
            choices=[mock.MagicMock(content="NO_RELEVANT_OUTPUT")]
        )
        result = _make_long_text(MAX_CHARS + 200)
        out = comp.compress_tool_output("send_email", '{"to":"a@b.com"}', result,
                                         model="test", client=mock_client, session_id="s3")
        assert out == "NO_RELEVANT_OUTPUT"

# ===========================================================================
# 6. Compressor: Stats tracking
# ===========================================================================

class TestCompressorStats:
    """Compression statistics should be tracked correctly."""

    def test_stats_recorded(self, mock_client):
        result = _make_long_text(MAX_CHARS + 100)
        comp.compress_tool_output("run_command", '{"cmd":"ls"}', result,
                                   model="test", client=mock_client, session_id="s1")
        stats = comp.get_compression_stats()
        assert "run_command" in stats
        assert stats["run_command"]["calls"] == 1
        assert stats["run_command"]["compressed"] == 1
        assert stats["run_command"]["in"] > MAX_CHARS
        assert stats["run_command"]["out"] < stats["run_command"]["in"]

    def test_reset_stats(self):
        result = _make_long_text(MAX_CHARS + 100)
        comp.compress_tool_output("cat", '{"file":"x"}', result,
                                   model="test", client=None, session_id="s1")
        assert len(comp.get_compression_stats()) == 1
        comp.reset_compression_stats()
        assert len(comp.get_compression_stats()) == 0

    def test_session_lifecycle(self):
        comp.init_session("new_sess")
        assert "new_sess" in comp._sessions
        comp.clear_session("new_sess")
        assert "new_sess" not in comp._sessions

# ===========================================================================
# 7. Context Manager: _est_tokens
# ===========================================================================

class TestEstTokens:
    """Token estimation should follow the 2.5/4.0 char-per-token ratio."""

    def test_tool_role_ratio(self):
        row = ("tool", "a" * 250, "tid", "tname", '{"a":"b"}', 0)
        tokens = _est_tokens(row)
        expected = max(1, int(250 / 2.5))
        assert tokens == expected

    def test_non_tool_role_ratio(self):
        row = ("assistant", "a" * 400, "tid", "tname", "", 0)
        tokens = _est_tokens(row)
        expected = max(1, int(400 / 4.0))
        assert tokens == expected

    def test_empty_content(self):
        row = ("user", "", "tid", "tname", "", 0)
        tokens = _est_tokens(row)
        assert tokens == 1  # minimum is 1

# ===========================================================================
# 8. Context Manager: Importance scoring
# ===========================================================================

class TestImportanceScore:
    """Importance scores should reflect error presence, tool output size, etc."""

    @staticmethod
    def _score(exchange_msgs, raw_result=""):
        # Import the method from ContextMixin
        from nbchat.ui.context_manager import ContextMixin
        return ContextMixin._importance_score(exchange_msgs, raw_result)

    def test_base_score(self):
        msgs = [{"role": "user", "content": "hello"}]
        score = self._score(msgs)
        assert score == 1.0  # base

    def test_error_in_tool_result(self):
        msgs = [{"role": "user", "content": "run ls"}, {"role": "tool", "content": "Error: file not found"}]
        score = self._score(msgs, "Error: file not found")
        assert score >= 4.0  # base 1.0 + error 3.0

    def test_success_in_tool_result(self):
        msgs = [{"role": "user", "content": "run ls"}, {"role": "tool", "content": "Success: file created"}]
        score = self._score(msgs)
        assert score >= 2.5  # base 1.0 + tool 1.0 + success 1.5

    def test_long_tool_result(self):
        msgs = [{"role": "user", "content": "run ls"}, {"role": "tool", "content": "a" * 600}]
        score = self._score(msgs)
        assert score >= 2.5  # base 1.0 + tool 1.0 + long 0.5

    def test_user_correction(self):
        msgs = [{"role": "user", "content": "actually, do it differently"}]
        score = self._score(msgs)
        assert score >= 3.5  # base 1.0 + correction 2.5

    def test_score_capped_at_10(self):
        msgs = [
            {"role": "user", "content": "actually, wrong, no, don't do that"},
            {"role": "tool", "content": "Error: exception failed traceback"},
        ]
        score = self._score(msgs, "Error: exception failed traceback")
        assert score == 10.0

# ===========================================================================
# 9. Context Manager: Structured summary parsing
# ===========================================================================

class TestParseStructuredSummary:
    """Should correctly parse GOAL/ENTITIES/RATIONALE format."""

    def test_full_summary(self):
        text = "GOAL: Fix the bug\nENTITIES: file:report.py | api:/users\nRATIONALE: Fixed the issue"
        result = _parse_structured_summary(text)
        assert result["goal"] == "Fix the bug"
        assert result["entities"] == ["file:report.py", "api:/users"]
        assert result["rationale"] == "Fixed the issue"

    def test_missing_entities(self):
        text = "GOAL: Test\nENTITIES: none\nRATIONALE: Done"
        result = _parse_structured_summary(text)
        assert result["goal"] == "Test"
        assert result["entities"] == []
        assert result["rationale"] == "Done"

    def test_single_line(self):
        text = "GOAL: Only goal here"
        result = _parse_structured_summary(text)
        assert result["goal"] == "Only goal here"
        assert result["entities"] == []
        assert result["rationale"] == ""

# ===========================================================================
# 10. Context Manager: Entity extraction
# ===========================================================================

class TestExtractEntities:
    """Should extract file paths, API endpoints, and URLs."""

    def test_file_extensions(self):
        text = "modified /content/nbchat/core/compressor.py and /content/repo_config.yaml"
        entities = _extract_entities(text)
        assert "compressor.py" in entities or "/content/nbchat/core/compressor.py" in entities

    def test_api_endpoints(self):
        text = "called /api/users and /api/reports"
        entities = _extract_entities(text)
        assert "api:/api/users" in entities or "/api/users" in entities

    def test_urls(self):
        text = "visited https://example.com/path"
        entities = _extract_entities(text)
        assert "url:example.com" in entities

    def test_limits_to_10(self):
        text = " ".join([f"/content/file{i}.py" for i in range(20)])
        entities = _extract_entities(text)
        assert len(entities) <= 10

# ===========================================================================
# 11. Context Manager: Group by user turn
# ===========================================================================

class TestGroupByUserTurn:
    """Should group messages into user-turn units."""

    def test_simple_turn(self):
        rows = [
            ("user", "hello", "t1", "", "", 0),
            ("assistant", "hi", "t2", "", "", 0),
            ("tool", "result", "t3", "run", '{"a":1}', 0),
        ]
        units = _group_by_user_turn(rows)
        assert len(units) == 1
        assert len(units[0]) == 3

    def test_multiple_turns(self):
        rows = [
            ("user", "first", "t1", "", "", 0),
            ("assistant", "ok", "t2", "", "", 0),
            ("user", "second", "t3", "", "", 0),
            ("assistant", "done", "t4", "", "", 0),
        ]
        units = _group_by_user_turn(rows)
        assert len(units) == 2
        assert len(units[0]) == 2
        assert len(units[1]) == 2

    def test_system_message_first(self):
        rows = [
            ("system", "prompt", "t0", "", "", 0),
            ("user", "hello", "t1", "", "", 0),
        ]
        units = _group_by_user_turn(rows)
        # system is not a user message, so it goes with the first unit
        assert len(units) == 1

# ===========================================================================
# 12. Context Manager: ImportanceTracker
# ===========================================================================

class TestImportanceTracker:
    """Should track importance scores and compute thresholds."""

    def test_initial_write_threshold(self):
        tracker = ImportanceTracker()
        # Cold start: should return COLD_WRITE (2.5)
        assert tracker.write_threshold == 2.5

    def test_initial_retrieval_threshold(self):
        tracker = ImportanceTracker()
        assert tracker.retrieval_threshold == 3.0

    def test_thresholds_after_cold_start(self):
        tracker = ImportanceTracker()
        # Fill with enough scores to pass cold start
        for _ in range(15):
            tracker.record(5.0)
        # Now thresholds should be based on percentile
        assert tracker.write_threshold >= 2.5
        assert tracker.retrieval_threshold >= 3.0

    def test_state_dict(self):
        tracker = ImportanceTracker()
        tracker.record(3.0)
        tracker.record(5.0)
        state = tracker.state_dict()
        assert state["n"] == 2
        assert "write_threshold" in state
        assert "retrieval_threshold" in state
        assert state["min"] == 3.0
        assert state["max"] == 5.0

    def test_fifo_eviction(self):
        tracker = ImportanceTracker(window=5)
        for i in range(10):
            tracker.record(float(i))
        # Only last 5 should remain
        assert tracker.state_dict()["n"] == 5

# ===========================================================================
# 13. Context Manager: Hard trim Pass 2
# ===========================================================================

class TestHardTrimPass2:
    """Last-resort truncation of largest tool result to 200 chars."""

    @staticmethod
    def _simulate_hard_trim(messages, limit=100000):
        """Simulate _hard_trim Pass 2 logic."""
        from nbchat.ui.context_manager import ContextMixin

        def est(msg):
            chars = len(msg.get("content") or "") + len(
                "".join(tc.get("function", {}).get("arguments", "") for tc in (msg.get("tool_calls") or []))
            )
            return max(1, int(chars / 2.5))

        def total():
            return sum(est(m) for m in messages)

        # Pass 2: truncate largest tool result
        while total() > limit:
            tool_indices = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
            if not tool_indices:
                break
            largest = max(tool_indices, key=lambda i: len(messages[i].get("content", "")))
            original = messages[largest].get("content", "")
            if len(original) <= 200:
                break
            messages[largest]["content"] = original[:200] + f"\n[...truncated {len(original) - 200} chars...]"

    def test_truncates_largest_tool_result(self):
        messages = [
            {"role": "assistant", "content": "ok", "tool_calls": [{"function": {"name": "run", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "t1", "content": "a" * 1000},
            {"role": "assistant", "content": "done"},
        ]
        # Set a very low limit to force truncation
        self._simulate_hard_trim(messages, limit=10)
        # The tool result should be truncated
        tool_msg = messages[1]
        assert "truncated" in tool_msg["content"]
        assert len(tool_msg["content"]) == 200 + len("[...truncated 800 chars...]")

    def test_no_truncation_when_under_limit(self):
        messages = [
            {"role": "assistant", "content": "ok", "tool_calls": [{"function": {"name": "run", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "t1", "content": "short"},
        ]
        self._simulate_hard_trim(messages, limit=10000)
        assert messages[1]["content"] == "short"

    def test_no_truncation_when_already_small(self):
        messages = [
            {"role": "assistant", "content": "ok", "tool_calls": [{"function": {"name": "run", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "t1", "content": "a" * 100},
        ]
        self._simulate_hard_trim(messages, limit=10)
        # Should not truncate since content <= 200 chars
        assert messages[1]["content"] == "a" * 100

# ===========================================================================
# 14. Integration: Full compression + context flow
# ===========================================================================

class TestIntegration:
    """End-to-end test: tool output compressed, then context window respected."""

    def test_compressed_output_fits_in_context(self, mock_client):
        """Tool output is compressed to MAX_CHARS, then context window is applied."""
        # Generate a very long tool output
        long_result = _make_long_text(MAX_CHARS + 1000)

        # Compress it
        compressed = comp.compress_tool_output(
            "run_command", '{"cmd":"ls -la /"}', long_result,
            model="test", client=mock_client, session_id="int_test"
        )

        # Should be compressed
        assert len(compressed) < len(long_result)
        assert len(compressed) <= MAX_CHARS  # should not exceed max

        # Verify stats were recorded
        stats = comp.get_compression_stats()
        assert "run_command" in stats
        assert stats["run_command"]["compressed"] == 1

    def test_context_budget_calculation(self):
        """Verify CONTEXT_BUDGET is computed correctly from config."""
        ctx_budget = config.CONTEXT_BUDGET
        expected = config.CTX_SIZE // config.N_PARALLEL
        assert ctx_budget == expected

    def test_headroom_budget(self):
        """Verify effective budget with headroom and reserve."""
        budget = int(config.CONTEXT_BUDGET * config.CONTEXT_HEADROOM) - config.PREFIX_TOKEN_RESERVE
        # Should be less than raw CONTEXT_BUDGET
        assert budget < config.CONTEXT_BUDGET

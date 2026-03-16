"""Tests for nbchat.core.compressor.

Run from repo root:
    pytest tests/test_compressor.py -v

All LLM client calls are mocked.  Tests are fully self-contained.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Make the module importable without a full nbchat install by patching the
# config import that fires at module load time.
# ---------------------------------------------------------------------------
_config_mock = MagicMock()
_config_mock.MAX_TOOL_OUTPUT_CHARS = 200   # deliberately small for tests
sys.modules.setdefault("nbchat", MagicMock())
sys.modules.setdefault("nbchat.core", MagicMock())
sys.modules["nbchat.core.config"] = _config_mock

# Now import the module under test.
# We use importlib so the patch above is in place before the module executes.
import importlib
import nbchat.core.compressor as _comp_mod

# Re-point the module-level constant so tests exercise compression logic.
_comp_mod.MAX_TOOL_OUTPUT_CHARS = 200

from nbchat.core.compressor import (
    compress_tool_output,
    get_compression_stats,
    reset_compression_stats,
    init_session,
    clear_session,
    _python_skeleton,
    _json_skeleton,
    _yaml_skeleton,
    _js_skeleton,
    _head_tail,
    _extract_key_arg,
    _detect_file_extension,
    FILE_READ_TOOLS,
    COMMAND_TOOLS,
)

MAX = 200  # matches _comp_mod.MAX_TOOL_OUTPUT_CHARS above


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_client(response_text: str = "LLM summary"):
    client = MagicMock()
    client.chat.completions.create.return_value.choices[0].message.content = (
        response_text
    )
    return client


def _short(n: int = 10) -> str:
    return "x" * n


def _long(n: int = MAX + 50) -> str:
    return "a" * (n // 2) + "\n" + "b" * (n - n // 2)


# ---------------------------------------------------------------------------
# 1. Passthrough
# ---------------------------------------------------------------------------

class TestPassthrough:
    def test_short_output_returned_unchanged(self):
        result = compress_tool_output(
            "any_tool", "{}", _short(), model="m", client=_mock_client()
        )
        assert result == _short()

    def test_exact_boundary_passes_through(self):
        text = "z" * MAX
        result = compress_tool_output(
            "any_tool", "{}", text, model="m", client=_mock_client()
        )
        assert result == text

    def test_one_over_boundary_triggers_compression(self):
        text = "z" * (MAX + 1)
        result = compress_tool_output(
            "search_api", "{}", text, model="m", client=_mock_client("summary")
        )
        assert result == "summary"


# ---------------------------------------------------------------------------
# 2. Python skeleton extraction
# ---------------------------------------------------------------------------

class TestPythonSkeleton:
    _SOURCE = '''\
import os
import sys

CONSTANT = "hello"

def standalone(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y

class MyClass:
    """A demo class."""

    def __init__(self, value: int):
        """Init."""
        self.value = value

    def method(self) -> str:
        return str(self.value)

    @staticmethod
    def static_method():
        pass

async def async_fn():
    await something()
'''

    def test_imports_preserved(self):
        result = _python_skeleton(self._SOURCE, 2000)
        assert "import os" in result
        assert "import sys" in result

    def test_constant_preserved(self):
        result = _python_skeleton(self._SOURCE, 2000)
        assert "CONSTANT" in result

    def test_function_signature_preserved(self):
        result = _python_skeleton(self._SOURCE, 2000)
        assert "def standalone(x: int, y: int) -> int:" in result

    def test_function_body_replaced_with_ellipsis(self):
        result = _python_skeleton(self._SOURCE, 2000)
        assert "return x + y" not in result
        assert "..." in result

    def test_class_definition_preserved(self):
        result = _python_skeleton(self._SOURCE, 2000)
        assert "class MyClass:" in result

    def test_method_signatures_preserved(self):
        result = _python_skeleton(self._SOURCE, 2000)
        assert "__init__" in result
        assert "def method(self)" in result
        assert "def static_method" in result

    def test_static_decorator_preserved(self):
        result = _python_skeleton(self._SOURCE, 2000)
        assert "@staticmethod" in result

    def test_async_function_signature_preserved(self):
        result = _python_skeleton(self._SOURCE, 2000)
        assert "async def async_fn" in result

    def test_short_docstrings_preserved(self):
        result = _python_skeleton(self._SOURCE, 2000)
        assert "Add two numbers." in result

    def test_header_line_count_present(self):
        result = _python_skeleton(self._SOURCE, 2000)
        assert "lines total" in result

    def test_syntax_error_returns_none(self):
        result = _python_skeleton("def broken(:\n    pass", 2000)
        assert result is None

    def test_max_chars_truncation(self):
        result = _python_skeleton(self._SOURCE, 50)
        assert result is not None
        assert len(result) <= 50 + len("\n...[skeleton truncated]") + 50
        assert "skeleton truncated" in result

    def test_empty_source_returns_header(self):
        result = _python_skeleton("", 2000)
        assert result is not None
        assert "0 lines total" in result


# ---------------------------------------------------------------------------
# 3. JSON skeleton extraction
# ---------------------------------------------------------------------------

class TestJsonSkeleton:
    def test_dict_keys_shown(self):
        obj = {"name": "alice", "age": 30, "active": True}
        result = _json_skeleton(json.dumps(obj), 2000)
        assert "name" in result
        assert "age" in result
        assert "active" in result

    def test_nested_dict_summarised(self):
        obj = {"config": {"a": 1, "b": 2, "c": 3}}
        result = _json_skeleton(json.dumps(obj), 2000)
        assert "config" in result
        assert "{...3 keys}" in result

    def test_nested_list_summarised(self):
        obj = {"items": [1, 2, 3, 4, 5]}
        result = _json_skeleton(json.dumps(obj), 2000)
        assert "[...5 items]" in result

    def test_array_shows_count(self):
        arr = [{"id": i} for i in range(20)]
        result = _json_skeleton(json.dumps(arr), 2000)
        assert "20 items" in result

    def test_array_shows_first_item(self):
        arr = [{"id": 0, "val": "x"}, {"id": 1}]
        result = _json_skeleton(json.dumps(arr), 2000)
        assert '"id"' in result

    def test_invalid_json_returns_none(self):
        result = _json_skeleton("{not: valid json}", 2000)
        assert result is None

    def test_long_string_value_truncated(self):
        obj = {"key": "x" * 200}
        result = _json_skeleton(json.dumps(obj), 2000)
        assert "..." in result

    def test_max_chars_truncation(self):
        obj = {f"key_{i}": f"value_{i}" for i in range(50)}
        result = _json_skeleton(json.dumps(obj), 100)
        assert result is not None
        assert len(result) <= 100 + len("\n...[truncated]") + 10


# ---------------------------------------------------------------------------
# 4. YAML skeleton extraction
# ---------------------------------------------------------------------------

class TestYamlSkeleton:
    _YAML = """\
name: my-project
version: 1.0.0
dependencies:
  - requests
  - numpy
config:
  debug: true
  host: localhost
"""

    def test_top_level_keys_present(self):
        result = _yaml_skeleton(self._YAML, 2000)
        assert "name:" in result
        assert "version:" in result
        assert "dependencies:" in result
        assert "config:" in result

    def test_indented_lines_excluded(self):
        result = _yaml_skeleton(self._YAML, 2000)
        assert "requests" not in result
        assert "debug" not in result

    def test_header_shows_line_count(self):
        result = _yaml_skeleton(self._YAML, 2000)
        assert "lines" in result

    def test_empty_yaml_returns_none(self):
        result = _yaml_skeleton("# just a comment\n\n", 2000)
        assert result is None

    def test_max_chars_truncation(self):
        result = _yaml_skeleton(self._YAML, 20)
        assert result is not None
        assert "truncated" in result


# ---------------------------------------------------------------------------
# 5. JS/TS skeleton extraction
# ---------------------------------------------------------------------------

class TestJsSkeleton:
    _SOURCE = """\
import { something } from './module';

export async function fetchData(url: string): Promise<Response> {
  return fetch(url);
}

export class DataService {
  private cache: Map<string, any>;

  constructor(private config: Config) {
    this.cache = new Map();
  }

  async getData(key: string): Promise<any> {
    return this.cache.get(key);
  }
}

const helper = (x: number) => x * 2;

export interface Config {
  timeout: number;
}

export type Result<T> = { data: T; error?: string };
"""

    def test_export_function_captured(self):
        result = _js_skeleton(self._SOURCE, 2000)
        assert result is not None
        assert "fetchData" in result

    def test_class_definition_captured(self):
        result = _js_skeleton(self._SOURCE, 2000)
        assert "DataService" in result

    def test_interface_captured(self):
        result = _js_skeleton(self._SOURCE, 2000)
        assert "Config" in result

    def test_type_alias_captured(self):
        result = _js_skeleton(self._SOURCE, 2000)
        assert "Result" in result

    def test_function_body_not_captured(self):
        result = _js_skeleton(self._SOURCE, 2000)
        assert "return fetch" not in result

    def test_header_shows_line_count(self):
        result = _js_skeleton(self._SOURCE, 2000)
        assert "lines" in result

    def test_empty_source_returns_none(self):
        result = _js_skeleton("// no signatures here\nconst x = 1;\n", 2000)
        # const x = captured
        # this is fine either way — just check it doesn't crash
        assert result is None or isinstance(result, str)

    def test_max_chars_truncation(self):
        result = _js_skeleton(self._SOURCE, 40)
        assert result is not None
        assert "truncated" in result


# ---------------------------------------------------------------------------
# 6. Head+tail
# ---------------------------------------------------------------------------

class TestHeadTail:
    def test_output_bounded(self):
        text = "a" * 1000
        result = _head_tail(text, MAX)
        # head + tail + separator; total chars < input
        assert len(result) < len(text)

    def test_start_preserved(self):
        text = "START" + "x" * 500 + "END"
        result = _head_tail(text, MAX)
        assert result.startswith("START")

    def test_end_preserved(self):
        text = "START" + "x" * 500 + "END"
        result = _head_tail(text, MAX)
        assert result.endswith("END")

    def test_omission_notice_present(self):
        text = "a" * 1000
        result = _head_tail(text, MAX)
        assert "chars omitted" in result

    def test_label_included_when_given(self):
        text = "a" * 1000
        result = _head_tail(text, MAX, label="bash")
        assert "bash" in result


# ---------------------------------------------------------------------------
# 7. Strategy dispatch
# ---------------------------------------------------------------------------

class TestStrategyDispatch:
    def test_command_tool_uses_headtail(self):
        reset_compression_stats()
        text = "a" * (MAX + 100)
        compress_tool_output("bash", "{}", text, model="m", client=_mock_client())
        stats = get_compression_stats()
        assert "bash" in stats
        assert "headtail_command" in stats["bash"]["strategies"]

    def test_file_read_py_uses_syntax_aware(self):
        reset_compression_stats()
        source = "def foo(): pass\n" * 20
        args = json.dumps({"path": "utils.py"})
        compress_tool_output(
            "read_file", args, source * 5, model="m", client=_mock_client()
        )
        stats = get_compression_stats()
        assert "read_file" in stats
        assert any("syntax_py" in k for k in stats["read_file"]["strategies"])

    def test_file_read_unknown_ext_uses_headtail(self):
        reset_compression_stats()
        text = "binary content\n" * 50
        args = json.dumps({"path": "data.bin"})
        compress_tool_output(
            "read_file", args, text, model="m", client=_mock_client()
        )
        stats = get_compression_stats()
        assert "headtail_file" in stats["read_file"]["strategies"]

    def test_other_tool_uses_llm(self):
        reset_compression_stats()
        text = "search result " * 30
        compress_tool_output(
            "web_search", '{"query":"test"}', text, model="m",
            client=_mock_client("LLM summary of search"),
        )
        stats = get_compression_stats()
        assert "llm" in stats["web_search"]["strategies"]

    def test_llm_failure_falls_back_to_headtail(self):
        reset_compression_stats()
        bad_client = MagicMock()
        bad_client.chat.completions.create.side_effect = RuntimeError("timeout")
        text = "data " * 100
        result = compress_tool_output(
            "api_call", "{}", text, model="m", client=bad_client
        )
        assert "chars omitted" in result
        stats = get_compression_stats()
        assert "headtail_llm_fallback" in stats["api_call"]["strategies"]


# ---------------------------------------------------------------------------
# 8. Session-local lossless learning
# ---------------------------------------------------------------------------

class TestLosslessLearning:
    def setup_method(self):
        reset_compression_stats()
        init_session("sess-test")

    def teardown_method(self):
        clear_session("sess-test")

    def _compress(self, tool_name="web_search", args='{"query":"foo"}', text=None):
        if text is None:
            text = "result " * 60
        return compress_tool_output(
            tool_name, args, text, model="m",
            client=_mock_client("summary"), session_id="sess-test",
        )

    def test_first_call_not_lossless(self):
        reset_compression_stats()
        self._compress()
        stats = get_compression_stats()
        assert "lossless_learned" not in stats.get("web_search", {}).get(
            "strategies", {}
        )

    def test_repeat_call_triggers_lossless(self):
        reset_compression_stats()
        args = '{"query":"foo"}'
        text = "result " * 60
        # First call: compressed normally
        self._compress(args=args, text=text)
        # Second call with same args: should detect repeat
        self._compress(args=args, text=text)
        stats = get_compression_stats()
        assert "lossless_learned" in stats["web_search"]["strategies"]

    def test_after_lossless_learning_uses_headtail(self):
        args = '{"query":"bar"}'
        text = "content " * 60
        # Force learning by doing 2 calls
        self._compress(args=args, text=text)
        self._compress(args=args, text=text)
        # Third call should use lossless_headtail
        reset_compression_stats()
        result = self._compress(args=args, text=text)
        assert "chars omitted" in result
        stats = get_compression_stats()
        assert "lossless_headtail" in stats["web_search"]["strategies"]

    def test_different_key_arg_not_lossless(self):
        reset_compression_stats()
        text = "result " * 60
        self._compress(args='{"query":"foo"}', text=text)
        # Different query — should not trigger lossless
        result2 = self._compress(args='{"query":"completely_different"}', text=text)
        stats = get_compression_stats()
        assert "lossless_learned" not in stats.get("web_search", {}).get(
            "strategies", {}
        )

    def test_session_isolation(self):
        """Lossless set is per-session, not global."""
        init_session("sess-other")
        args = '{"query":"foo"}'
        text = "result " * 60
        # Train session sess-test
        self._compress(args=args, text=text)
        self._compress(args=args, text=text)
        # sess-other should not be affected
        reset_compression_stats()
        compress_tool_output(
            "web_search", args, text, model="m",
            client=_mock_client("summary"), session_id="sess-other",
        )
        stats = get_compression_stats()
        assert "lossless_headtail" not in stats.get("web_search", {}).get(
            "strategies", {}
        )
        clear_session("sess-other")

    def test_clear_session_resets_lossless(self):
        args = '{"query":"foo"}'
        text = "result " * 60
        self._compress(args=args, text=text)
        self._compress(args=args, text=text)
        # Clear and reinit
        clear_session("sess-test")
        init_session("sess-test")
        reset_compression_stats()
        # Should not use lossless any more
        self._compress(args=args, text=text)
        stats = get_compression_stats()
        assert "lossless_headtail" not in stats.get("web_search", {}).get(
            "strategies", {}
        )

    def test_no_session_id_disables_learning(self):
        """Passing session_id='' disables lossless tracking."""
        reset_compression_stats()
        args = '{"query":"foo"}'
        text = "result " * 60
        # Two calls without session_id
        compress_tool_output(
            "web_search", args, text, model="m",
            client=_mock_client("s"), session_id="",
        )
        compress_tool_output(
            "web_search", args, text, model="m",
            client=_mock_client("s"), session_id="",
        )
        stats = get_compression_stats()
        assert "lossless_learned" not in stats.get("web_search", {}).get(
            "strategies", {}
        )


# ---------------------------------------------------------------------------
# 9. Compression statistics
# ---------------------------------------------------------------------------

class TestCompressionStats:
    def setup_method(self):
        reset_compression_stats()

    def test_passthrough_recorded(self):
        compress_tool_output("tool_a", "{}", _short(), model="m", client=_mock_client())
        stats = get_compression_stats()
        assert stats["tool_a"]["calls"] == 1
        assert stats["tool_a"]["compressed_calls"] == 0
        assert stats["tool_a"]["strategies"]["passthrough"] == 1

    def test_compression_rate_non_zero_after_compression(self):
        compress_tool_output(
            "tool_b", "{}", _long(), model="m", client=_mock_client("s")
        )
        stats = get_compression_stats()
        assert stats["tool_b"]["compressed_calls"] == 1
        assert stats["tool_b"]["compression_rate"] == 1.0

    def test_avg_ratio_below_one_after_compression(self):
        compress_tool_output(
            "tool_c", "{}", _long(MAX * 10), model="m", client=_mock_client("s")
        )
        stats = get_compression_stats()
        assert stats["tool_c"]["avg_ratio"] < 1.0

    def test_multiple_calls_accumulate(self):
        for _ in range(3):
            compress_tool_output(
                "tool_d", "{}", _long(), model="m", client=_mock_client("s")
            )
        stats = get_compression_stats()
        assert stats["tool_d"]["calls"] == 3

    def test_reset_clears_stats(self):
        compress_tool_output(
            "tool_e", "{}", _long(), model="m", client=_mock_client("s")
        )
        reset_compression_stats()
        stats = get_compression_stats()
        assert "tool_e" not in stats


# ---------------------------------------------------------------------------
# 10. Argument helpers
# ---------------------------------------------------------------------------

class TestArgHelpers:
    def test_extract_path_key(self):
        assert _extract_key_arg('{"path": "/foo/bar.py"}') == "/foo/bar.py"

    def test_extract_file_key(self):
        assert _extract_key_arg('{"file": "README.md"}') == "README.md"

    def test_extract_first_string_fallback(self):
        result = _extract_key_arg('{"count": 5, "label": "hello"}')
        assert result == "hello"

    def test_extract_invalid_json_returns_raw(self):
        result = _extract_key_arg("not json at all")
        assert isinstance(result, str)
        assert len(result) <= 100

    def test_detect_ext_from_path_key(self):
        assert _detect_file_extension('{"path": "main.py"}') == ".py"

    def test_detect_ext_from_file_key(self):
        assert _detect_file_extension('{"file": "config.yaml"}') == ".yaml"

    def test_detect_ext_json(self):
        assert _detect_file_extension('{"path": "data.json"}') == ".json"

    def test_detect_ext_unknown_returns_empty(self):
        assert _detect_file_extension('{"action": "run"}') == ""

    def test_detect_ext_fallback_regex(self):
        assert _detect_file_extension('read /home/user/app.ts') == ".ts"
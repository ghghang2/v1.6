"""Single executor for all tool calls."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any, Dict
import json

from nbchat.tools import TOOLS

_executor = ThreadPoolExecutor(max_workers=4)

MAX_TOOL_OUTPUT_CHARS = 6000


def trim_tool_output(result: str, max_chars: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    """Trim large tool outputs to keep them within context budget.

    Keeps the first and last halves of the output so both the beginning
    (often the most structured part) and the end (often the result) are
    preserved.
    """
    if len(result) <= max_chars:
        return result
    half = max_chars // 2
    removed = len(result) - max_chars
    return (
        result[:half]
        + f"\n[...{removed} chars trimmed — output too large for context window...]\n"
        + result[-half:]
    )


def run_tool(tool_name: str, args_json: str, timeout: int | None = None) -> str:
    """Execute a tool with arguments and return the (trimmed) string result."""
    try:
        args = json.loads(args_json)
    except Exception as e:
        return f"❌ Failed to parse tool arguments: {e}"

    func = next((t.func for t in TOOLS if t.name == tool_name), None)
    if not func:
        return f"⚠️ Unknown tool '{tool_name}'"

    if timeout is None:
        timeout = 60 if tool_name in ["browser", "run_tests"] else 30

    future = _executor.submit(func, **args)
    try:
        result = future.result(timeout=timeout)
        return trim_tool_output(str(result))
    except TimeoutError:
        return f"⏰ Tool '{tool_name}' timed out after {timeout} seconds."
    except Exception as e:
        return f"❌ Tool execution error: {e}"


__all__ = ["run_tool", "trim_tool_output"]
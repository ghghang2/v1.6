"""Single executor for all tool calls."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any, Dict
import json

from nbchat.tools import TOOLS
from nbchat.core.retry import retry_with_backoff, DEFAULT_MAX_RETRIES

_executor = ThreadPoolExecutor(max_workers=4)

from nbchat.core.config import MAX_TOOL_OUTPUT_CHARS


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
    """Execute a tool with arguments and return the (trimmed) string result.
    
    Includes retry policy inspired by openclaw (https://docs.openclaw.ai/concepts/retry).
    """
    try:
        args = json.loads(args_json)
    except Exception as e:
        return f"Failed to parse tool arguments: {e}"

    func = next((t.func for t in TOOLS if t.name == tool_name), None)
    if not func:
        return f"Unknown tool '{tool_name}'"

    if timeout is None:
        timeout = 60 if tool_name in ["browser", "run_tests"] else 30

    def execute_with_retry() -> str:
        """Execute tool with retry logic."""
        future = _executor.submit(func, **args)
        try:
            result = future.result(timeout=timeout)
            return str(result)
        except TimeoutError:
            raise TimeoutError(f"Tool '{tool_name}' timed out after {timeout} seconds.")
        except Exception as e:
            raise Exception(f"Tool execution error: {e}")
    
    # Execute with retry policy
    try:
        result = retry_with_backoff(
            execute_with_retry,
            max_retries=DEFAULT_MAX_RETRIES,
            initial_delay=1.0,
            max_delay=10.0,
        )
        return result
    except Exception as e:
        return f"Tool '{tool_name}' failed after {DEFAULT_MAX_RETRIES} retries: {e}"


__all__ = ["run_tool", "trim_tool_output"]
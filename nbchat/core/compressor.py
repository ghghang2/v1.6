"""Tool output compressor.

Compresses individual tool outputs via a quick LLM call before they are
stored in history or sent to the model.  This is the primary mechanism
for keeping token usage bounded during long agentic loops.
"""
from __future__ import annotations

import logging
from typing import Optional

_log = logging.getLogger("nbchat.compaction")
if not _log.handlers:
    import logging.handlers
    _h = logging.FileHandler("compaction.log", mode="a")
    _h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    _log.addHandler(_h)
    _log.setLevel(logging.DEBUG)

# Tool outputs shorter than this are kept verbatim — no LLM call needed.
COMPRESS_THRESHOLD_CHARS = 800


def compress_tool_output(
    tool_name: str,
    tool_args: str,
    result: str,
    model: str,
    client,
) -> str:
    """Return a compressed version of *result*.

    If the output is short enough it is returned unchanged.
    Otherwise an LLM call extracts only the relevant information.
    If the output contains nothing relevant the sentinel string
    ``NO_RELEVANT_OUTPUT`` is returned so the caller can decide
    whether to store a placeholder or drop the row.
    """
    if len(result) <= COMPRESS_THRESHOLD_CHARS:
        return result

    _log.debug(
        f"compress_tool_output: {tool_name} output is {len(result)} chars, compressing"
    )

    # Truncate the raw result sent to the compressor so the compressor
    # call itself cannot overflow the context window.
    max_raw = 12_000
    truncated = result[:max_raw] + (
        f"\n[...{len(result) - max_raw} chars truncated for compression...]"
        if len(result) > max_raw else ""
    )

    prompt = (
        f"Tool called: {tool_name}\n"
        f"Arguments: {tool_args}\n"
        f"Output:\n{truncated}\n\n"
        "Extract only the information from this output that is relevant to "
        "the ongoing task. Be concise — a few sentences or a short list is "
        "enough. Preserve exact values like file paths, line numbers, error "
        "messages, and function names.\n"
        "If the output contains NO information relevant to the task "
        "(e.g. it is empty, a confirmation with no data, or pure noise), "
        "respond with exactly the word: NO_RELEVANT_OUTPUT\n"
        "Write only the extracted information, no preamble."
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
        )
        compressed = response.choices[0].message.content.strip()
        _log.debug(
            f"compress_tool_output: {tool_name} compressed "
            f"{len(result)} -> {len(compressed)} chars"
        )
        return compressed
    except Exception as e:
        _log.debug(f"compress_tool_output: LLM call failed ({e}), using truncation fallback")
        # Fall back to simple head+tail truncation.
        half = COMPRESS_THRESHOLD_CHARS // 2
        return (
            result[:half]
            + f"\n[...{len(result) - COMPRESS_THRESHOLD_CHARS} chars omitted...]\n"
            + result[-half:]
        )


__all__ = ["compress_tool_output", "COMPRESS_THRESHOLD_CHARS"]
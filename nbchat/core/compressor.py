"""Tool output compressor.

Compresses individual tool outputs via a quick LLM call before they are
stored in messages sent to the model.  This keeps token usage bounded
during long agentic loops without losing critical information.

New in this revision:
  • Syntax-aware truncation — Python (AST), JSON, YAML, JS/TS (regex) files
    get structural skeleton extraction instead of blind head+tail, giving
    the model function signatures and key names rather than just the first N
    and last N characters.
  • Session-local lossless learning — if the model requests the same tool
    call a second time within a session after it was compressed, that is a
    signal the compression lost signal.  The tool is added to a per-session
    lossless set and always receives head+tail treatment for the rest of the
    session, eliminating the re-read loop.
  • Compression statistics — per-tool call counts, compression ratios, and
    strategy breakdowns are tracked in memory and accessible via
    get_compression_stats().  Use these to tune MAX_TOOL_OUTPUT_CHARS and
    ALWAYS_KEEP_TOOLS without guessing.
"""
from __future__ import annotations

import ast
import json
import logging
import re
from collections import deque, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config import MAX_TOOL_OUTPUT_CHARS

_log = logging.getLogger("nbchat.compaction")
if not _log.handlers:
    _h = logging.FileHandler("compaction.log", mode="a")
    _h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    _log.addHandler(_h)
    _log.setLevel(logging.DEBUG)

# ── Tool sets ─────────────────────────────────────────────────────────────────

# File-read tools benefit from syntax-aware skeleton extraction.
FILE_READ_TOOLS = frozenset({
    "read_file", "cat", "view_file", "get_file",
    "list_files", "list_directory", "tree", "glob",
})

# Command / shell tools: head+tail only — no relevance filtering.
# Filtering causes the model to re-run commands repeatedly when the
# summary is too thin to act on.
COMMAND_TOOLS = frozenset({
    "bash", "run_command", "execute",
    "sed", "awk", "head", "tail", "grep", "find",
})

# Union kept for external callers that check against the old name.
ALWAYS_KEEP_TOOLS = FILE_READ_TOOLS | COMMAND_TOOLS

# File extensions that have a structured extractor.
_STRUCTURED_EXTS = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".json", ".yaml", ".yml",
})

# Rolling window of compressed calls tracked per session for lossless detection.
_LOSSLESS_WINDOW = 10


# ── Per-session state ─────────────────────────────────────────────────────────

@dataclass
class _SessionState:
    """Mutable per-session compression state."""
    # Tool names to always treat as lossless (head+tail only) this session.
    lossless_tools: set = field(default_factory=set)
    # Ring buffer of (tool_name, key_arg) for recently compressed calls.
    recent_compressed: deque = field(
        default_factory=lambda: deque(maxlen=_LOSSLESS_WINDOW)
    )


_sessions: dict[str, _SessionState] = {}


def _get_session(session_id: str) -> _SessionState:
    if session_id not in _sessions:
        _sessions[session_id] = _SessionState()
    return _sessions[session_id]


def init_session(session_id: str) -> None:
    """Initialise (or reset) compression state for *session_id*."""
    _sessions[session_id] = _SessionState()


def clear_session(session_id: str) -> None:
    """Remove all compression state for *session_id* (call on session reset)."""
    _sessions.pop(session_id, None)


# ── Compression statistics ────────────────────────────────────────────────────

@dataclass
class _ToolStats:
    calls: int = 0
    compressed_calls: int = 0
    total_input_chars: int = 0
    total_output_chars: int = 0
    strategy_counts: dict = field(default_factory=lambda: defaultdict(int))


_stats: dict[str, _ToolStats] = defaultdict(lambda: _ToolStats())


def get_compression_stats() -> dict:
    """Return a snapshot of per-tool compression statistics.

    Returns a dict mapping ``tool_name`` →
    ``{calls, compressed_calls, compression_rate, avg_ratio, strategies}``.

    ``avg_ratio < 1.0`` means output was on average compressed.
    ``compression_rate`` is the fraction of calls that triggered compression.
    """
    result: dict = {}
    for tool_name, s in _stats.items():
        ratio = (
            s.total_output_chars / s.total_input_chars
            if s.total_input_chars else 1.0
        )
        result[tool_name] = {
            "calls": s.calls,
            "compressed_calls": s.compressed_calls,
            "compression_rate": (
                s.compressed_calls / s.calls if s.calls else 0.0
            ),
            "avg_ratio": ratio,
            "strategies": dict(s.strategy_counts),
        }
    return result


def reset_compression_stats() -> None:
    """Clear all accumulated compression statistics (useful in tests)."""
    _stats.clear()


def _record_stat(
    tool_name: str, input_len: int, output_len: int, strategy: str
) -> None:
    s = _stats[tool_name]
    s.calls += 1
    s.total_input_chars += input_len
    s.total_output_chars += output_len
    s.strategy_counts[strategy] += 1
    if output_len < input_len:
        s.compressed_calls += 1


# ── Argument helpers ──────────────────────────────────────────────────────────

def _extract_key_arg(tool_args: str) -> str:
    """Extract the primary string argument (usually a file path) from JSON tool args.

    Used as the identity key for repeat-read detection.
    """
    try:
        args = json.loads(tool_args)
        for key in ("path", "file", "filename", "filepath", "file_path", "target"):
            if key in args and isinstance(args[key], str):
                return args[key]
        # First string value as fallback
        for v in args.values():
            if isinstance(v, str):
                return v
    except Exception:
        pass
    return tool_args[:100]


def _detect_file_extension(tool_args: str) -> str:
    """Detect file extension from JSON tool arguments.

    Returns the extension (e.g. '.py') in lower case, or '' if undetectable.
    """
    try:
        args = json.loads(tool_args)
        for key in ("path", "file", "filename", "filepath", "file_path", "target"):
            val = args.get(key, "")
            if isinstance(val, str) and "." in val:
                return Path(val).suffix.lower()
    except Exception:
        pass
    # Fallback: scan raw args string for a file-path-like token
    m = re.search(r'\b[\w./\-]+(\.[a-zA-Z]{1,6})\b', tool_args)
    return m.group(1).lower() if m else ""


# ── Syntax-aware extractors ───────────────────────────────────────────────────

def _python_skeleton(source: str, max_chars: int) -> Optional[str]:
    """Extract an importable skeleton from Python source using the AST.

    Preserves: imports, top-level assignments, function/async-function
    signatures (with short docstrings), class definitions with all method
    signatures (with short docstrings).  Function bodies are replaced with
    '...'.  Returns None on SyntaxError so the caller can fall back to
    head+tail.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    lines = source.splitlines()

    def get_line(lineno: int) -> str:
        idx = lineno - 1
        return lines[idx] if 0 <= idx < len(lines) else ""

    output: list[str] = []

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            output.append(get_line(node.lineno))

        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            # Top-level constants and module-level assignments
            output.append(get_line(node.lineno))

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in node.decorator_list:
                output.append(get_line(d.lineno))
            output.append(get_line(node.lineno))
            ds = ast.get_docstring(node)
            if ds and len(ds) <= 120:
                output.append(f'    """{ds}"""')
            output.append("    ...")

        elif isinstance(node, ast.ClassDef):
            for d in node.decorator_list:
                output.append(get_line(d.lineno))
            # class Foo(Base):
            output.append(get_line(node.lineno))
            ds = ast.get_docstring(node)
            if ds and len(ds) <= 120:
                output.append(f'    """{ds}"""')
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for d in item.decorator_list:
                        output.append(f"    {get_line(d.lineno).strip()}")
                    output.append(f"    {get_line(item.lineno).strip()}")
                    ds2 = ast.get_docstring(item)
                    if ds2 and len(ds2) <= 80:
                        output.append(f'        """{ds2}"""')
                    output.append("        ...")
            output.append("")  # blank line between classes

    skeleton = "\n".join(output)
    if len(skeleton) > max_chars:
        skeleton = skeleton[:max_chars] + "\n...[skeleton truncated]"
    return f"[Python skeleton — {len(lines)} lines total]\n{skeleton}"


def _json_skeleton(text: str, max_chars: int) -> Optional[str]:
    """Summarise JSON structure: key names, value types, and counts."""
    try:
        obj = json.loads(text)
    except Exception:
        return None

    if isinstance(obj, dict):
        preview: dict = {}
        for k, v in list(obj.items())[:30]:
            if isinstance(v, dict):
                preview[k] = f"{{...{len(v)} keys}}"
            elif isinstance(v, list):
                preview[k] = f"[...{len(v)} items]"
            elif isinstance(v, str) and len(v) > 80:
                preview[k] = v[:80] + "..."
            else:
                preview[k] = v
        extra = f" ({len(obj) - 30} more keys)" if len(obj) > 30 else ""
        skeleton = (
            f"[JSON object — {len(obj)} keys{extra}]\n"
            + json.dumps(preview, indent=2)
        )
    elif isinstance(obj, list):
        first_str = (
            json.dumps(obj[0], indent=2)[:400] if obj else "(empty)"
        )
        skeleton = (
            f"[JSON array — {len(obj)} items]\n"
            f"First item:\n{first_str}"
        )
    else:
        return None

    if len(skeleton) > max_chars:
        skeleton = skeleton[:max_chars] + "\n...[truncated]"
    return skeleton


def _yaml_skeleton(text: str, max_chars: int) -> Optional[str]:
    """Extract top-level YAML keys without requiring PyYAML."""
    lines = text.splitlines()
    top_level: list[str] = []
    for line in lines:
        # Skip blank lines, comments, and indented lines
        if not line or line[0].isspace() or line.startswith("#"):
            continue
        if ":" in line:
            top_level.append(line[:120])
    if not top_level:
        return None
    skeleton = (
        f"[YAML — {len(lines)} lines, top-level keys]\n"
        + "\n".join(top_level)
    )
    if len(skeleton) > max_chars:
        skeleton = skeleton[:max_chars] + "\n...[truncated]"
    return skeleton


def _js_skeleton(text: str, max_chars: int) -> Optional[str]:
    """Extract function/class/export signatures from JS/TS using regex."""
    _top_re = re.compile(
        r'^(?:export\s+(?:default\s+)?)?'
        r'(?:async\s+)?'
        r'(?:'
        r'function\*?\s+\w+'
        r'|class\s+\w+'
        r'|const\s+\w+\s*='
        r'|let\s+\w+\s*='
        r'|var\s+\w+\s*='
        r'|interface\s+\w+'
        r'|type\s+\w+\s*='
        r'|enum\s+\w+'
        r')'
    )
    # Class methods indented 2–4 spaces
    _method_re = re.compile(
        r'^[ \t]{2,4}'
        r'(?:(?:public|private|protected|static|async|override|readonly)\s+)*'
        r'\w+\s*[(<]'
    )

    sigs: list[str] = []
    for line in text.splitlines():
        if _top_re.match(line) or _method_re.match(line):
            sigs.append(line[:120])

    if not sigs:
        return None
    total = len(text.splitlines())
    skeleton = f"[JS/TS skeleton — {total} lines]\n" + "\n".join(sigs)
    if len(skeleton) > max_chars:
        skeleton = skeleton[:max_chars] + "\n...[truncated]"
    return skeleton


def _syntax_aware_truncate(
    text: str, ext: str, max_chars: int
) -> Optional[str]:
    """Dispatch to the appropriate skeleton extractor.

    Returns None when no extractor applies or extraction fails — the caller
    should fall back to head+tail in that case.
    """
    if ext == ".py":
        return _python_skeleton(text, max_chars)
    if ext == ".json":
        return _json_skeleton(text, max_chars)
    if ext in (".yaml", ".yml"):
        return _yaml_skeleton(text, max_chars)
    if ext in (".js", ".ts", ".jsx", ".tsx"):
        return _js_skeleton(text, max_chars)
    return None


def _head_tail(text: str, max_chars: int, label: str = "") -> str:
    """Symmetric head+tail truncation preserving both ends of the output."""
    half = max_chars // 2
    omitted = len(text) - max_chars
    suffix = f" of {label} output" if label else ""
    return (
        text[:half]
        + f"\n[...{omitted} chars omitted (middle{suffix})...]\n"
        + text[-half:]
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def compress_tool_output(
    tool_name: str,
    tool_args: str,
    result: str,
    model: str,
    client,
    session_id: str = "",
) -> str:
    """Return a compressed version of *result* bounded to MAX_TOOL_OUTPUT_CHARS.

    Strategy (evaluated in priority order):

    1. Short output (≤ MAX_TOOL_OUTPUT_CHARS) — pass through unchanged.
    2. Session lossless set — tool was learned to be lossy; use head+tail,
       skip LLM/skeleton.
    3. Repeat-read detection — if this exact (tool_name, key_arg) was
       compressed recently, the model is re-requesting it because the
       compression lost information.  Add to session lossless set and return
       head+tail immediately.
    4. File-read tool + structured extension — apply syntax-aware skeleton
       extraction (AST for Python, structural for JSON/YAML/JS).
    5. File-read / command tool — head+tail truncation; no LLM, no relevance
       filtering (filtering causes re-read loops).
    6. All other tools — LLM structural compression.

    Side effects:
      • Compression statistics are updated for every call.
      • Session lossless set may be updated on repeat-read detection.

    Parameters
    ----------
    session_id:
        Pass the current session ID to enable per-session lossless learning
        and repeat-read detection.  Pass "" (default) to disable both.
    """
    input_len = len(result)

    # 1. Passthrough
    if input_len <= MAX_TOOL_OUTPUT_CHARS:
        _record_stat(tool_name, input_len, input_len, "passthrough")
        return result

    state = _get_session(session_id) if session_id else _SessionState()
    key_arg = _extract_key_arg(tool_args)

    # 2. Session lossless set (learned from prior repeat-reads this session)
    if tool_name in state.lossless_tools:
        out = _head_tail(result, MAX_TOOL_OUTPUT_CHARS, tool_name)
        _record_stat(tool_name, input_len, len(out), "lossless_headtail")
        _log.debug(
            f"compress: {tool_name} — session-lossless, "
            f"{input_len} → {len(out)} chars"
        )
        return out

    # 3. Repeat-read detection
    if session_id and (tool_name, key_arg) in state.recent_compressed:
        state.lossless_tools.add(tool_name)
        out = _head_tail(result, MAX_TOOL_OUTPUT_CHARS, tool_name)
        _record_stat(tool_name, input_len, len(out), "lossless_learned")
        _log.debug(
            f"compress: {tool_name}({key_arg!r:.40}) repeated — "
            f"marked lossless, {input_len} → {len(out)} chars"
        )
        return out

    _log.debug(f"compress: {tool_name} is {input_len} chars — compressing")

    # 4. File-read tool: try syntax-aware skeleton first
    if tool_name in FILE_READ_TOOLS:
        ext = _detect_file_extension(tool_args)
        if ext in _STRUCTURED_EXTS:
            skeleton = _syntax_aware_truncate(result, ext, MAX_TOOL_OUTPUT_CHARS)
            if skeleton is not None:
                if session_id:
                    state.recent_compressed.append((tool_name, key_arg))
                _record_stat(
                    tool_name, input_len, len(skeleton),
                    f"syntax_{ext.lstrip('.')}"
                )
                _log.debug(
                    f"compress: {tool_name} syntax-aware ({ext}) "
                    f"{input_len} → {len(skeleton)} chars"
                )
                return skeleton

        # Fallback for file reads with no structured extractor
        out = _head_tail(result, MAX_TOOL_OUTPUT_CHARS, tool_name)
        if session_id:
            state.recent_compressed.append((tool_name, key_arg))
        _record_stat(tool_name, input_len, len(out), "headtail_file")
        _log.debug(
            f"compress: {tool_name} head+tail {input_len} → {len(out)} chars"
        )
        return out

    # 5. Command tool: head+tail
    if tool_name in COMMAND_TOOLS:
        out = _head_tail(result, MAX_TOOL_OUTPUT_CHARS, tool_name)
        if session_id:
            state.recent_compressed.append((tool_name, key_arg))
        _record_stat(tool_name, input_len, len(out), "headtail_command")
        _log.debug(
            f"compress: {tool_name} head+tail {input_len} → {len(out)} chars"
        )
        return out

    # 6. LLM structural compression
    truncated_input = result[:MAX_TOOL_OUTPUT_CHARS] + (
        f"\n[...{input_len - MAX_TOOL_OUTPUT_CHARS} chars truncated for compression...]"
        if input_len > MAX_TOOL_OUTPUT_CHARS else ""
    )
    prompt = (
        f"Tool called: {tool_name}\n"
        f"Arguments: {tool_args}\n"
        f"Output:\n{truncated_input}\n\n"
        "Summarise this output concisely. Preserve:\n"
        "- All function/class/method signatures and names\n"
        "- Key error messages and stack traces verbatim\n"
        "- File paths and line numbers\n"
        "- Any values explicitly returned or printed\n"
        "Omit only: blank lines, boilerplate comments, and large repeated blocks.\n"
        "If the output is empty or a bare confirmation (e.g. 'OK', 'None', ''), "
        "respond with exactly: NO_RELEVANT_OUTPUT\n"
        "Write only the summary, no preamble."
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=MAX_TOOL_OUTPUT_CHARS,
        )
        out = response.choices[0].message.content.strip()
        if session_id:
            state.recent_compressed.append((tool_name, key_arg))
        _record_stat(tool_name, input_len, len(out), "llm")
        _log.debug(
            f"compress: {tool_name} LLM {input_len} → {len(out)} chars"
        )
        return out
    except Exception as exc:
        _log.debug(f"compress: LLM failed ({exc}), falling back to head+tail")
        out = _head_tail(result, MAX_TOOL_OUTPUT_CHARS, tool_name)
        _record_stat(tool_name, input_len, len(out), "headtail_llm_fallback")
        return out


__all__ = [
    "compress_tool_output",
    "get_compression_stats",
    "reset_compression_stats",
    "init_session",
    "clear_session",
    "ALWAYS_KEEP_TOOLS",
    "FILE_READ_TOOLS",
    "COMMAND_TOOLS",
]
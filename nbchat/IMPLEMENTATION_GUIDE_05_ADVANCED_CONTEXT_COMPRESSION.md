# Implementation Guide: Advanced Context Compression with Fact Preservation (Opportunity 5)

> **Prerequisites:** Basic Python knowledge, familiarity with nbchat's codebase, understanding of LLM-based summarization.
> **Estimated time:** 2–3 days (including testing and iteration).
> **Source:** Meta-Harness "Context Compression" approach with fact preservation.
> **⚠️ CRITICAL NOTE:** This guide has been corrected. The original guide proposed creating a new `fact_extractor.py` module, which would add complexity. This fixed version instead ENHANCES the existing `compressor.py` with fact preservation logic, keeping everything in one place.

---

## 1. Goal

Enhance nbchat's context compression to preserve key facts, decisions, and tool outputs during summarization, going beyond naive truncation.

**⚠️ IMPORTANT DECISION:** Before implementing, ask yourself:

1. **Is this actually needed?** Nbchat's `compressor.py` already has syntax-aware skeleton extraction for py/json/yaml/js files. The question is whether we need LLM-based fact extraction.

2. **What's the complexity cost?** LLM-based fact extraction adds:
   - An extra API call per compression
   - New failure modes (LLM might fail to extract facts)
   - New prompts to maintain

3. **Is it worth it?** For now, the existing syntax-aware skeleton extraction is probably sufficient. Add LLM-based fact extraction only if you see evidence that critical information is being lost.

**Recommendation:** Enhance the existing `compressor.py` with better fact preservation rules. Don't add LLM-based fact extraction unless you have a compelling use case.

---

## 2. Background: How Nbchat Currently Handles Context Compression

Nbchat currently implements **sliding window + LLM-based summarization** in `compressor.py`:

- When the token budget is exceeded, the compressor summarizes older conversation turns.
- The compressor already has syntax-aware skeleton extraction for py/json/yaml/js files.
- However, it doesn't explicitly preserve key facts, decisions, or tool outputs.

### Key files to understand:
| File | Purpose |
|------|---------|
| `nbchat/core/compressor.py` | Token-bounded context compression (sliding window + summarization) |
| `nbchat/core/config.py` | Application-wide configuration (model, API keys, tools, memory) |
| `nbchat/core/db.py` | SQLite persistence: chat history, memory, episodes, tool outputs |

---

## 3. Architecture Overview

```
nbchat/core/
├── compressor.py      # Enhanced with fact preservation
└── ...
```

**⚠️ DESIGN DECISION:** We are NOT creating a new `fact_extractor.py` module. Instead, we enhance `compressor.py` with better fact preservation logic. This keeps the change minimal and avoids adding a new module.

---

## 4. Step-by-Step Implementation

### Step 1: Enhance the Compressor with Fact Preservation

**File:** `nbchat/core/compressor.py`

Add fact preservation logic to the existing `compress_tool_output` function.

```python
# Add these functions to nbchat/core/compressor.py

def _extract_facts_from_tool_output(tool_name: str, tool_args: str, result: str) -> dict:
    """Extract key facts from a tool output.

    This is a rule-based extractor that identifies important information
    without requiring an LLM call.

    Args:
        tool_name: Name of the tool that produced the output.
        tool_args: Arguments passed to the tool.
        result: The tool output.

    Returns:
        Dictionary with extracted facts.
    """
    facts = {
        "tool": tool_name,
        "facts": [],
        "errors": [],
        "decisions": [],
    }

    # Extract error messages
    error_patterns = [
        r"Error[:\s]+(.+)",
        r"Exception[:\s]+(.+)",
        r"Traceback\(most recent call last\):(.+?)(?:\n\n|\Z)",
        r"FAILED[:\s]+(.+)",
        r"ERROR[:\s]+(.+)",
    ]
    for pattern in error_patterns:
        matches = re.findall(pattern, result, re.IGNORECASE | re.DOTALL)
        for match in matches:
            facts["errors"].append(match.strip()[:200])

    # Extract file paths
    file_patterns = [
        r"(/[\w./\-]+)",
        r"(\w+:\w+/\w+)",
    ]
    for pattern in file_patterns:
        matches = re.findall(pattern, result)
        for match in matches:
            if len(match) < 200 and match not in facts["facts"]:
                facts["facts"].append(f"File: {match}")

    # Extract line numbers
    line_patterns = [
        r"line\s+(\d+)",
        r":(\d+):",
    ]
    for pattern in line_patterns:
        matches = re.findall(pattern, result, re.IGNORECASE)
        for match in matches:
            facts["facts"].append(f"Line: {match}")

    # Extract key values (e.g., counts, sizes, IDs)
    value_patterns = [
        r"(\d+)\s+(?:items|files|lines|bytes|tokens|characters)",
        r"(?:total|found|returned|processed)[:\s]+(\d+)",
    ]
    for pattern in value_patterns:
        matches = re.findall(pattern, result, re.IGNORECASE)
        for match in matches:
            facts["facts"].append(f"Count: {match}")

    # Extract important strings (e.g., status codes, messages)
    status_patterns = [
        r"(HTTP/\d\.\d\s+\d+)",
        r"(status[:\s]+(\w+))",
        r"(response[:\s]+(\w+))",
    ]
    for pattern in status_patterns:
        matches = re.findall(pattern, result, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                facts["facts"].append(match[0])
            else:
                facts["facts"].append(match)

    return facts


def _format_facts(facts: dict) -> str:
    """Format extracted facts into a readable string.

    Args:
        facts: Dictionary with extracted facts.

    Returns:
        Formatted string with facts.
    """
    lines = []

    if facts.get("errors"):
        lines.append("Errors:")
        for error in facts["errors"][:5]:  # Limit to 5 errors
            lines.append(f"  - {error}")

    if facts.get("facts"):
        lines.append("Key Facts:")
        for fact in facts["facts"][:10]:  # Limit to 10 facts
            lines.append(f"  - {fact}")

    if facts.get("decisions"):
        lines.append("Decisions:")
        for decision in facts["decisions"][:5]:
            lines.append(f"  - {decision}")

    return "\n".join(lines) if lines else ""


def compress_tool_output_with_facts(tool_name: str, tool_args: str, result: str,
                                     model: str, client, session_id: str = "") -> str:
    """Compress tool output with fact preservation.

    This is an enhanced version of compress_tool_output that first extracts
    key facts from the output, then compresses the rest.

    Args:
        tool_name: Name of the tool that produced the output.
        tool_args: Arguments passed to the tool.
        result: The tool output.
        model: Model name for LLM summarization.
        client: LLM client for summarization.
        session_id: Session ID for tracking.

    Returns:
        Compressed output with preserved facts.
    """
    in_len = len(result)

    # If output is small, no compression needed
    if in_len <= MAX_TOOL_OUTPUT_CHARS:
        return result

    # Extract facts first
    facts = _extract_facts_from_tool_output(tool_name, tool_args, result)
    facts_text = _format_facts(facts)

    # If facts are significant, include them in the output
    if facts_text and len(facts_text) < MAX_TOOL_OUTPUT_CHARS // 2:
        # Compress the rest of the output
        compressed = _head_tail(result, MAX_TOOL_OUTPUT_CHARS - len(facts_text) - 50, tool_name)
        return f"{facts_text}\n\n{compressed}"

    # Fall back to normal compression
    return _head_tail(result, MAX_TOOL_OUTPUT_CHARS, tool_name)
```

**What this does:**
- Adds rule-based fact extraction from tool outputs.
- Extracts errors, file paths, line numbers, counts, and status codes.
- Preserves extracted facts in the compressed output.
- Falls back to normal compression if facts are not significant.

---

### Step 2: Integrate with the Existing Compressor

**File:** `nbchat/core/compressor.py`

Modify the `compress_tool_output` function to use the new fact preservation logic.

```python
# Modify the compress_tool_output function in compressor.py

def compress_tool_output(tool_name: str, tool_args: str, result: str,
                         model: str, client, session_id: str = "") -> str:
    """Compress tool output with optional fact preservation.

    Args:
        tool_name: Name of the tool that produced the output.
        tool_args: Arguments passed to the tool.
        result: The tool output.
        model: Model name for LLM summarization.
        client: LLM client for summarization.
        session_id: Session ID for tracking.

    Returns:
        Compressed output.
    """
    in_len = len(result)
    if in_len <= MAX_TOOL_OUTPUT_CHARS:
        _record(tool_name, in_len, in_len, "passthrough")
        return result

    # Use fact preservation for important tools
    if tool_name in ("read_file", "cat", "view_file", "get_file"):
        # For file reading tools, preserve file paths and content
        return compress_tool_output_with_facts(tool_name, tool_args, result, model, client, session_id)

    # Use fact preservation for error outputs
    if is_error_content(result):
        return compress_tool_output_with_facts(tool_name, tool_args, result, model, client, session_id)

    # Fall back to normal compression for other tools
    state = _sess(session_id) if session_id else {"lossless": set(), "recent": deque()}
    key = _key_arg(tool_args)

    if tool_name in state["lossless"]:
        out = _head_tail(result, MAX_TOOL_OUTPUT_CHARS, tool_name)
        _record(tool_name, in_len, len(out), "lossless_headtail")
        return out

    if session_id and (tool_name, key) in state["recent"]:
        state["lossless"].add(tool_name)
        out = _head_tail(result, MAX_TOOL_OUTPUT_CHARS, tool_name)
        _record(tool_name, in_len, len(out), "lossless_learned")
        _log.debug("compress: %s(%r) repeated — marked lossless", tool_name, key[:40])
        return out

    if tool_name in FILE_READ_TOOLS:
        ext = _file_ext(tool_args)
        if ext in _STRUCTURED_EXTS:
            sk = _syntax_skeleton(result, ext, MAX_TOOL_OUTPUT_CHARS)
            if sk is not None:
                if session_id:
                    state["recent"].append((tool_name, key))
                _record(tool_name, in_len, len(sk), f"syntax_{ext.lstrip('.')}")
                return sk
        out = _head_tail(result, MAX_TOOL_OUTPUT_CHARS, tool_name)
        if session_id:
            state["recent"].append((tool_name, key))
        _record(tool_name, in_len, len(out), "headtail_file")
        return out

    if tool_name in COMMAND_TOOLS:
        out = _head_tail(result, MAX_TOOL_OUTPUT_CHARS, tool_name)
        if session_id:
            state["recent"].append((tool_name, key))
        _record(tool_name, in_len, len(out), "headtail_command")
        return out

    # LLM summarisation
    truncated = result[:MAX_TOOL_OUTPUT_CHARS]
    if in_len > MAX_TOOL_OUTPUT_CHARS:
        truncated += f"\n[...{in_len - MAX_TOOL_OUTPUT_CHARS} chars truncated for compression...]"
    prompt = (
        f"Tool: {tool_name}\nArgs: {tool_args}\nOutput:\n{truncated}\n\n"
        "Summarise concisely. Preserve: signatures, error messages/tracebacks verbatim, "
        "file paths, line numbers, returned values. Omit: blank lines, boilerplate, repeated blocks.\n"
        "If output is empty or a bare confirmation, respond exactly: NO_RELEVANT_OUTPUT\n"
        "Write only the summary, no preamble."
    )
    try:
        resp = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prompt}], max_tokens=MAX_TOOL_OUTPUT_CHARS,
        )
        out = resp.choices[0].message.content.strip()
        if session_id:
            state["recent"].append((tool_name, key))
        _record(tool_name, in_len, len(out), "llm")
        return out
    except Exception as exc:
        _log.debug("compress: LLM failed (%s), falling back to head+tail", exc)
        out = _head_tail(result, MAX_TOOL_OUTPUT_CHARS, tool_name)
        _record(tool_name, in_len, len(out), "headtail_llm_fallback")
        return out
```

**What this does:**
- Integrates fact preservation into the existing `compress_tool_output` function.
- Uses fact preservation for file reading tools and error outputs.
- Falls back to normal compression for other tools.

---

## 5. Testing

### 5.1 Unit Tests

**File:** `tests/test_fact_extraction.py`

```python
"""Tests for fact extraction."""
import pytest
from nbchat.core.compressor import _extract_facts_from_tool_output, _format_facts


def test_extract_errors():
    """Test error extraction from tool output."""
    result = """
Error: File not found: /path/to/file.txt
Traceback (most recent call last):
  File "script.py", line 10, in main
    raise FileNotFoundError("File not found")
"""
    facts = _extract_facts_from_tool_output("bash", '{"cmd": "cat /path/to/file.txt"}', result)
    assert len(facts["errors"]) > 0


def test_extract_file_paths():
    """Test file path extraction from tool output."""
    result = "Processing file /home/user/project/main.py on line 42"
    facts = _extract_facts_from_tool_output("read_file", '{"path": "/home/user/project/main.py"}', result)
    facts_text = _format_facts(facts)
    assert "/home/user/project/main.py" in facts_text


def test_extract_counts():
    """Test count extraction from tool output."""
    result = "Found 15 files in directory"
    facts = _extract_facts_from_tool_output("list_files", '{"path": "/home/user/project"}', result)
    facts_text = _format_facts(facts)
    assert "15" in facts_text


def test_format_facts():
    """Test fact formatting."""
    facts = {
        "errors": ["Error: File not found"],
        "facts": ["File: /path/to/file.txt", "Line: 42"],
        "decisions": ["Decision: Use backup file"],
    }
    formatted = _format_facts(facts)
    assert "Errors:" in formatted
    assert "Key Facts:" in formatted
    assert "Decisions:" in formatted


def test_format_empty_facts():
    """Test formatting empty facts."""
    facts = {"errors": [], "facts": [], "decisions": []}
    formatted = _format_facts(facts)
    assert formatted == ""
```

---

## 6. Usage

### 6.1 Basic Usage

The fact preservation is automatically used by `compress_tool_output` for file reading tools and error outputs:

```python
from nbchat.core.compressor import compress_tool_output

# Compress tool output with fact preservation
compressed = compress_tool_output(
    tool_name="read_file",
    tool_args='{"path": "/path/to/file.txt"}',
    result=large_file_content,
    model="qwen3.5-35b",
    client=client,
    session_id="session_123",
)
print(compressed)
```

### 6.2 Monitoring Compression Performance

```python
from nbchat.core.compressor import get_compression_stats

stats = get_compression_stats()
for tool, tool_stats in stats.items():
    print(f"{tool}: {tool_stats['compression_rate']:.2%} compression rate")
```

---

## 7. Common Pitfalls

1. **Over-extraction:** Rule-based fact extraction may extract too much or too little. Tune the extraction patterns based on your use case.

2. **Performance:** Fact extraction adds overhead to compression. For high-throughput scenarios, consider disabling fact extraction.

3. **Accuracy:** Rule-based extraction is not perfect. Critical facts may be missed. If this is a concern, consider LLM-based fact extraction.

4. **Output size:** Preserving facts increases the output size. Ensure the compressed output still fits within the token budget.

5. **Maintenance:** Extraction patterns may need to be updated as tool outputs change. Keep the patterns up to date.

---

## 8. Success Criteria

- [ ] All unit tests pass.
- [ ] Fact extraction correctly identifies errors, file paths, and counts.
- [ ] Compressed output includes preserved facts.
- [ ] Compression rate is not significantly degraded.
- [ ] No regression in existing compression functionality.

---

## Appendix: What NOT to Implement

The following approaches were considered but rejected:

1. **New `fact_extractor.py` module:** Adding a new module adds complexity. Keep fact extraction in `compressor.py` where it belongs.

2. **LLM-based fact extraction:** LLM-based extraction adds an extra API call per compression. Use rule-based extraction for now.

3. **Persistent fact store:** Storing extracted facts in a separate database adds complexity. Keep facts in the compressed output.

4. **Separate compression pipeline:** Creating a separate compression pipeline for fact preservation adds complexity. Integrate fact preservation into the existing pipeline.

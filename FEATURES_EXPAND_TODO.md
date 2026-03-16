# Adaptive Compression and Syntax-Aware Truncation - Implementation Plan

## Overview

This document tracks the implementation of two refined features that address token efficiency and information preservation in nbchat's multi-layer context management system.

These features are derived from Compresr's Context Gateway concepts but reimagined to:
1. **Eliminate unnecessary LLM overhead** during compression
2. **Preserve actionability** while reducing token count
3. **Learn from actual usage patterns** to adapt compression behavior

Both features complement nbchat's existing L0-L2 context architecture without duplicating its responsibilities.

---

## Feature 1: Adaptive Tool Compression Learning

**Priority:** HIGH  
**Status:** To Implement

### Problem Statement

The current `ALWAYS_KEEP_TOOLS` set uses a static, coarse-grained classification. This leads to two failure modes:

1. **Over-compression:** File/command tools in `ALWAYS_KEEP_TOOLS` get head+tail truncation even when their outputs are concise and perfectly usable. This wastes tokens unnecessarily.

2. **Under-compression:** Non-tool tools (search results, API responses) may be compressed when they don't need to be, while some file tools outside `ALWAYS_KEEP_TOOLS` are aggressively compressed and then the model calls `read_file` on the same path again within 2 turns—indicating the compression was lossy for that context.

### Solution: Session-Learned Tool Tracking

Instead of a separate "expand cache," implement **adaptive compression learning** that tracks which tools produce lossy compression for the current session.

#### Core Insight

If a tool's output was compressed and the model immediately re-reads the same file/path within 2 turns, that's a strong signal the compression was lossy for that tool in that context. Add the tool to a session-local `_lossless_tools` set and skip LLM compression for it for the rest of the session.

#### Implementation

**Location:** `nbchat/core/compressor.py`

**Changes:**
1. Add session-local tracking dictionary: `_lossless_tools: Dict[str, Set[str]]` mapping `session_id` → `Set[tool_name]`
2. After compression, check if the tool is already in `_lossless_tools`:
   - If yes, skip compression entirely (return original output)
   - If no, compress as usual and check if re-read occurs within 2 turns
3. If re-read detected within 2 turns (check via `self.history` in context manager), add tool to `_lossless_tools`
4. Persist `_lossless_tools` to `session_meta` table for recovery on restart

**No new cache subsystem needed.** This reuses existing patterns:
- Session ID from context manager
- History tracking already exists in `chat_history.db`
- Metrics already logged to `compaction.log`

**Benefits:**
- Zero additional LLM calls (learning happens from existing behavior)
- No new database tables (uses existing `session_meta`)
- Immediate ROI: reduces unnecessary compression for tools that don't need it
- Self-tuning: adapts to each session's actual usage patterns

---

## Feature 2: Syntax-Aware Structural Truncation

**Priority:** HIGH  
**Status:** To Implement

### Problem Statement

The current `ALWAYS_KEEP_TOOLS` mechanism applies **head+tail truncation** to all file/command tools. This is appropriate when outputs are huge, but has critical flaws:

1. **For structured files (Python, JSON, YAML, etc.), head+tail is semantically meaningless.** The head might contain imports and the tail might contain unrelated code, while the actual actionability lies in function signatures and method definitions.

2. **The real problem the critique identifies:** "Relevance filtering causes the model to re-read files repeatedly because the summary is too thin to act on." Head+tail truncation doesn't solve this—it just makes the summary even thinner.

### Solution: Syntax-Aware Structural Extraction

For structured file types, extract the **structural skeleton** (signatures, keys, top-level definitions) rather than arbitrary head+tail segments.

#### Implementation

**Location:** `nbchat/core/compressor.py`

**New function:** `truncate_by_syntax(file_type: str, content: str, max_chars: int) -> str`

**Strategies by file type:**

1. **Python (.py):**
   - Use `ast.parse()` to extract:
     - All function/class definitions (name + signature + decorators)
     - Top-level imports
     - Module-level constants and variables
   - Drop function bodies (unless they contain errors or exceptions)
   - Result: ~60-70% token reduction while preserving callability

2. **JSON (.json, .yaml, .yml):**
   - Extract top-level keys and their types/values
   - For nested structures, recurse down to depth 2-3
   - Truncate value strings and arrays beyond length threshold
   - Result: ~50-60% token reduction while preserving schema

3. **Command outputs (.sh, .bash, grep, find, etc.):**
   - Keep head (first 100 chars)
   - Keep tail (last 100 chars)
   - Add line count: `[total: N lines, M matches]`
   - Result: ~80% reduction for large outputs, preserves context

4. **Other tools (API responses, search results, etc.):**
   - Keep existing LLM-based compression
   - Preserve: signatures, errors, paths, values
   - Result: ~70% reduction

**No LLM call for code files.** This is deterministic, fast, and requires only the `ast` module for Python.

**Fallback:** If parsing fails, fall back to head+tail truncation.

---

## Feature 3: Prefix Caching Alignment

**Priority:** CRITICAL  
**Status:** To Implement

### Problem Statement

The critique correctly identifies that **prefix caching is conspicuously absent**. The system prompt + L1 core memory + L2 episodic block are rebuilt on every turn, but their content changes slightly every turn (new entities appended, new errors added), which busts the cache on every call.

### Solution: Separate Stable/Volatile Message Blocks

**Location:** `nbchat/ui/chat_builder.py` and `nbchat/ui/context_manager.py`

**Changes:**

1. **In `build_messages()`:**
   - Split system message into two parts:
     - **Stable part:** Base system prompt + static instructions
     - **Volatile part:** L1/L2 blocks, task log (injected later)
   - Always emit stable part as `messages[0]`
   - Append volatile part as additional user/system blocks

2. **In `ContextMixin._window()`:**
   - Move L1/L2 injections and task log from `messages[0]` content into separate blocks
   - Structure:
     ```
     messages[0]: {"role": "system", "content": STABLE_PROMPT}
     messages[1]: {"role": "user", "content": "[CORE MEMORY...]"}
     messages[2]: {"role": "user", "content": "[RELEVANT PAST EVENTS...]"}
     messages[3]: {"role": "user", "content": "[PRIOR SESSION CONTEXT...]"}
     messages[4+]: conversation history
     ```

3. **Caching strategy:**
   - Hash only `messages[0]` for prefix cache
   - Volatile blocks are appended later and don't affect cache hit rate
   - Result: Significantly higher prefix cache hit rate across consecutive turns

**Benefits:**
- Eliminates cache busting from minor context updates
- Enables true incremental conversation without re-computation
- Highest-leverage improvement for token efficiency

---

## Implementation Phases

### Phase 1: Adaptive Tool Compression (Week 1)

#### Task 1.1: Add Session-Learned Lossless Tool Tracking
- [ ] Add `_lossless_tools` dictionary to compressor module
- [ ] Modify `compress_tool_output()` to check against `_lossless_tools`
- [ ] Add re-read detection in `ContextMixin` to populate `_lossless_tools`
- [ ] Persist/load from `session_meta` for recovery
- [ ] Add metrics logging to `compaction.log`

**Estimated:** 3-4 hours  
**Files:** `nbchat/core/compressor.py`, `nbchat/ui/context_manager.py`, `nbchat/core/db.py`

#### Task 1.2: Unit Tests
- [ ] Test lossless tool tracking with simulated re-reads
- [ ] Test session persistence/load
- [ ] Test edge cases (empty history, concurrent sessions)

**Estimated:** 2-3 hours

**Phase 1 Total:** 5-7 hours

---

### Phase 2: Syntax-Aware Truncation (Week 1-2)

#### Task 2.1: Implement Syntax-Aware Truncation
- [ ] Create `truncate_by_syntax()` function in `compressor.py`
- [ ] Python: Use `ast` module to extract structural skeleton
- [ ] JSON/YAML: Extract keys and recurse with depth limit
- [ ] Shell outputs: Head+tail with metadata
- [ ] Fallback to head+tail on parse failure

**Estimated:** 4-5 hours

#### Task 2.2: Integrate into Compression Pipeline
- [ ] Modify `compress_tool_output()` to call `truncate_by_syntax()` for file tools
- [ ] Preserve existing LLM compression for non-file tools
- [ ] Update logging to show strategy used

**Estimated:** 2-3 hours

#### Task 2.3: Unit Tests
- [ ] Test Python AST extraction with sample files
- [ ] Test JSON/YAML key extraction
- [ ] Test fallback behavior
- [ ] Verify token reduction matches expectations

**Estimated:** 2-3 hours

**Phase 2 Total:** 8-11 hours

---

### Phase 3: Prefix Caching Alignment (Week 2)

#### Task 3.1: Refactor Message Building
- [ ] Split system prompt into stable/volatile parts in `chat_builder.py`
- [ ] Modify `ContextMixin._window()` to inject volatile blocks separately
- [ ] Update `build_messages()` to handle multi-block system injection

**Estimated:** 3-4 hours

#### Task 3.2: Enable Prefix Caching
- [ ] Implement prefix cache hash based only on stable block
- [ ] Cache strategy: hash → message template
- [ ] Integrate with existing client calls

**Estimated:** 3-4 hours

#### Task 3.3: Unit Tests & Metrics
- [ ] Verify cache hit rate improvement
- [ ] Test with varying context lengths
- [ ] Monitor performance gains

**Estimated:** 2-3 hours

**Phase 3 Total:** 8-11 hours

---

## Testing Plan

### Unit Tests
- [ ] Adaptive compression learning (re-read detection)
- [ ] Syntax-aware truncation (Python, JSON, YAML, shell)
- [ ] Prefix caching alignment (stable/volatile separation)
- [ ] Fallback behavior for all edge cases

### Integration Tests
- [ ] End-to-end compression with adaptive learning
- [ ] End-to-end syntax-aware truncation with various file types
- [ ] Context manager integration with prefix caching

### Performance Tests
- [ ] Token reduction metrics per strategy
- [ ] Cache hit rate before/after alignment
- [ ] Latency impact of syntax parsing vs. LLM compression

---

## Configuration Updates (`repo_config.yaml`)

Add these optional tuning knobs:

```yaml
# Adaptive compression learning
adaptive_compression:
  enabled: true
  re_read_window_turns: 2  # How many turns to watch for re-reads
  max_lossless_tools: 50   # Cap on tools marked as lossless

# Syntax-aware truncation
syntax_truncation:
  enabled: true
  python:
    max_function_bodies: 0  # 0 = drop all, -1 = keep all
    max_body_chars: 500     # Truncate body text beyond this
  json:
    max_depth: 3            # Nesting depth for key extraction
    max_value_chars: 200    # Truncate string values
  shell:
    head_chars: 100
    tail_chars: 100

# Prefix caching
prefix_caching:
  enabled: true
  stable_prompt_keys_only: true  # Only cache if stable prompt matches
```

---

## Metrics to Track

### Adaptive Compression Learning Metrics
- Number of tools marked as lossless per session
- Compression ratio for lossless vs. non-lossless tools
- Re-read rate (tools re-read within window)
- Token savings from avoiding unnecessary compression

### Syntax-Aware Truncation Metrics
- Token reduction by file type
- Parsing success rate (ast failures, JSON parse errors)
- Fallback rate (when syntax parsing fails)
- Comparison: syntax vs. head+tail vs. LLM compression

### Prefix Caching Metrics
- Cache hit rate by message block
- Time saved from cache hits
- Prefix hash collision rate
- Volatile block size distribution

---

## Rollback Plan

If issues arise:
1. **Adaptive compression:** Disable learning (always compress as before)
2. **Syntax truncation:** Fall back to head+tail for all tools
3. **Prefix caching:** Merge stable/volatile back into single system message

All changes are backwards compatible and can be disabled via configuration.

---

## Dependencies

- `nbchat/core/config.py` - For configuration handling
- `nbchat/core/db.py` - For session_meta persistence
- `nbchat/ui/context_manager.py` - For history tracking and re-read detection
- `nbchat/ui/chat_builder.py` - For message structure modifications
- `nbchat/core/compressor.py` - Core compression logic

---

## Success Criteria

1. **Adaptive Compression Learning:**
   - [ ] Tools correctly identified as lossless after re-read
   - [ ] Session persistence works (recovery on restart)
   - [ ] Metrics show reduced unnecessary compression
   - [ ] Tests pass

2. **Syntax-Aware Truncation:**
   - [ ] Python AST extraction preserves signatures
   - [ ] JSON/YAML key extraction maintains schema
   - [ ] Fallback to head+tail on parse failure
   - [ ] Token reduction >50% for large structured files
   - [ ] Tests pass

3. **Prefix Caching Alignment:**
   - [ ] Stable prompt never modified across turns
   - [ ] Cache hit rate >50% for consecutive turns
   - [ ] Volatile blocks injected correctly
   - [ ] No regression in conversation quality
   - [ ] Tests pass

---

## Summary of Changes from Original TODO

| Original Feature | New Implementation | Rationale |
|-----------------|-------------------|-----------|
| Expand cache (SQLite-backed TTL) | Adaptive compression learning (session-local dict) | Eliminates cache complexity; learns from actual behavior rather than assuming retrieval |
| Intent-aware filtering (regex classifier) | Syntax-aware structural truncation | Deterministic, no LLM overhead, preserves actionability |
| Compression ratio metrics (logging only) | Adaptive learning + per-strategy metrics | Metrics inform actual learning decisions, not just observation |
| (Missing) | Prefix caching alignment | Highest-leverage improvement; was conspicuously absent from original TODO |

---

*Last Updated: 2026-03-16*
*Status: Design complete, implementation ready to begin*

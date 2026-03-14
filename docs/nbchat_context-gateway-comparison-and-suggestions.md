# NBChat Context Gateway Comparison and Implementation Suggestions

## Executive Summary

This document compares the **Context Gateway** technology (developed by Compresr) with the current **nbchat** implementation, and provides detailed recommendations for enhancing nbchat's context management capabilities.

### Key Findings

1. **nbchat already implements sophisticated context management** with a multi-layered approach (L0-L2)
2. **Context Gateway offers additional optimizations** that could complement nbchat's existing architecture
3. **Key integration opportunities** include: intent-aware compression, SLM-based preprocessing, and proactive compaction triggers

---

## Part 1: Technology Overview

### Context Gateway (Compresr)

**Core Philosophy:**
- Sits between AI coding agents and LLM as a transparent proxy
- Compresses tool outputs before they enter the context window
- Uses small language models (SLMs) to detect signal vs. noise

**Key Features:**
1. **Tool Output Compression:**
   - Trained classifiers analyze context to identify relevant parts
   - Compression conditioned on tool call intent (e.g., if `grep` searches for error patterns, only keep relevant matches)
   - Latency: <0.5s per compression

2. **Two-Stage Compression:**
   - Stage 1: Per-step tool output compression (prevents cache invalidation during runs)
   - Stage 2: Background compaction triggered at 85% window capacity

3. **Expand-on-Demand:**
   - Compressed content can be retrieved via `expand()` if the model needs more detail

4. **Additional Features:**
   - Spending caps and cost tracking
   - Dashboard for monitoring sessions
   - Slack pings when agents wait for human input

**Technical Implementation:**
- Python-based proxy with Go backend components
- Uses SLMs (likely 1B parameter range locally) for compression
- Maintains cache of original outputs for expansion

---

### NBChat Current Implementation

**Core Architecture:**
- Multi-tier context management system (L0-L2)
- Sliding window for recent turns
- Episodic SQLite store for important exchanges
- Importance-scored hard trim with L2 write-before-drop

**Key Components:**

1. **L0 Sliding Window:**
   - Last `WINDOW_TURNS` user turns kept verbatim in hot buffer
   - Configurable via `repo_config.yaml`

2. **L1 Core Memory:**
   - Persistent slots: goal, constraints, active entities, error history
   - Injected as dedicated system block on every call
   - Limits: 20 active entities, 5 error history entries

3. **L2 Episodic Store:**
   - Append-only SQLite log of tool exchanges
   - Tagged with entity refs and importance scores
   - Retrieved and injected before window fill

4. **Prior Context Summarization:**
   - Turns that slid off are summarized per-turn by LLM
   - Structured GOAL/ENTITIES/RATIONALE format
   - Injected as system block

5. **Importance-Scored Hard Trim:**
   - Exchanges scored from 0.0-10.0
   - Those above L2_WRITE_THRESHOLD (default 3.5) persisted before eviction
   - Token budget enforced at 85% of threshold

6. **Tool Output Compressor:**
   - File/command tools: head+tail truncation (no LLM call)
   - Other tools: LLM-based summary preserving structure
   - Max output: `MAX_TOOL_OUTPUT_CHARS` (default 16384)
   - Always-keep tools: read_file, cat, grep, find, ls, etc.

**Technical Implementation:**
- Python-based with SQLite storage
- Uses OpenAI-compatible API for LLM calls
- Metrics logging via file handlers
- Task log maintained separately

---

## Part 2: Comparative Analysis

### Similarities

| Feature | Context Gateway | NBChat |
|---------|----------------|--------|
| Tool output compression | ✅ SLM-based | ✅ LLM-based |
| Per-step compression | ✅ | ✅ |
| Importance scoring | ✅ | ✅ |
| Episodic/persistent store | ✅ Cache | ✅ SQLite L2 |
| Proactive compaction trigger | ✅ 85% capacity | ✅ Token budget at 85% |
| Expand on demand | ✅ | ❌ |

### Differences

| Feature | Context Gateway | NBChat |
|---------|----------------|--------|
| Compression model | SLM (local) | LLM (API) |
| Intent-aware filtering | ✅ Yes | ❌ No |
| Expand on demand | ✅ Yes | ❌ No |
| Background compaction | ✅ Continuous | ❌ On-demand |
| Tool description lazy loading | ✅ Yes | ❌ No |
| Spending/cost tracking | ✅ Yes | ✅ Metrics logging |
| Storage mechanism | Cache | SQLite |
| Multi-layer context | ❌ N/A | ✅ L0-L2 system |
| Entity extraction | ✅ Yes | ✅ Yes |
| Structured summarization | ✅ Yes | ✅ GOAL/ENTITIES/RATIONALE |

---

## Part 3: Recommendations

### High Priority (Quick Wins)

#### 1. Add Expand-on-Demand Mechanism

**Problem:** Currently, once content is truncated or compressed, it cannot be retrieved if the model needs more detail.

**Suggestion:**
- Implement a simple in-memory or SQLite-backed cache of original outputs
- Add an `expand()` method that retrieves original content by tool_call_id
- Store metadata (original size, compression ratio) alongside compressed content

**Implementation Steps:**
```python
# In nbchat/core/compressor.py

class OutputCompressor:
    def __init__(self):
        self._cache = {}  # tool_call_id -> {"original": str, "compressed": str, "metadata": {...}}
    
    def compress(self, tool_name, tool_args, result, tool_call_id):
        # ... existing compression logic ...
        self._cache[tool_call_id] = {
            "original": result,
            "compressed": compressed,
            "tool_name": tool_name,
            "metadata": {"original_size": len(result), "compressed_size": len(compressed)}
        }
    
    def expand(self, tool_call_id):
        if tool_call_id in self._cache:
            return self._cache[tool_call_id]["original"]
        return None
```

**Benefits:**
- Allows model to request more detail when needed
- Prevents information loss
- Minimal implementation effort

---

#### 2. Add Intent Detection for File/Command Tools

**Problem:** Currently, file and command tools always use head+tail truncation, even when the output is clearly irrelevant to the current task.

**Suggestion:**
- Add a lightweight intent classifier that analyzes the tool call arguments
- For `grep` with pattern matching, identify keywords and filter output accordingly
- For file reads, check if the file is related to current context entities

**Implementation Steps:**
```python
# In nbchat/core/compressor.py

def filter_grep_output(grep_pattern: str, file_content: str) -> str:
    """Filter grep output to keep only lines matching the intent."""
    # Extract keywords from grep pattern
    keywords = re.findall(r'["\']([^"\']+)["\']', grep_pattern)
    if not keywords:
        # Fall back to head+tail
        return head_tail_truncate(file_content)
    
    # Keep only lines with relevant keywords
    lines = file_content.split('\n')
    relevant_lines = [
        line for line in lines
        if any(kw in line.lower() for kw in [k.lower() for k in keywords])
    ]
    
    return '\n'.join(relevant_lines[:MAX_TOOL_OUTPUT_CHARS])
```

**Benefits:**
- More aggressive compression without information loss
- Faster compression (regex vs LLM call)
- Better signal-to-noise ratio in context

---

### Medium Priority (Enhanced Functionality)

#### 3. Implement SLM-Based Pre-Compression

**Problem:** Current tool output compression uses an LLM call for non-file tools, which adds latency and cost.

**Suggestion:**
- Add support for running SLMs locally for pre-compression
- Use a small model (e.g., 1B parameter) that can run efficiently
- Fall back to LLM-based compression if SLM is unavailable

**Implementation Steps:**
```python
# In nbchat/core/compressor.py

def try_slm_compression(tool_name, result):
    """Try SLM-based compression if available."""
    try:
        from nbchat.core.slms import ContextAwareSLM
        slm = ContextAwareSLM.get_instance()
        return slm.compress(tool_name, result)
    except ImportError:
        # SLM not available, use LLM fallback
        return llm_compress(tool_name, result)
```

**Benefits:**
- Faster compression (<0.5s vs several seconds for LLM)
- Lower cost (local vs API)
- Can run without internet connection

---

#### 4. Add Background Compaction with Lazy Loading

**Problem:** Currently, compaction only happens when token budget is exceeded.

**Suggestion:**
- Implement background compaction that runs periodically
- Keep original outputs lazily loaded in memory
- Pre-compute summaries for future retrieval

**Implementation Steps:**
```python
# In nbchat/core/compactor.py

class BackgroundCompactor:
    def __init__(self):
        self._trigger_threshold = 0.85  # 85% capacity
        self._lazy_cache = {}  # tool_call_id -> lazy_loader
    
    def run_background_compaction(self, current_token_count, max_tokens):
        if current_token_count / max_tokens > self._trigger_threshold:
            self._compress_and_cache()
    
    def _compress_and_cache(self):
        """Compress and cache oldest eligible exchanges."""
        # Get oldest exchanges not already compressed
        exchanges = self._db.get_oldest_exchanges(limit=50)
        for exchange in exchanges:
            compressed = self._compress(exchange)
            self._cache[exchange.id] = compressed
```

**Benefits:**
- Proactive rather than reactive compaction
- Maintains better context quality
- Reduces peak token usage

---

#### 5. Implement Tool Description Lazy Loading

**Problem:** All tool descriptions are sent to the model regardless of relevance.

**Suggestion:**
- Maintain a registry of all available tools
- Use entity extraction to determine which tools are relevant
- Only include relevant tool descriptions in the prompt

**Implementation Steps:**
```python
# In nbchat/ui/chat_builder.py

def filter_relevant_tools(current_entities, all_tools):
    """Filter tool descriptions based on current context entities."""
    relevant = []
    for tool in all_tools:
        tool_desc = tool.description.lower()
        # Check if tool mentions any active entities
        if any(entity in tool_desc for entity in current_entities):
            relevant.append(tool)
    return relevant
```

**Benefits:**
- Reduces prompt size
- Helps model focus on relevant capabilities
- Faster prompt processing

---

### Low Priority (Future Enhancements)

#### 6. Add Cost Tracking and Spending Caps

**Suggestion:**
- Track token usage per session
- Add spending caps to prevent runaway costs
- Provide dashboard-style metrics

**Implementation:**
- Extend existing `inference_metrics.log` with cost estimation
- Add `/stop` or spending cap feature

---

#### 7. Add Structured Summarization for Episodic Store

**Suggestion:**
- Improve L2 episodic entries with structured GOAL/ENTITIES/RATIONALE format
- Better retrieval relevance

---

#### 8. Add Human-in-the-Loop Alerting

**Suggestion:**
- Detect when agent is stuck (like Context Gateway's Slack pings)
- Send notifications when human intervention may be needed

---

## Part 4: Architecture Diagram Comparison

### Context Gateway Flow

```
Agent -> Context Gateway -> [Compression Service] -> LLM
                      |
                      +-> [Expand Cache]
                      |
                      +-> [Background Compactor]
```

### NBChat Current Flow

```
Agent -> ContextManager -> [L0 Window] -> [L1 Core Memory] -> LLM
                                      |
                                      +-> [L2 Episodic Store]
                                      |
                                      +-> [Importance-Scoring]
```

### Proposed Hybrid Architecture

```
Agent -> ContextManager -> [L0 Window] -> [Compression Layer] -> LLM
                                      |      |
                                      +-> [L1 Core Memory]
                                      |
                                      +-> [L2 Episodic Store]
                                             |
                                             +-> [Background Compactor]
                                             |
                                             +-> [Expand Cache]
```

---

## Part 5: Implementation Roadmap

### Phase 1 (Week 1): Quick Wins

- [ ] Add expand-on-demand mechanism
- [ ] Add intent detection for grep/filter tools
- [ ] Add cost tracking to metrics logging

### Phase 2 (Week 2-3): Enhanced Compression

- [ ] Implement SLM-based compression option
- [ ] Add background compaction trigger
- [ ] Improve episodic store with structured summaries

### Phase 3 (Week 4): Advanced Features

- [ ] Implement tool description lazy loading
- [ ] Add human-in-the-loop alerting
- [ ] Spending caps and budget management

---

## Part 6: Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SLM compatibility issues | Medium | Medium | Fallback to LLM compression |
| Expand cache memory overhead | Low | Low | Use SQLite cache, TTL expiry |
| Intent detection false positives | Medium | Low | Conservative filtering, user feedback |
| Background compaction complexity | Medium | Medium | Start with simple trigger-based approach |

### Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Increased latency from extra compression | Medium | Low | Batch compression, async |
| Complexity in codebase | Medium | Medium | Modular design, clear interfaces |
| Backward compatibility | Low | Medium | Feature flags, opt-in |

---

## Part 7: Conclusion

NBChat already has a sophisticated context management system that addresses many of the same problems that Context Gateway does. The key differences are:

1. **NBChat's multi-layer approach (L0-L2)** is more comprehensive than Context Gateway's simpler compression model
2. **Context Gateway's SLM-based compression** is faster and more intent-aware than NBChat's LLM-based approach
3. **Context Gateway's expand-on-demand** feature is missing in NBChat and should be added
4. **Background compaction** in Context Gateway is proactive vs NBChat's reactive approach

### Recommendation

NBChat should adopt a hybrid approach:
- Keep the existing L0-L2 multi-layer context management
- Add Context Gateway's expand-on-demand mechanism
- Consider adding SLM-based compression as an option for faster/cheaper compression
- Implement proactive background compaction

The goal is not to replace nbchat's existing system but to enhance it with additional features that complement the multi-layer architecture.

---

*Generated: 2026-03-14*
*Based on analysis of Context Gateway (github.com/Compresr-ai/Context-Gateway) and nbchat repository*
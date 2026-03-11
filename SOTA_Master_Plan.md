# SOTA Autonomous Agent - Master Planning Document

## Status: Code Review Phase Complete - Ready for Implementation Phase

**Document Version**: 1.0  
**Last Updated**: Current  
**Purpose**: This is the single source of truth for all SOTA planning, progress tracking, and implementation priorities.

---

## CRITICAL WORKING PRINCIPLES

All concepts and ideas MUST include:
1. **Source references** (GitHub links, papers, documentation URLs)
2. **Sample code snippets** or implementation patterns
3. **Clear attribution** of inspiration
4. **No lazy statements** - every plan must be backed by research

**Why this matters:** Setting the right goals requires deep understanding of what SOTA implementations actually exist in the commercial and open source communities.

---

## EXECUTIVE SUMMARY

This document consolidates:
- **SOTA_Autonomous_Agent_Review.md**: Comprehensive analysis of current architecture vs SOTA patterns
- **SOTA_Review_Progress_v2.md**: Current implementation progress and immediate priorities
- **docs/compaction_review.md**: Technical review of compaction subsystem

All previous progress trackers have been consolidated into this single document.

---

## COMPLETED WORK (Checklist)

- [x] Review nbchat/ folder code
- [x] Review SOTA_Autonomous_Agent_Review.md documentation (comprehensive analysis exists)
- [x] Review openclaw project repository - FOUND at https://github.com/openclaw/openclaw
- [x] Review browser tool - proposed version already implemented in browser.py
- [x] Review context management implementation
- [x] Reviewed openclaw README, VISION, and AGENTS.md
- [x] Analyzed current implementation - tool compression is already optimized with head+tail truncation for file/command tools
- [x] Fixed browser tool - Playwright installation completed
- [x] Implemented retry policy for tool calls (openclaw-inspired)
- [x] Added error_flag field for protected exchanges
- [x] Updated context_manager.py to protect error exchanges during trimming
- [x] Implemented importance scoring for tool exchanges
- [x] Implemented hard-trim with importance-scored eviction

---

## OPEN TASKS & PRIORITIES

### PHASE 1 - Quick Wins (1-2 weeks) - HIGH PRIORITY

#### Task 1: Add error_flag field for protected exchanges
**Status**: DONE ✅  
**Priority**: HIGH (highest ROI, lowest effort)  
**Inspiration**: openclaw's protection of critical exchanges

**Implementation**:
1. Add `error_flag` field to database schema ✅
2. Set error_flag when an exchange contains error content ✅
3. Use error_flag in importance scoring to protect error exchanges during trimming ✅

**Files Modified**:
- `nbchat/core/db.py` - Added error_flag column to exchanges table
- `nbchat/core/db.py` - Updated get_episodic_store to include error_flag
- `nbchat/ui/context_manager.py` - Set error_flag during importance scoring
- `nbchat/ui/context_manager.py` - Use error_flag to protect exchanges during trim

**SOTA Reference**: openclaw uses strong defaults with operator-controlled risky paths

---

#### Task 2: Decompose flat summary into structured format (Goal, Entity Delta, Rationale)
**Status**: TODO  
**Priority**: HIGH  
**Inspiration**: openclaw's structured memory injection

**Implementation Plan**:
1. Review current summary generation in context_manager.py
2. Update LLM prompt to output structured JSON format
3. Parse and store as typed blocks: goal, entity_delta, rationale
4. Inject structured summary as dedicated system block

**Current State**:
- Existing prompt in context_manager.py already uses GOAL/, ENTITIES/, RATIONALE: format
- Need to ensure consistent parsing and storage

**SOTA Reference**:
- openclaw: "structured summary injected as a dedicated system block on every call"
- Reference: https://docs.openclaw.ai/concepts/memory

---

#### Task 3: Implement action verification mechanism
**Status**: TODO  
**Priority**: HIGH  
**Inspiration**: openclaw's plugin verification and state tracking

**Implementation Plan**:
1. Add verification step after tool execution
2. Compare expected vs actual state changes
3. Log verification results for audit trail
4. Implement rollback on verification failure

**SOTA Reference**:
- openclaw: "Plugin verification" ensures plugin state is consistent after execution

---

#### Task 4: Add progress tracking for long-running tasks
**Status**: TODO  
**Priority**: MEDIUM  
**Inspiration**: openclaw's presence & typing indicators

**Implementation Plan**:
1. Add progress_updates to task_log entries
2. Emit periodic status updates during long operations
3. Track intermediate states and partial results
4. Enable user visibility into agent progress

**SOTA Reference**:
- openclaw: "Presence & Typing Indicators - Real-time status updates across channels"
- Reference: https://docs.openclaw.ai/concepts/presence

---

### PHASE 1b - openclaw-inspired Improvements (1-2 weeks)

#### Task 5: Implement retry policy for tool calls
**Status**: DONE ✅  
**Inspiration**: openclaw retry mechanisms

#### Task 6: Add model failover configuration
**Status**: TODO  
**Priority**: HIGH impact, MEDIUM effort  
**Inspiration**: openclaw's automatic fallback when primary model fails

#### Task 7: Add session pruning policy
**Status**: TODO  
**Priority**: MEDIUM impact, LOW effort  
**Inspiration**: openclaw's automatic cleanup of old sessions

#### Task 8: Implement presence tracking for long-running tasks
**Status**: TODO  
**Priority**: MEDIUM impact, MEDIUM effort  
**Inspiration**: openclaw's real-time status updates across channels

#### Task 9: Add security model improvements (operator-controlled risky paths)
**Status**: TODO  
**Priority**: HIGH impact, MEDIUM effort  
**Inspiration**: openclaw security model  
**Reference**: https://github.com/openclaw/openclaw/blob/main/SECURITY.md

---

### PHASE 2 - Structured External Store (2-4 weeks)

#### Task 10: Implement Core Memory blocks as typed JSON
**Status**: TODO  
**Priority**: MEDIUM  
**Inspiration**: openclaw's plugin-based memory system

#### Task 11: Implement Episodic store with SQLite
**Status**: PARTIALLY DONE (existing SQLite store exists)  
**Priority**: MEDIUM

#### Task 12: Wire structured summary to entity deltas
**Status**: TODO  
**Priority**: MEDIUM

---

### PHASE 3 - Advanced Features (4-8 weeks)

#### Task 13: Implement plugin architecture for memory system
**Status**: TODO  
**Priority**: LOW  
**Inspiration**: openclaw plugin system

#### Task 14: Add multi-channel support
**Status**: TODO  
**Priority**: LOW  
**Inspiration**: openclaw gateway control plane

---

## OPENCLAW PROJECT INFORMATION

The openclaw project exists and is publicly available:
- **Repository**: https://github.com/openclaw/openclaw
- **Stars**: 294,389 (very active, high adoption)
- **Description**: "Your own personal AI assistant. Any OS. Any Platform. The lobster way."

**Key Architecture Patterns**:
1. **Gateway Control Plane** - Central control plane (ws://127.0.0.1:18789) that routes messages from multiple channels
2. **Multi-Platform Support** - Native nodes for iOS, Android, macOS with Canvas, Voice Wake, Talk Mode
3. **Plugin Architecture** - Core stays lean; optional capability ships as plugins
4. **MCP Support** - Uses `mcporter` bridge for MCP integration
5. **Skills Platform** - Bundled, managed, and workspace skills
6. **Security Model** - Strong defaults without killing capability

**SOTA Patterns to Learn From**:
1. **Channel Routing** - Unified routing from multiple messaging channels through gateway
2. **Retry Policy** - Built-in retry mechanisms with streaming/chunking
3. **Presence & Typing Indicators** - Real-time status updates across channels
4. **Model Failover** - Automatic fallback when primary model fails
5. **Session Pruning** - Automatic cleanup of old sessions
6. **Doctor Migrations** - Built-in diagnostics and repair tools
7. **Remote Gateway Control** - Tailscale Serve/Funnel or SSH tunnels

---

## KNOWN ISSUES & FAILURE MODES

### Issue: Streaming Tool Call Index Mismatch

**Symptom**: `APIError: Invalid diff: now finding less tool calls!`

**Root Cause**: The model predicts multiple tool calls in the initial streaming tokens, then changes its mind and reduces the number of tool calls.

**Current Mitigation**: Added tracking of tool call indices and automatic reset when mismatch is detected.

**Long-term Fix Needed**:
1. Implement model-level retry with adjusted prompts
2. Add tool call validation before streaming
3. Consider using non-streaming mode for tool calls
4. Implement graceful degradation when tool call prediction fails

**Reference**: Known limitation in OpenAI's streaming API when models change tool call predictions mid-stream.

---

## KNOWN ISSUES FIXED

### 1. Streaming Tool Call Index Mismatch
**Problem**: When streaming tool calls, the model returns chunks with `index` fields that don't necessarily arrive in order.

**Solution**: 
- Changed `tool_buffer: dict[int, dict] = {}` to `tool_buffer: dict = {}`
- Used `setdefault` with `tc.index` as the key to properly buffer tool calls
- Reconstructed the final tool_calls list by sorting indices

**Files Modified**: `nbchat/ui/conversation.py`

---

## ARCHITECTURE STRENGTHS

1. **Robust Context Management**
   - Three-layer approach (tool compression, task log, hard trim) is well-designed
   - Deterministic task log prevents catastrophic forgetting
   - Token budget management is sophisticated and reliable

2. **Tool Execution Framework**
   - ThreadPoolExecutor for parallel tool execution
   - Automatic tool discovery via module scanning
   - Schema generation from function signatures

3. **Persistence Layer**
   - SQLite-based chat history with session management
   - Session metadata storage for context summaries and caches
   - Task log survives kernel restarts

4. **Streaming Response Handling**
   - Real-time streaming with reasoning_content support
   - Proper tool call handling in streaming chunks
   - UI rendering of intermediate states

---

## ARCHITECTURE WEAKNESSES & OPPORTUNITIES

1. **Limited Self-Reflection**
   - No mechanism for the agent to review its own actions
   - No error recovery or retry strategies
   - No learning from past failures

2. **Single-Model Dependency**
   - All operations use the same model
   - No model selection based on task complexity
   - No ensemble or verification mechanisms

3. **Limited Planning Capabilities**
   - No explicit planning phase before execution
   - No task decomposition or subgoal generation
   - Reactive rather than proactive behavior

4. **Missing Memory Systems**
   - No long-term memory across sessions
   - No knowledge base or fact storage
   - No preference learning

5. **Limited Multi-Agent Patterns**
   - No specialized agents for different tasks
   - No agent collaboration or delegation
   - No role-based specialization

---

## REFERENCES & LINKS

### OpenClaw Project
- Repository: https://github.com/openclaw/openclaw
- Vision: https://github.com/openclaw/openclaw/blob/main/VISION.md
- Docs: https://docs.openclaw.ai
- Security: https://github.com/openclaw/openclaw/blob/main/SECURITY.md
- Retry: https://docs.openclaw.ai/concepts/retry
- Model Failover: https://docs.openclaw.ai/concepts/model-failover
- Session Pruning: https://docs.openclaw.ai/concepts/session-pruning
- Presence: https://docs.openclaw.ai/concepts/presence
- Plugins: https://docs.openclaw.ai/tools/plugin.md
- MCP Support: https://github.com/steipete/mcporter
- Browser Tool: https://docs.openclaw.ai/tools/browser

### Academic References
- MemGPT: Towards LLMs as Operating Systems (Packer et al., 2023)
- Letta Memory Blocks (2024-2025)
- A-MEM: Agentic Memory for LLM Agents (Xu et al., NeurIPS 2025)
- AgeMem: Agentic Memory - Unified Long-Term and Short-Term Memory Management
- TRIM-KV: Cache What Lasts (NeurIPS 2025)
- HippoRAG: Neurobiologically Inspired Long-Term Memory (Gutierrez et al., NeurIPS 2024)

### Compaction Review
- See `docs/compaction_review.md` for detailed technical review
- Key issues: token estimation, turn grouping, core logic, maintainability

---

## NEXT ACTIONS

1. **Immediate (This Week)**:
   - [ ] Decompose flat summary into structured format (Goal, Entity Delta, Rationale)
   - [ ] Implement action verification mechanism
   - [ ] Add model failover configuration

2. **Short-term (2-4 weeks)**:
   - [ ] Implement Core Memory blocks as typed JSON
   - [ ] Wire structured summary to entity deltas
   - [ ] Add session pruning policy

3. **Long-term (4-8 weeks)**:
   - [ ] Implement plugin architecture for memory system
   - [ ] Add multi-channel support
   - [ ] Create comprehensive test suite

4. **CRITICAL RULE**:
   - **ALL NEW IDEAS MUST INCLUDE REFERENCES to SOTA implementations with links and sample code**
   - **No lazy statements - every plan must be backed by research**

---

## NOTES

- SOTA_Autonomous_Agent_Review.md provides comprehensive analysis
- openclaw project is accessible at https://github.com/openclaw/openclaw
- Browser tool is already at SOTA level and now working
- Context management is strong foundation but needs memory system improvements
- Tool compression already uses smart strategies (head+tail for file tools, LLM for others)
- openclaw does NOT use agent-hierarchy frameworks (avoid this pattern)
- openclaw uses plugin-based memory system (consider for future extensibility)
- openclaw has strong security model with operator-controlled risky paths

---

*This document consolidates all previous SOTA planning and tracking documents.*
*Previous versions have been removed to maintain a clean repository.*
## ADDITIONAL TECHNICAL DOCS

### SOTA_Autonomous_Agent_Review.md
**Purpose**: Comprehensive architecture analysis - current capabilities vs SOTA patterns
**Content**: Architecture strengths, weaknesses, opportunities, detailed refactoring plans
**Status**: KEEP - Reference document with deep analysis

### Agent_Memory_Testing_Progress.md
**Purpose**: Memory system testing strategy and progress
**Content**: Testing plans, validation scenarios, test file creation status
**Status**: KEEP - Separate focus on testing/memory

### docs/compaction_review.md
**Purpose**: Technical code review of compaction subsystem
**Content**: Token estimation, turn grouping, core logic, integration, code quality issues
**Status**: KEEP - Technical debt review for compaction

### Consolidated Files Removed (Superseded by this document):
- SOTA_Implementation_Phase_Progress.md → **REMOVED**
- SOTA_Review_Progress_v2.md → **REMOVED**
- SOTA_Agent_Review_Progress.md → **REMOVED**
- Agent_Memory_Report_Implementation_Progress.md → **REMOVED**

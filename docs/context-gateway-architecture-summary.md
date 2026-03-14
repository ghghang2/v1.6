# Context Gateway - Architecture Summary

## Overview

Context Gateway is an open-source proxy developed by Compresr (YC-backed) that sits between AI coding agents (Claude Code, Cursor, OpenClaw, etc.) and LLM APIs. It compresses tool outputs before they enter the context window to save tokens, reduce costs, and improve performance.

**Repository:** https://github.com/Compresr-ai/Context-Gateway  
**Stars:** 373  
**Language:** Go (90.9%), TypeScript (6.5%), Shell (2.3%)

## Motivation

- **Context rot problem:** As conversations grow, LLMs lose attention to earlier messages
- **Token waste:** Tool outputs like `grep` can dump thousands of tokens, most being noise
- **Performance degradation:** Long contexts show steep accuracy drops
- **Cost:** Expensive token usage with diminishing returns

**Solution:** Use small language models (SLMs) to intelligently compress tool outputs, keeping only the signal-relevant parts while preserving the ability to expand on-demand.

## Architecture

### High-Level Flow

```
AI Agent (Claude Code, etc.) 
    ↓
Context Gateway Proxy (port 18081)
    ↓
    ├─ [1] HTTP Handler (internal/gateway/handler.go)
    ├─ [2] Router (internal/gateway/router.go)
    ├─ [3] Pipes (compression/filtering)
    │   ├─ tool_output pipe: Compresses tool results
    │   └─ tool_discovery pipe: Filters irrelevant tools
    ├─ [4] Upstream LLM Provider (Anthropic, OpenAI, etc.)
    └─ [5] Expand Context Loop (when LLM needs full content)
```

### Component Breakdown

#### 1. Main Binary (`cmd/`)

**Entry Point:** `cmd/main.go`

**Commands:**
- `agent` - Launch agent with interactive TUI wizard
- `serve` - Start gateway proxy server only
- `config` - Configure gateway (TUI or browser)
- `update` - Update to latest version
- `uninstall` - Remove installation

**Subcommands:**
- `cmd/cmd/` - Main entry point for agent command
- `cmd/config_cmd.go` - Configuration management
- `cmd/onboarding.go` - User onboarding flow
- `cmd/wizard_core.go` - TUI wizard logic

#### 2. Gateway Proxy (`internal/gateway/`)

**Core File:** `internal/gateway/gateway.go`

**Main Structure:**
```go
type Gateway struct {
    config *config.Config
    router *Router
    store  store.Store
    tracker *monitoring.Tracker
    preemptive *preemptive.Manager
    costTracker *costcontrol.Tracker
    expander *tooloutput.Expander
    authMode *authFallbackStore
    ...
}
```

**Key Functions:**
- `handleProxy()` - Main request handler
- `setupRoutes()` - HTTP route registration
- `Start()` / `Shutdown()` - Lifecycle management
- `handleExpand()` - /expand endpoint for on-demand expansion

**Security:**
- SSRF protection via allowlist of LLM provider hosts
- Rate limiting
- Session isolation

#### 3. Pipes (`internal/pipes/`)

**Interface:**
```go
type Pipe interface {
    Name() string
    Strategy() string
    Enabled() bool
    Process(ctx *PipeContext) ([]byte, error)
}
```

**Pipeline Architecture:**
- Pipes are provider-agnostic
- Use adapters for content extraction/application
- Can run in parallel

**tool_output Pipe (`internal/pipes/tool_output/`):**

*Compresses tool call results*

**Flow:**
1. Extract tool outputs via adapter
2. Skip already-compressed outputs (detected by `<<<SHADOW:>>>` prefix)
3. For new outputs > minBytes threshold:
   - Use assistant's intent as query (for relevance scoring)
   - Call Compresr API or external provider
   - Cache compressed result
4. Add `<<<SHADOW:id>>>` prefix at send-time
5. Apply compressed content back via adapter

**Key Features:**
- Query-agnostic models (don't need user query)
- Query-dependent models (use assistant intent or user query)
- Structured prefix preservation (JSON/YAML/XML verbatim prefix)
- TTL-based caching (original short TTL, compressed long TTL)
- Rate limiting to avoid API floods

**Compression Strategies:**
- `StrategyCompresr` - Use Compresr API (default)
- `StrategyPassthrough` - Don't compress
- External providers (via config)

**tool_discovery Pipe (`internal/pipes/tool_discovery/`):**

*Filters irrelevant tools from tool definitions*

- Uses hybrid search fallback
- Maintains tool session state
- Defers filtered tools for search

#### 4. Preemptive Summarization (`internal/preemptive/`)

**File:** `internal/preemptive/summarizer.go`

**Purpose:** Background summarization when context fills up to 85% capacity

**Strategy:**
- Triggered at 80% context window usage
- Pre-computes summaries for instant retrieval
- Never waits during active conversation

**Summarizer Types:**
1. `StrategyCompresr` - Uses Compresr API
2. `StrategyPassthrough` - Traditional LLM summarization

**Key Logic:**
- Calculate cutoff point based on trigger threshold (e.g., 80% → keep 20% recent)
- Use token-based or message-based approach
- Capture auth token from incoming request (for OAuth users)

#### 5. Adapters (`internal/adapters/`)

**Provider-Agnostic Interface:**

```go
type Adapter interface {
    Name() string
    Provider() Provider
    ExtractLastUserContent([]byte) ([]string, bool)
    ExtractToolOutput([]byte) ([]ExtractedContent, error)
    ExtractAssistantIntent([]byte) string
    ApplyLastUserContent([]byte, []string) []byte
    ApplyToolOutput([]byte, map[string]string) []byte
}
```

**Providers:**
- `internal/adapters/anthropic.go`
- `internal/adapters/openai.go`
- `internal/adapters/bedrock.go`
- `internal/adapters/gemini.go`
- `internal/adapters/litellm.go`
- `internal/adapters/ollama.go`

**Adapter Registry:** Centralized adapter factory

#### 6. Store (`internal/store/`)

**Purpose:** KV store for cached compressed content

**MemoryStore (`internal/store/memory.go`):**
- In-memory with TTL support
- Dual TTL: original (short), compressed (long)
- Thread-safe with mutex

#### 7. Cost Control (`internal/costcontrol/`)

**Features:**
- Token usage tracking
- Cost calculation (by provider/model)
- Savings tracking
- Trajectory logging per session

#### 8. Monitoring (`internal/monitoring/`)

**Components:**
- `Tracker` - Request-level metrics
- `SavingsTracker` - Cost/time savings
- `LogAggregator` - Background log aggregation
- `TrajectoryManager` - Session trajectory files
- `MetricsCollector` - Operational metrics
- `ExpandLog` / `SearchLog` - Ring buffers for dashboard

#### 9. Auth (`internal/auth/`)

**Features:**
- OAuth support for Claude Code
- Subscription-based auth (Max/Pro users without API key)
- Auth fallback mechanism
- Callback server for OAuth flow

#### 10. Dashboard (`internal/dashboard/` + `web/dashboard/`)

**Dashboard Port:** 18080 (fixed)

**React Dashboard (`web/dashboard/`):**
- TypeScript/React
- Components: MonitorTab, SavingsTab, SettingsTab, etc.
- Features: Real-time monitoring, cost tracking, session config

#### 11. Tool Output Expansion (`internal/pipes/tool_output/tool_output_expand.go`)

**Purpose:** Handle `/expand` endpoint for retrieving original compressed content

**Flow:**
- LLM calls `/expand` with shadow ID
- Gateway retrieves original content from store
- Patches request and forwards to LLM

#### 12. External (`external/`)

**Helper Functions:**
- `CallLLM()` - Universal LLM calling
- `CallLLMParams` - Standardized request params
- `SystemPrompt*` - Predefined prompts
- `UserPrompt*` - User-facing prompts

#### 13. Config (`internal/config/`)

**Configuration:** YAML-based with hot-reload support

**Hot-Reload Mechanism:**
- File watcher via `internal/config/reloader.go`
- Config source passed to gateway for reference
- Thread-safe config updates

## Key Design Decisions

### 1. Pipe Architecture
**Why:** Provider-agnostic compression logic
**Benefit:** New adapters don't need to reimplement compression
**Tradeoff:** Slight abstraction overhead

### 2. Shadow Prefix at Send-Time
**Why:** Avoid re-compressing already-compressed content
**Implementation:** `<<<SHADOW:id>>>` prefix added after compression, before sending
**Benefit:** KV-cache preservation, no redundant compression

### 3. Preemptive Background Summarization
**Why:** User waits for compaction otherwise
**Trigger:** 80% context window (not 85% - safety margin)
**Benefit:** Instant response when hitting limits

### 4. Query-Agnostic Models
**Why:** Not all compression models need context
**Detection:** `IsQueryAgnostic()` check
**Fallback:** Extract from assistant intent or user query

### 5. Dual TTL Caching
**Why:** Balance storage vs accessibility
**Original:** Short TTL (minutes, touched on every LLM call)
**Compressed:** Long TTL (hours/days)

### 6. SSRF Protection
**Why:** Prevent agents from hitting arbitrary hosts
**Mechanism:** Whitelist of allowed LLM provider hosts
**Configurable:** `GATEWAY_ALLOWED_HOSTS` env var

## Compression Process Flow

```
1. Agent sends request to gateway (18081)
   ├─ Request body contains: system, user, tool_result blocks
   
2. Gateway receives request
   ├─ Extract session ID from path or first request
   ├─ Setup PipeContext
   ├─ Classify user message (classify.go)
   
3. Router selects appropriate pipes
   ├─ tool_output pipe if tool results present
   ├─ tool_discovery pipe if tool defs present
   
4. tool_output pipe processes
   ├─ Extract tool outputs via adapter
   ├─ Skip <<<SHADOW:>>> prefixed content
   ├─ For each new tool output > minBytes:
   │   ├─ Build query from assistant intent
   │   ├─ Call Compresr API (or external provider)
   │   ├─ Cache compressed result
   │   └─ Record metrics
   ├─ Add <<<<SHADOW:shadow_id>>> prefix at send-time
   
5. Request forwarded to upstream LLM
   ├─ Modified request body with compressed content
   
6. LLM responds
   ├─ Response may request expand_context
   ├─ Gateway intercepts /expand call
   ├─ Retrieves original content from store
   └─ Forwards to LLM
   
7. Response returned to agent
```

## Configuration

**Default Config Locations:**
1. `~/.config/context-gateway/config.yaml`
2. `configs/fast_setup.yaml` (embedded)

**Key Settings:**
```yaml
server:
  port: 18081

compresr:
  api_key: "sk-..."
  base_url: "https://api.compresr.ai"

pipes:
  tool_output:
    enabled: true
    min_bytes: 500
    strategy: compresr
  tool_discovery:
    enabled: false

preemptive:
  enabled: true
  trigger_threshold: 80  # Percent
  model: "claude-3-5-sonnet-20241022"

cost_control:
  enabled: true
```

## Dependencies

**Go Modules:**
- `aws/aws-sdk-go-v2` - Bedrock support
- `coder/websocket` - Streaming support
- `jkroulik/pkoukk-tiktoken-go` - Token counting
- `rs/zerolog` - Logging
- `tidwall/gjson` / `tidwall/sjson` - JSON manipulation
- `joho/godotenv` - Env file loading
- `modernc.org/sqlite` - Prompt history storage

## Testing

**Test Structure:**
```
tests/
├─ anthropic/
├─ bedrock/
├─ common/
├─ compresr/
├─ config/
├─ costcontrol/
├─ dashboard/
├─ gateway/
├─ gemini/
├─ litellm/
├─ monitoring/
├─ ollama/
├─ openai/
├─ phantom_tools/
├─ postsession/
├─ preemptive/
├─ store/
├─ stress/
├─ tool_discovery/
└─ tool_output/
```

**Categories:**
- `unit/` - Unit tests
- `integration/` - Integration tests
- `e2e/` - End-to-end tests

## Installation

```bash
# Install via script
curl -fsSL https://compresr.ai/api/install | sh

# Or build from source
go build -o context-gateway ./cmd
```

## Usage

```bash
# Launch with Claude Code
context-gateway

# Launch with debug logging
context-gateway -d

# Start gateway server only
context-gateway serve

# Access dashboard
curl http://localhost:18080/dashboard/

# Claude Code CLI commands
/savings - Show cost/time savings
/compact - Manual compaction (triggers preemptive)
```

## Related Projects Mentioned

- **Swival:** Context management solution (https://swival.dev)
- **Distill:** Token compression (https://github.com/samuelfaj/distill)
- **Anthropic Claude 1M context:** GA with improved attention
- **OpenAI GPT-5.4 eval:** Context accuracy benchmarks

## API Endpoints

**Gateway Port (18081):**
- `/health` - Health check
- `/expand` - Expand compressed content
- `/api/dashboard` - Dashboard API
- `/api/savings` - Savings data
- `/api/account` - Account status
- `/api/config` - Config management
- `/api/prompts` - Prompt history

**Dashboard Port (18080):**
- All API endpoints centralized
- React dashboard UI

## Performance Characteristics

- **Tool output compression:** < 0.5s latency
- **Preemptive summarization:** Instant (pre-computed)
- **Expand on demand:** < 10ms (cache hit)
- **Token savings:** Varies by tool output size and content

## Limitations & Tradeoffs

1. **Provider-specific adapters required:** New LLM providers need adapter implementation
2. **SSRF protection:** Must whitelist all valid LLM provider hosts
3. **Cache eviction:** MemoryStore uses TTL-based eviction
4. **OAuth token scope:** Captured tokens must match provider
5. **Structured data:** Verbatim prefix may be lost if content too large

## Future Enhancements (Not Implemented)

- MCP tool integration
- Custom compression models
- Enhanced analytics dashboard
- Multi-agent coordination

## References

- **Hacker News Post:** https://news.ycombinator.com/item?id=47367526
- **GitHub Repository:** https://github.com/Compresr-ai/Context-Gateway
- **Website:** https://compresr.ai
- **Documentation:** https://compresr.ai/docs
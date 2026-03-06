# Context Management in nbchat

## Overview

Long agentic sessions — where the assistant makes many tool calls in a single turn with no user follow-up — quickly exhaust a local model's context window. This document describes the three-layer approach nbchat uses to keep token usage bounded while preserving the model's ability to reason about what it has done.

The design deliberately avoids LLM-based conversation summarisation, which proved fragile in practice: summaries were unreliable, injecting them as a second system message was ignored by most llama.cpp chat templates, and any failure in the summariser caused total context loss.

---

## The Three Layers

### Layer 1 — Tool Output Compression (`nbchat/core/compressor.py`)

Tool outputs are the primary driver of context overflow. A single `read_file` call can return 50 000 characters; ten such calls fill the context before the assistant has done any reasoning.

**How it works:**

Every tool result passes through `compress_tool_output` before it is appended to `messages`. If the result is under `COMPRESS_THRESHOLD_CHARS` (default 800 chars) it is stored verbatim. Otherwise a fast LLM call extracts only the relevant information:

```
Tool called: read_file
Arguments: {"path": "nbchat/core/compaction.py"}
Output: <full file contents>

Extract only the information from this output that is relevant to
the ongoing task. If the output contains NO relevant information,
respond with exactly: NO_RELEVANT_OUTPUT
```

The compressed result (typically a few sentences or a short list) is what the model receives in `messages`. The full raw result is stored in `self.history` and the DB so the UI always shows complete output.

If the LLM call fails, a simple head+tail truncation is used as a fallback — the tool loop is never interrupted.

**Key properties:**
- Raw output renders in the UI immediately, before compression runs
- `NO_RELEVANT_OUTPUT` results send `[tool_name: no relevant output]` to the model — the tool call is acknowledged without consuming tokens
- The compressor input is itself capped at 12 000 chars to prevent the compression call from overflowing the context

---

### Layer 2 — Task Log (`nbchat/ui/context_manager.py`, `nbchat/core/db.py`)

Windowing and compression mean the model may not see messages from earlier in the session. The task log solves catastrophic forgetting: even with an empty window the model always knows what it has done.

**How it works:**

After every tool call, one line is appended to `self.task_log`:

```
read_file(nbchat/core/compaction.py) → class CompactionEngine with threshold
str_replace_editor(compaction.py) → OK
run_tests(test_compaction.py) → 3 passed, 1 failed
```

The log is capped at 30 entries and persisted to the DB so it survives kernel restarts. On every API call it is injected into the system prompt:

```
[RECENT ACTION LOG — what has been done so far]
  read_file(nbchat/core/compaction.py) → class CompactionEngine with threshold
  str_replace_editor(compaction.py) → OK
  ...
[END ACTION LOG]
```

**Key properties:**
- Deterministic — no LLM call, no risk of hallucinated history
- Incremental — each entry is appended at the time of the tool call, never reconstructed
- Survives any amount of message trimming — it lives in the system prompt, not in messages
- Scoped to the last 30 tool calls — bounded and predictable

---

### Layer 3 — Hard Trim (`nbchat/ui/context_manager.py`)

Even with compressed tool outputs, a sufficiently long agentic loop can accumulate enough messages to overflow the context. `_hard_trim` is called immediately before every API call as a guaranteed safety net.

**How it works:**

`_hard_trim` drops the oldest complete exchange units from `messages`. An exchange unit is one `assistant` message with `tool_calls` plus all the `tool` result messages that immediately follow it. Exchanges are always dropped atomically — never one message at a time — because the llama.cpp Jinja template requires every `tool` message to be preceded by an `assistant` message with a matching `tool_call`. Dropping them individually causes a server 500.

```
Before trim:
  [0] system
  [1] user: "familiarise yourself with the code"
  [2] assistant (tool_calls: [read_file])       ← oldest exchange
  [3] tool: read_file result
  [4] assistant (tool_calls: [read_file])
  [5] tool: read_file result
  [6] assistant (tool_calls: [str_replace])     ← kept (KEEP_RECENT_EXCHANGES=2)
  [7] tool: str_replace result
  [8] assistant (tool_calls: [run_tests])       ← kept
  [9] tool: run_tests result

After trim (if over budget):
  [0] system
  [1] user: "familiarise yourself with the code"
  [4] assistant (tool_calls: [read_file])
  [5] tool: read_file result
  [6] assistant (tool_calls: [str_replace])
  ...
```

`KEEP_RECENT_EXCHANGES = 2` ensures the two most recent tool round-trips are never dropped, preserving the model's immediate working memory.

Last resort: if no complete exchange can be dropped (e.g. there is only one exchange and it is the most recent one), the content of the largest tool result is truncated in-place to 200 chars.

**Key properties:**
- Called on every API call — context overflow is mathematically impossible
- Atomic drops — message ordering invariant is never violated
- `reasoning_content` is stripped from all messages before the API call — this field is output-only and can add thousands of tokens per step if left in

---

## File Map

```
nbchat/
├── core/
│   ├── compressor.py        # Layer 1 — tool output compression
│   └── db.py                # save_task_log / load_task_log
└── ui/
    ├── chatui.py            # Widget creation, history rendering, event handlers
    ├── context_manager.py   # Layer 2 (task log) + Layer 3 (hard trim) + window
    ├── conversation.py      # Agentic tool-calling loop + streaming
    └── chat_builder.py      # Builds OpenAI messages list; injects task log
```

---

## Configuration

| Constant | Location | Default | Effect |
|---|---|---|---|
| `CONTEXT_TOKEN_THRESHOLD` | `config.py` | 16384 | Model context size; hard trim targets 85% of this |
| `COMPRESS_THRESHOLD_CHARS` | `compressor.py` | 800 | Tool outputs longer than this are compressed |
| `WINDOW_TURNS` | `chatui.py` | 2 | Number of user turns included in the model's window |
| `KEEP_RECENT_EXCHANGES` | `context_manager.py` | 2 | Exchange blocks protected from hard trim |
| Max task log entries | `context_manager.py` | 30 | Rolling cap on task log length |

---

## Data Flow

```
User sends message
        │
        ▼
_on_send → append to self.history → DB → render in UI
        │
        ▼
_process_conversation_turn
        │
        ├── _window()          → last WINDOW_TURNS user turns of history
        ├── chat_builder        → build messages list with task log in system prompt
        │
        └── loop:
              │
              ├── _hard_trim(messages)    ← before every API call
              ├── stream response
              │
              └── for each tool call:
                    ├── run_tool()               → raw result
                    ├── render_tool(raw_result)  → UI (immediate)
                    ├── compress_tool_output()   → compressed result
                    ├── _log_action()            → one line appended to task_log
                    ├── append raw to self.history + DB
                    └── append compressed to messages
```

---

## What Was Tried Before

Earlier approaches and why they were abandoned:

| Approach | Problem |
|---|---|
| LLM conversation summarisation | Summaries were unreliable; second system message ignored by llama.cpp templates; summariser could itself overflow context |
| Turn-count sliding window | A single turn with 30 tool calls was still 17k tokens |
| Token-estimate sliding window | Estimator (`len//3`) was 2–5x off for code/JSON content; window was too large |
| Drop oldest messages one-at-a-time | Broke `assistant`/`tool` message pairing; caused server 500 |

The current approach avoids all of these by compressing at the source (individual tool outputs), using a deterministic log for continuity, and enforcing a hard structural trim that respects message ordering invariants.
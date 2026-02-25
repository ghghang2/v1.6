# Compaction Engine Documentation

## 1. Introduction

The repository contains the implementation of a **CompactionEngine** used in the `nbchat` project. The engine is responsible for managing the size of the chat history sent to a language model so that the model never receives more tokens than it can handle.

The overall workflow is:

1. Estimate the number of tokens in the current conversation.
2. If the estimate is close to the configured maximum, summarise the older part of the history.
3. Replace that older part with a single *compacted* message that contains a concise summary.
4. Keep the most recent `tail_messages` rows untouched so the user can see the exact latest interaction.

The engine is used by `ChatUI` in the `nbchat` package but can also be invoked directly.

## 2. Architecture

The design follows a small, single‑responsibility class that exposes a public API consisting of three methods:

* `should_compact(history)` – returns a Boolean indicating whether the history should be compacted.
* `compact_history(history)` – performs the summarisation and returns a new history list.
* `total_tokens(history)` – returns a token estimate used only for the decision step.

The engine depends on the following helper modules:

* `build_messages()` – converts raw history tuples into the OpenAI chat message format.
* `get_client()` – obtains a configured OpenAI client that points at the local `llama-server` instance.

Internally it keeps a small token‑count cache protected by a lock to keep `total_tokens` fast in multi‑threaded contexts.

The compaction logic itself is described in detail in section 4.

## 3. Token Estimation

*The real OpenAI API provides a token count for a given string. In this project we use a lightweight heuristic to keep the code dependency minimal.*

The estimator simply returns `max(1, len(text)//3)`. It is *good enough* for our purposes because:

* The model is a large‑language‑model that roughly uses one token per 3 characters of English text.
* The estimator is deterministic and fast.

The `total_tokens()` method walks the history list, hashes the tuple of (`content`, `tool_args`) to avoid double‑counting identical rows. If a row has already been seen the cached token count is reused.

```python
    def total_tokens(self, history):
        total = 0
        for role, content, tool_id, tool_name, tool_args in history:
            msg_hash = hash((content, tool_args))
            if msg_hash in self._cache:
                total += self._cache[msg_hash]
                continue
            tokens = self._estimate_tokens(content) + (
                self._estimate_tokens(tool_args) if tool_args else 0
            )
            self._cache[msg_hash] = tokens
            total += tokens
        return total
```

## 4. Compaction Algorithm

### 4.1 Decision

The `should_compact()` method simply checks if the estimated token count is greater than or equal to **75 %** of the threshold. This gives a buffer so that the *tail* (the most recent `tail_messages` rows) is still fully available.

### 4.2 Splitting the History

The history list is split into:

* **older** – everything before the tail.
* **tail** – the last `tail_messages` rows.

The *tail* must start on a **user** message. This is required because the Llama‑Server Jinja template expects that a tool result is always preceded by an assistant message that contains a tool call. By ensuring the tail begins on a user message we keep the exchange boundary intact.

If a suitable boundary cannot be found the compaction is aborted – the conversation is left untouched.

### 4.3 Summarisation

The older slice is converted into OpenAI API message format using `build_messages()` from `nbchat.ui.chat_builder`. The system prompt is prepended so the summariser has full context.

All *reasoning_content* fields are stripped because most inference servers ignore them and they would otherwise consume tokens.

A single user message containing the `summary_prompt` is appended.

The summariser is called via `client.chat.completions.create()` using the configured `summary_model`. The response is taken from the first choice.

### 4.4 Updating the History

The returned history is:

```
[("compacted", summary_text, "", "", "")]
+tail
```

The *compacted* row has role `compacted` and contains only the summary text. The cache is cleared because the shape of the history has changed.

## 5. Integration with ChatUI

`ChatUI` creates a `CompactionEngine` instance in its constructor:

```python
self.compaction_engine = CompactionEngine(
    threshold=config.CONTEXT_TOKEN_THRESHOLD,
    tail_messages=config.TAIL_MESSAGES,
    summary_prompt=config.SUMMARY_PROMPT,
    summary_model=config.MODEL_NAME,
    system_prompt=self.system_prompt,
)
```

During a user request the UI calls `self.compaction_engine.should_compact()` to decide if compaction is needed. If the answer is `True` it replaces the history with `self.compaction_engine.compact_history(history)`.

The compaction step is performed **before** a new message is sent to the model, which guarantees that the model never receives a history that is too large.

## 6. Configuration

All parameters are defined in `nbchat.core.config`:

| Variable | Default | Description |
|---------|---------|-------------|
| `CONTEXT_TOKEN_THRESHOLD` | 6000 | Max token count before compaction is triggered |
| `TAIL_MESSAGES` | 6 | Number of recent rows kept verbatim |
| `SUMMARY_PROMPT` | see file | Prompt passed to the summariser |
| `MODEL_NAME` | "unsloth/gpt-oss-20b-GGUF:F16" | The default Llama‑Server model |
| `SERVER_URL` | "http://localhost:8000" | Base URL for the OpenAI‑compatible server |

The user can override these values by setting the corresponding environment variables or by editing `config.py`.

## 7. Extending the Engine

If you want a different summarisation strategy you can subclass `CompactionEngine` and override:

* `total_tokens()` – to provide a more accurate estimator.
* `compact_history()` – to change how the history is split or how the summariser is called.
* `should_compact()` – to use a different trigger rule.

The rest of the system will continue to work because `ChatUI` only interacts with the public API of the engine.

## 8. Testing

Run the project's test suite with `pytest`:

```bash
pytest
```

---

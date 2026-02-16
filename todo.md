# TODO list for nbchat.py rewrite

[DONE] 1. **Draft the rewrite plan**
   - Identify all functional gaps between `nbchat.py` and the working Streamlit app.
   - Break the fix into discrete, testable steps.
   - Store the plan as a numbered list in this file.
[DONE] 2. **Implement the steps**
   - Execute each numbered step in order.
   - After finishing a step, prepend `[DONE]` to its line to mark it as complete.

## Planned steps
1. **Add session persistence**
   - Generate or reuse a session ID that survives notebook reloads.
2. **Refactor `build_messages`**
   - Use the full 5‑tuple conversation history instead of only assistant turns.
3. **Implement a robust `stream_and_collect` helper**
   - Copy the Streamlit logic for streaming and collecting assistant responses.
4. **Add tool‑call handling**
   - After a tool call, re‑invoke streaming to get the assistant’s follow‑up.
5. **Correct logging**
   - Store tool calls as a single 5‑tuple row, and persist analysis blocks.
6. **Improve rendering**
   - Render tool calls and analysis blocks using `<details>` elements.
7. **Add finish‑reason handling**
   - Stop streaming when `finish_reason` is `stop` or `tool_calls`.
8. **Add error handling for tools**
   - Show tool execution errors in the UI.
9. **Update UI widgets**
   - Use `ipywidgets` for a cleaner chat area with scroll support.
10. **Run tests**
    - Ensure the notebook still loads and runs without errors.

---
Note: Mark a line as completed by changing its prefix from `1.` to `[DONE] 1.` (or similar).
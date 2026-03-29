# Monitoring Issue Investigation Findings

## Summary
The monitoring panel in `nbchat/ui/chatui.py` shows "No monitoring data yet" even after conversations have occurred. This investigation identifies the root cause and proposes a fix.

## Issue Description
When the chat UI's monitoring panel is refreshed, it displays empty data despite user interactions and LLM calls having occurred during the session.

## Root Cause Analysis

### Data Flow Trace

1. **SessionMonitor Creation**
   - `nbchat/core/monitoring.py` line 668: `get_session_monitor(session_id)` returns or creates a SessionMonitor instance
   - Session monitors are stored in a global `_monitors` dict keyed by session_id

2. **Recording Metrics**
   - `nbchat/ui/conversation.py` line 150: Calls `monitor.record_llm_call()` after LLM responses
   - `nbchat/ui/conversation.py` line 306: Calls `monitor.record_tool_call()` for tool executions
   - These accumulate metrics in the SessionMonitor instance

3. **Session Reset**
   - `nbchat/ui/chatui.py` line 227: `_reset_session_state()` clears per-session state
   - `nbchat/ui/chatui.py` line 536: Calls `self._reset_session_state()` during session initialization
   - This triggers `flush_session_monitor(session_id, db_module)`

4. **The Problem**
   - `nbchat/core/monitoring.py` line 676: `flush_session_monitor()` merges session data into global stats
   - **Critical**: It uses `self._monitors.pop(session_id)` which REMOVES the monitor from memory
   - `nbchat/ui/chatui.py` line 422/531: `_refresh_monitoring_panel()` is called AFTER the flush
   - The panel refresh finds NO session monitor because it was popped during flush

### Code Evidence

```python
# nbchat/core/monitoring.py line 676
def flush_session_monitor(session_id: str, db) -> None:
    """Merge session monitor data into global stats"""
    monitor = self._monitors.pop(session_id)  # <-- REMOVES from memory
    # ... merges data to global aggregates
```

```python
# nbchat/ui/chatui.py line 536
self._reset_session_state()  # Triggers flush_session_monitor
# ...
self._refresh_monitoring_panel()  # <-- Finds empty _monitors dict
```

## Proposed Fix

### Option 1: Don't Pop from Memory
Change `flush_session_monitor` to NOT pop the monitor, keeping it available for UI display:

```python
def flush_session_monitor(session_id: str, db) -> None:
    monitor = self._monitors.get(session_id)
    if monitor:
        # Merge to global stats but don't remove
        # Keep monitor in _monitors for UI access
        pass
```

### Option 2: Refresh Panel Before Reset
Change the order in `_reset_session_state` to refresh the monitoring panel BEFORE flushing:

```python
def _reset_session_state(self) -> None:
    self._refresh_monitoring_panel()  # Refresh first
    flush_session_monitor(self.session_id, db)  # Then flush
```

### Option 3: Copy Monitor Data for UI
Create a separate read-only copy for the UI that persists after flush:

```python
def flush_session_monitor(session_id: str, db) -> None:
    monitor = self._monitors.pop(session_id)
    # Store snapshot for UI
    self._ui_snapshots[session_id] = monitor.to_dict()
```

## Recommendation
**Option 1** is the cleanest solution because:
- Session monitors should remain accessible for display purposes
- The flush is meant to persist data, not destroy it
- UI panels should be able to query current session data at any time
- No reordering of operations required

## Files Involved
- `nbchat/core/monitoring.py` - SessionMonitor class and flush_session_monitor function
- `nbchat/ui/chatui.py` - _refresh_monitoring_panel and _reset_session_state methods
- `nbchat/ui/conversation.py` - record_llm_call and record_tool_call invocations

## Testing Steps
1. Start a new chat session
2. Send a message that triggers LLM calls and tool executions
3. Check monitoring panel - should show turn_count > 0 and tools > 0
4. Refresh the monitoring panel
5. Verify data persists and is accurate

## Status
Investigation complete. Fix ready to implement.
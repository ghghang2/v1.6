# Implementation Guide: Enhanced Episode Persistence with Metadata (Opportunity 4)

> **Prerequisites:** Basic Python knowledge, familiarity with nbchat's codebase, understanding of SQLite.
> **Estimated time:** 2–3 days (including testing and iteration).
> **Source:** Meta-Harness "Episode-Level Persistence" approach.
> **⚠️ CRITICAL NOTE:** This guide has been corrected. The original guide proposed creating a NEW `episodes` table and a separate `episode.py` module, which would create parallel persistence with the existing `db.py`. This fixed version instead ENHANCES the existing `db.py` with new columns in the existing `session_meta` table, which is the correct approach.

---

## 1. Goal

Enhance nbchat's SQLite persistence to store rich metadata about multi-turn interactions, enabling performance analysis, debugging, and learning from past interactions.

**⚠️ IMPORTANT DECISION:** Before implementing, ask yourself:

1. **Is this actually needed?** Nbchat already has `session_meta` table for metadata storage. The question is whether we need a separate `episodes` table or can just extend `session_meta`.

2. **What's the complexity cost?** A new `episodes` table means:
   - New migration logic
   - New queries
   - New failure modes
   - Parallel persistence (chat_log vs episodes)

3. **Is it worth it?** For now, extending `session_meta` is simpler and sufficient. If you need richer episode tracking, add it later.

**Recommendation:** Extend `session_meta` with new keys for episode metadata. Don't create a new `episodes` table unless you have a compelling reason.

---

## 2. Background: How Nbchat Currently Handles Episodes

Nbchat currently stores episodes with **limited metadata** in the `session_meta` table:

- `db.py` has a `session_meta` table with (session_id, key, value) schema.
- Episodes store conversation history in `chat_log` table.
- There is no structured metadata for episodes (e.g., tokens used, cost, tool calls).

### Key files to understand:
| File | Purpose |
|------|---------|
| `nbchat/core/db.py` | SQLite persistence: chat history, memory, episodes, tool outputs |
| `nbchat/core/client.py` | OpenAI-compatible streaming client with metrics logging |
| `nbchat/core/monitoring.py` | Metrics collection, structured logging, alerting |

---

## 3. Architecture Overview

```
nbchat/core/
├── db.py              # Enhanced with new session_meta keys
└── ...
```

**⚠️ DESIGN DECISION:** We are NOT creating a new `episodes` table or `episode.py` module. Instead, we extend `session_meta` with new keys for episode metadata. This keeps the change minimal and avoids parallel persistence.

---

## 4. Step-by-Step Implementation

### Step 1: Add Episode Metadata Functions to db.py

**File:** `nbchat/core/db.py`

Add new functions to store and retrieve episode metadata in the `session_meta` table.

```python
# Add these functions to nbchat/core/db.py

def save_episode_metadata(session_id: str, metadata: dict) -> None:
    """Save episode metadata as JSON in session_meta.
    
    Args:
        session_id: The session/episode ID.
        metadata: Dictionary with keys like:
            - model: str
            - prompt_version: str
            - tokens_in: int
            - tokens_out: int
            - cost_usd: float
            - tool_calls: list[dict]
            - errors: list[dict]
            - tags: list[str]
            - outcome: str
            - start_time: float
            - end_time: float
            - duration_ms: int
    """
    import json
    from .db import _meta_set
    _meta_set(session_id, "episode_metadata_v1", json.dumps(metadata))


def load_episode_metadata(session_id: str) -> dict:
    """Load episode metadata from session_meta.
    
    Args:
        session_id: The session/episode ID.
    
    Returns:
        Dictionary with episode metadata, or empty dict if not found.
    """
    import json
    from .db import _meta_get
    raw = _meta_get(session_id, "episode_metadata_v1")
    try:
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def save_episode_conversation(session_id: str, conversation: list[dict]) -> None:
    """Save the full conversation for an episode.
    
    Args:
        session_id: The session/episode ID.
        conversation: List of message dictionaries with 'role' and 'content'.
    """
    import json
    from .db import _meta_set
    _meta_set(session_id, "episode_conversation_v1", json.dumps(conversation))


def load_episode_conversation(session_id: str) -> list[dict]:
    """Load the full conversation for an episode.
    
    Args:
        session_id: The session/episode ID.
    
    Returns:
        List of message dictionaries, or empty list if not found.
    """
    import json
    from .db import _meta_get
    raw = _meta_get(session_id, "episode_conversation_v1")
    try:
        return json.loads(raw) if raw else []
    except Exception:
        return []
```

**What this does:**
- Adds functions to store and retrieve episode metadata in `session_meta`.
- Uses JSON serialization for complex data types (lists, dicts).
- Keeps the change minimal - no new tables, no new modules.

---

### Step 2: Integrate with the Client Module

**File:** `nbchat/core/client.py`

Modify the `ChatClient` class to populate episode metadata.

```python
# Add these imports at the top of client.py
from .db import save_episode_metadata, save_episode_conversation

# In the ChatClient class, add episode tracking
class ChatClient:
    def __init__(self, config, stream=False):
        # ... existing init code ...
        self._current_session_id = None
        self._current_conversation = []
        self._current_start_time = None

    def start_session(self, session_id: str) -> None:
        """Start a new episode/session."""
        self._current_session_id = session_id
        self._current_conversation = []
        self._current_start_time = time.time()
        logger.info("Started session: %s", session_id)

    def stop_session(self, model: str, prompt_version: str = "",
                     tokens_in: int = 0, tokens_out: int = 0,
                     cost_usd: float = 0.0, tool_calls: list = None,
                     errors: list = None, tags: list = None,
                     outcome: str = "success") -> None:
        """Stop the current episode/session and save metadata."""
        if not self._current_session_id:
            return

        end_time = time.time()
        duration_ms = int((end_time - self._current_start_time) * 1000) if self._current_start_time else 0

        metadata = {
            "model": model,
            "prompt_version": prompt_version,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": cost_usd,
            "tool_calls": tool_calls or [],
            "errors": errors or [],
            "tags": tags or [],
            "outcome": outcome,
            "start_time": self._current_start_time,
            "end_time": end_time,
            "duration_ms": duration_ms,
        }

        # Save metadata and conversation
        save_episode_metadata(self._current_session_id, metadata)
        save_episode_conversation(self._current_session_id, self._current_conversation)

        logger.info("Stopped session: %s (%d ms)", self._current_session_id, duration_ms)

        # Reset
        self._current_session_id = None
        self._current_conversation = []
        self._current_start_time = None
```

**What this does:**
- Tracks the current session/episode.
- Saves metadata and conversation when the session ends.
- Integrates with the existing `db.py` functions.

---

## 5. Testing

### 5.1 Unit Tests

**File:** `tests/test_episode_metadata.py`

```python
"""Tests for episode metadata."""
import pytest
import json
from nbchat.core.db import save_episode_metadata, load_episode_metadata


def test_save_and_load_metadata(tmp_path):
    """Test saving and loading episode metadata."""
    import sqlite3
    from pathlib import Path
    
    # Create a temporary database
    db_path = tmp_path / "test.db"
    
    # Import the db module and point it to the test database
    import nbchat.core.db as db_module
    original_db_path = db_module.DB_PATH
    db_module.DB_PATH = db_path
    
    try:
        # Initialize the database
        db_module.init_db()
        
        # Save metadata
        metadata = {
            "model": "gpt-4",
            "tokens_in": 100,
            "tokens_out": 50,
            "cost_usd": 0.001,
        }
        save_episode_metadata("session1", metadata)
        
        # Load metadata
        loaded = load_episode_metadata("session1")
        assert loaded["model"] == "gpt-4"
        assert loaded["tokens_in"] == 100
        assert loaded["tokens_out"] == 50
        assert loaded["cost_usd"] == 0.001
    finally:
        # Restore original path
        db_module.DB_PATH = original_db_path
        # Clean up
        db_path.unlink(missing_ok=True)


def test_load_nonexistent_metadata():
    """Test loading metadata for a nonexistent session."""
    result = load_episode_metadata("nonexistent")
    assert result == {}


def test_metadata_with_list_values():
    """Test saving and loading metadata with list values."""
    import sqlite3
    from pathlib import Path
    import nbchat.core.db as db_module
    
    # Create a temporary database
    db_path = Path("/tmp/test_episode.db")
    original_db_path = db_module.DB_PATH
    db_module.DB_PATH = db_path
    
    try:
        # Initialize the database
        db_module.init_db()
        
        # Save metadata with lists
        metadata = {
            "model": "gpt-4",
            "tool_calls": [{"name": "bash", "args": {"cmd": "ls"}}],
            "errors": [{"code": 500, "message": "Internal error"}],
            "tags": ["test", "example"],
        }
        save_episode_metadata("session2", metadata)
        
        # Load metadata
        loaded = load_episode_metadata("session2")
        assert loaded["model"] == "gpt-4"
        assert len(loaded["tool_calls"]) == 1
        assert len(loaded["errors"]) == 1
        assert loaded["tags"] == ["test", "example"]
    finally:
        # Restore original path
        db_module.DB_PATH = original_db_path
        # Clean up
        db_path.unlink(missing_ok=True)
```

---

## 6. Usage

### 6.1 Basic Usage

```python
from nbchat.core.client import get_client
from nbchat.core.db import load_episode_metadata

# Get the client
client = get_client()

# Start a session
client.start_session("session_123")

# ... make API calls ...

# Stop the session and save metadata
client.stop_session(
    model="qwen3.5-35b",
    tokens_in=100,
    tokens_out=50,
    cost_usd=0.001,
    outcome="success",
)

# Load metadata later
metadata = load_episode_metadata("session_123")
print(f"Model: {metadata['model']}")
print(f"Tokens in: {metadata['tokens_in']}")
print(f"Tokens out: {metadata['tokens_out']}")
```

### 6.2 Querying Episodes

```python
from nbchat.core.db import load_episode_metadata

# Load all episode metadata for a session
metadata = load_episode_metadata("session_123")

# Filter by outcome
if metadata.get("outcome") == "success":
    print("Episode completed successfully")
elif metadata.get("outcome") == "failure":
    print(f"Episode failed: {metadata.get('errors', [])}")
```

---

## 7. Common Pitfalls

1. **JSON serialization:** Ensure all values in the metadata dictionary are JSON-serializable (strings, numbers, lists, dicts). Custom objects need special handling.

2. **Data size:** The `session_meta` table stores values as TEXT. Large conversations or metadata may exceed SQLite's text size limits. Consider truncating or compressing large values.

3. **Schema migration:** If you add new fields to the metadata, ensure backward compatibility. Use `json.loads(data.get("new_field", default))` to handle missing fields.

4. **Thread safety:** If multiple threads are saving/loading episode metadata simultaneously, ensure proper synchronization.

5. **Performance:** Loading large conversations from the database can be slow. Consider pagination or pagination-like approaches for large episodes.

---

## 8. Success Criteria

- [ ] All unit tests pass.
- [ ] Episode metadata is correctly saved and loaded.
- [ ] Metadata includes all required fields (model, tokens, cost, etc.).
- [ ] Episode conversations are correctly saved and loaded.
- [ ] Backward compatibility is maintained (loading metadata from sessions created before this change returns empty dict).

---

## Appendix: What NOT to Implement

The following approaches were considered but rejected:

1. **New `episodes` table:** Creating a new `episodes` table adds complexity and creates parallel persistence. Use `session_meta` instead.

2. **Separate `episode.py` module:** Adding a new module adds complexity. Keep episode functions in `db.py` where they belong.

3. **ORM (SQLAlchemy, etc.):** Using an ORM adds significant complexity. Stick with raw SQLite for now.

4. **Persistent cache:** Storing episode metadata in a separate cache layer adds complexity. Store it directly in SQLite.

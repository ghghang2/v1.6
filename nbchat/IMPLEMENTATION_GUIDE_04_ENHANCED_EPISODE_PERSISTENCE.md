# Implementation Guide: Enhanced Episode Persistence with Metadata (Opportunity 4)

> **Prerequisites:** Basic Python knowledge, familiarity with nbchat's codebase, understanding of SQLite.
> **Estimated time:** 2–3 days (including testing and iteration).
> **Source:** Meta-Harness "Episode-Level Persistence" approach.

---

## 1. Goal

Enhance nbchat's SQLite persistence to store rich metadata about multi-turn interactions, enabling performance analysis, debugging, and learning from past interactions.

---

## 2. Background: How Nbchat Currently Handles Episodes

Nbchat currently stores episodes with **limited metadata**:

- `db.py` stores episodes but with minimal information.
- Episodes store conversation history but lack structured metadata.
- There is no way to:
  - Analyze performance (e.g., which tools are most effective?).
  - Debug errors across multiple turns.
  - Learn from past interactions.

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
├── db.py              # Enhanced with new episode metadata
├── episode.py         # Episode metadata management (new)
└── ...
```

### Component Relationships

```
Client API Call
    │
    ▼
┌─────────────┐
│ Client      │── Collects per-turn metrics
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ DB          │── Stores episode metadata
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Monitoring  │── Aggregates episode-level metrics
└─────────────┘
```

---

## 4. Step-by-Step Implementation

### Step 1: Define the Enhanced Episode Schema

**File:** `nbchat/core/episode.py` (new file)

This module defines the schema for enhanced episode metadata.

```python
"""Enhanced episode metadata schema and management."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Outcome(Enum):
    """Outcome classification for episodes."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"


@dataclass
class EpisodeMetadata:
    """Metadata for an episode."""
    episode_id: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: Optional[int] = None
    model: str = ""
    prompt_version: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    tool_calls: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    outcome: Outcome = Outcome.SUCCESS
    conversation: list[dict] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        """Check if the episode is complete."""
        return self.end_time is not None

    def finalize(self) -> None:
        """Finalize the episode."""
        if not self.is_complete:
            self.end_time = time.time()
            if self.start_time:
                self.duration_ms = int((self.end_time - self.start_time) * 1000)
            logger.info("Episode %s finalized: %d ms", self.episode_id, self.duration_ms)

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            "episode_id": self.episode_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_usd": self.cost_usd,
            "tool_calls": json.dumps(self.tool_calls),
            "errors": json.dumps(self.errors),
            "tags": json.dumps(self.tags),
            "outcome": self.outcome.value,
            "conversation": json.dumps(self.conversation),
        }

    @classmethod
    def from_dict(cls, data: dict) -> EpisodeMetadata:
        """Create from dictionary (e.g., from database)."""
        return cls(
            episode_id=data["episode_id"],
            start_time=data["start_time"],
            end_time=data.get("end_time"),
            duration_ms=data.get("duration_ms"),
            model=data.get("model", ""),
            prompt_version=data.get("prompt_version", ""),
            tokens_in=data.get("tokens_in", 0),
            tokens_out=data.get("tokens_out", 0),
            cost_usd=data.get("cost_usd", 0.0),
            tool_calls=json.loads(data.get("tool_calls", "[]")),
            errors=json.loads(data.get("errors", "[]")),
            tags=json.loads(data.get("tags", "[]")),
            outcome=Outcome(data.get("outcome", "success")),
            conversation=json.loads(data.get("conversation", "[]")),
        )
```

**What this does:**
- Defines the schema for enhanced episode metadata.
- Includes fields for start/end time, tokens used, cost, tool calls, errors, tags, and outcome.
- Provides methods for serialization and deserialization.

### Step 2: Update the Database Module

**File:** `nbchat/core/db.py`

This module is enhanced with new columns for episode metadata.

```python
"""Enhanced SQLite persistence with episode metadata."""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

from .episode import EpisodeMetadata, Outcome

logger = logging.getLogger(__name__)


class Database:
    """Enhanced SQLite database with episode metadata."""

    def __init__(self, db_path: str = "nbchat.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        self._migrate_tables()
        logger.info("Database initialized at %s", db_path)

    def _create_tables(self) -> None:
        """Create tables if they don't exist."""
        cursor = self._conn.cursor()
        
        # Episodes table with enhanced metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                episode_id TEXT PRIMARY KEY,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                duration_ms INTEGER,
                model TEXT,
                prompt_version TEXT,
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0,
                tool_calls JSON,
                errors JSON,
                tags JSON,
                outcome TEXT DEFAULT 'success',
                conversation JSON
            )
        """)
        
        # Chat history table (existing)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (episode_id) REFERENCES episodes(episode_id)
            )
        """)
        
        # Tool outputs table (existing)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tool_outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id TEXT,
                tool_name TEXT,
                input TEXT,
                output TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (episode_id) REFERENCES episodes(episode_id)
            )
        """)
        
        self._conn.commit()

    def _migrate_tables(self) -> None:
        """Migrate existing tables to new schema."""
        cursor = self._conn.cursor()
        
        # Check if new columns exist
        cursor.execute("PRAGMA table_info(episodes)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Add missing columns
        new_columns = [
            ("prompt_version", "TEXT"),
            ("tokens_in", "INTEGER DEFAULT 0"),
            ("tokens_out", "INTEGER DEFAULT 0"),
            ("cost_usd", "REAL DEFAULT 0.0"),
            ("tool_calls", "JSON"),
            ("errors", "JSON"),
            ("tags", "JSON"),
            ("outcome", "TEXT DEFAULT 'success'"),
            ("conversation", "JSON"),
        ]
        
        for col_name, col_type in new_columns:
            if col_name not in columns:
                logger.info("Adding column %s to episodes table", col_name)
                cursor.execute(f"ALTER TABLE episodes ADD COLUMN {col_name} {col_type}")
        
        self._conn.commit()

    def create_episode(self, episode_id: str, model: str = "",
                       prompt_version: str = "") -> EpisodeMetadata:
        """Create a new episode."""
        metadata = EpisodeMetadata(
            episode_id=episode_id,
            model=model,
            prompt_version=prompt_version,
        )
        
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO episodes (
                episode_id, start_time, model, prompt_version
            ) VALUES (?, ?, ?, ?)
        """, (
            episode_id,
            metadata.start_time,
            model,
            prompt_version,
        ))
        self._conn.commit()
        
        logger.info("Created episode %s", episode_id)
        return metadata

    def update_episode_metadata(self, metadata: EpisodeMetadata) -> None:
        """Update episode metadata in the database."""
        data = metadata.to_dict()
        
        cursor = self._conn.cursor()
        cursor.execute("""
            UPDATE episodes SET
                end_time = ?,
                duration_ms = ?,
                tokens_in = ?,
                tokens_out = ?,
                cost_usd = ?,
                tool_calls = ?,
                errors = ?,
                tags = ?,
                outcome = ?,
                conversation = ?
            WHERE episode_id = ?
        """, (
            data["end_time"],
            data["duration_ms"],
            data["tokens_in"],
            data["tokens_out"],
            data["cost_usd"],
            data["tool_calls"],
            data["errors"],
            data["tags"],
            data["outcome"],
            data["conversation"],
            metadata.episode_id,
        ))
        self._conn.commit()
        
        logger.info("Updated episode %s metadata", metadata.episode_id)

    def add_chat_message(self, episode_id: str, role: str,
                         content: str) -> None:
        """Add a chat message to the episode."""
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO chat_history (episode_id, role, content)
            VALUES (?, ?, ?)
        """, (episode_id, role, content))
        self._conn.commit()

    def add_tool_output(self, episode_id: str, tool_name: str,
                        input_data: str, output_data: str) -> None:
        """Add a tool output to the episode."""
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO tool_outputs (episode_id, tool_name, input, output)
            VALUES (?, ?, ?, ?)
        """, (episode_id, tool_name, input_data, output_data))
        self._conn.commit()

    def get_episode(self, episode_id: str) -> Optional[EpisodeMetadata]:
        """Get an episode by ID."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM episodes WHERE episode_id = ?",
                       (episode_id,))
        row = cursor.fetchone()
        
        if row:
            return EpisodeMetadata.from_dict(dict(row))
        return None

    def get_episodes(self, limit: int = 100, offset: int = 0,
                     tags: list[str] = None, outcome: Outcome = None) -> list[EpisodeMetadata]:
        """Get episodes with optional filters."""
        cursor = self._conn.cursor()
        
        query = "SELECT * FROM episodes WHERE 1=1"
        params = []
        
        if tags:
            for tag in tags:
                query += " AND tags LIKE ?"
                params.append(f"%{tag}%")
        
        if outcome:
            query += " AND outcome = ?"
            params.append(outcome.value)
        
        query += " ORDER BY start_time DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [EpisodeMetadata.from_dict(dict(row)) for row in rows]

    def get_episode_stats(self) -> dict:
        """Get aggregate statistics for episodes."""
        cursor = self._conn.cursor()
        
        # Total episodes
        cursor.execute("SELECT COUNT(*) FROM episodes")
        total = cursor.fetchone()[0]
        
        # Total tokens
        cursor.execute("SELECT SUM(tokens_in), SUM(tokens_out) FROM episodes")
        row = cursor.fetchone()
        total_tokens_in = row[0] or 0
        total_tokens_out = row[1] or 0
        
        # Total cost
        cursor.execute("SELECT SUM(cost_usd) FROM episodes")
        total_cost = cursor.fetchone()[0] or 0.0
        
        # Average duration
        cursor.execute("SELECT AVG(duration_ms) FROM episodes WHERE duration_ms IS NOT NULL")
        avg_duration = cursor.fetchone()[0] or 0.0
        
        # Outcome distribution
        cursor.execute("SELECT outcome, COUNT(*) FROM episodes GROUP BY outcome")
        outcome_dist = dict(cursor.fetchall())
        
        return {
            "total_episodes": total,
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "total_cost_usd": total_cost,
            "avg_duration_ms": avg_duration,
            "outcome_distribution": outcome_dist,
        }

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
        logger.info("Database closed")
```

**What this does:**
- Adds new columns to the `episodes` table in SQLite.
- Populates metadata from `client.py`'s per-turn metrics.
- Provides query APIs for episode analysis.

### Step 3: Integrate with the Client Module

**File:** `nbchat/core/client.py`

This module is enhanced to populate episode metadata.

```python
"""Enhanced client with episode metadata population."""
from __future__ import annotations

import logging
import time
from typing import Optional

from .db import Database
from .episode import EpisodeMetadata, Outcome

logger = logging.getLogger(__name__)


class ChatClient:
    """Enhanced chat client with episode metadata."""

    def __init__(self, config, db: Database = None):
        self.config = config
        self.db = db
        self._current_episode: Optional[EpisodeMetadata] = None
        self._episode_counter = 0

    def start_episode(self, model: str = "", prompt_version: str = "") -> str:
        """Start a new episode and return its ID."""
        self._episode_counter += 1
        episode_id = f"episode_{self._episode_counter}"
        
        if self.db:
            self._current_episode = self.db.create_episode(
                episode_id=episode_id,
                model=model,
                prompt_version=prompt_version,
            )
        else:
            self._current_episode = EpisodeMetadata(
                episode_id=episode_id,
                model=model,
                prompt_version=prompt_version,
            )
        
        logger.info("Started episode %s", episode_id)
        return episode_id

    def send_message(self, message: str, system_prompt: str = None,
                     **kwargs) -> str:
        """Send a message and track episode metadata."""
        if not self._current_episode:
            self.start_episode()
        
        # Track input tokens (rough estimate)
        input_tokens = len(message.split())
        self._current_episode.tokens_in += input_tokens
        
        # Add user message to conversation
        self._current_episode.conversation.append({
            "role": "user",
            "content": message,
        })
        
        if self.db:
            self.db.add_chat_message(
                self._current_episode.episode_id,
                "user",
                message,
            )
        
        # Call the LLM (placeholder)
        response = self._call_llm(message, system_prompt, **kwargs)
        
        # Track output tokens (rough estimate)
        output_tokens = len(response.split())
        self._current_episode.tokens_out += output_tokens
        
        # Estimate cost
        self._current_episode.cost_usd += self._estimate_cost(input_tokens, output_tokens)
        
        # Add assistant message to conversation
        self._current_episode.conversation.append({
            "role": "assistant",
            "content": response,
        })
        
        if self.db:
            self.db.add_chat_message(
                self._current_episode.episode_id,
                "assistant",
                response,
            )
        
        # Update database
        if self.db:
            self.db.update_episode_metadata(self._current_episode)
        
        return response

    def record_tool_call(self, tool_name: str, input_data: str,
                         output_data: str) -> None:
        """Record a tool call in the current episode."""
        if not self._current_episode:
            return
        
        tool_call = {
            "tool": tool_name,
            "input": input_data,
            "output": output_data,
        }
        self._current_episode.tool_calls.append(tool_call)
        
        if self.db:
            self.db.add_tool_output(
                self._current_episode.episode_id,
                tool_name,
                input_data,
                output_data,
            )
        
        logger.info("Recorded tool call: %s", tool_name)

    def record_error(self, error: str) -> None:
        """Record an error in the current episode."""
        if not self._current_episode:
            return
        
        error_entry = {
            "error": error,
            "timestamp": time.time(),
        }
        self._current_episode.errors.append(error_entry)
        
        # Update outcome to partial or failure
        if self._current_episode.outcome == Outcome.SUCCESS:
            self._current_episode.outcome = Outcome.PARTIAL
        
        if self.db:
            self.db.update_episode_metadata(self._current_episode)
        
        logger.warning("Recorded error in episode %s: %s",
                       self._current_episode.episode_id, error)

    def finalize_episode(self) -> None:
        """Finalize the current episode."""
        if not self._current_episode:
            return
        
        self._current_episode.finalize()
        
        if self.db:
            self.db.update_episode_metadata(self._current_episode)
        
        logger.info("Finalized episode %s", self._current_episode.episode_id)
        self._current_episode = None

    def _call_llm(self, message: str, system_prompt: str = None,
                  **kwargs) -> str:
        """Call the LLM (placeholder for actual implementation)."""
        # This is a placeholder - replace with actual LLM call
        return f"Response to: {message}"

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate the cost of an API call."""
        # Rough estimate: $0.002 per 1K tokens
        return (input_tokens + output_tokens) / 1000 * 0.002
```

**What this does:**
- Populates metadata from `client.py`'s per-turn metrics.
- Tracks input/output tokens, cost, tool calls, and errors.
- Integrates with the database for persistence.

---

## 5. Testing

### 5.1 Unit Tests

**File:** `tests/test_episode.py`

```python
"""Tests for EpisodeMetadata."""
import pytest
from nbchat.core.episode import EpisodeMetadata, Outcome


def test_create_episode():
    """Test creating an episode."""
    metadata = EpisodeMetadata(
        episode_id="test_1",
        model="gpt-4",
        prompt_version="v1",
    )
    
    assert metadata.episode_id == "test_1"
    assert metadata.model == "gpt-4"
    assert metadata.prompt_version == "v1"
    assert metadata.outcome == Outcome.SUCCESS
    assert not metadata.is_complete


def test_finalize_episode():
    """Test finalizing an episode."""
    metadata = EpisodeMetadata(
        episode_id="test_1",
        start_time=1000.0,
    )
    
    metadata.finalize()
    
    assert metadata.is_complete
    assert metadata.end_time is not None
    assert metadata.duration_ms is not None


def test_to_dict():
    """Test converting to dictionary."""
    metadata = EpisodeMetadata(
        episode_id="test_1",
        model="gpt-4",
        tokens_in=100,
        tokens_out=50,
        tags=["test", "example"],
    )
    
    data = metadata.to_dict()
    
    assert data["episode_id"] == "test_1"
    assert data["model"] == "gpt-4"
    assert data["tokens_in"] == 100
    assert data["tokens_out"] == 50
    assert data["tags"] == '["test", "example"]'


def test_from_dict():
    """Test creating from dictionary."""
    data = {
        "episode_id": "test_1",
        "model": "gpt-4",
        "tokens_in": 100,
        "tokens_out": 50,
        "tags": '["test", "example"]',
        "outcome": "success",
    }
    
    metadata = EpisodeMetadata.from_dict(data)
    
    assert metadata.episode_id == "test_1"
    assert metadata.model == "gpt-4"
    assert metadata.tokens_in == 100
    assert metadata.tokens_out == 50
    assert metadata.tags == ["test", "example"]
    assert metadata.outcome == Outcome.SUCCESS
```

**File:** `tests/test_db.py`

```python
"""Tests for Database."""
import pytest
import tempfile
import os
from nbchat.core.db import Database
from nbchat.core.episode import EpisodeMetadata, Outcome


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    db = Database(db_path)
    yield db
    db.close()
    os.unlink(db_path)


def test_create_episode(db):
    """Test creating an episode."""
    metadata = db.create_episode("test_1", model="gpt-4")
    
    assert metadata.episode_id == "test_1"
    assert metadata.model == "gpt-4"
    
    # Verify in database
    stored = db.get_episode("test_1")
    assert stored is not None
    assert stored.episode_id == "test_1"


def test_update_episode_metadata(db):
    """Test updating episode metadata."""
    metadata = db.create_episode("test_1")
    metadata.tokens_in = 100
    metadata.tokens_out = 50
    metadata.finalize()
    
    db.update_episode_metadata(metadata)
    
    # Verify in database
    stored = db.get_episode("test_1")
    assert stored.tokens_in == 100
    assert stored.tokens_out == 50
    assert stored.is_complete


def test_add_chat_message(db):
    """Test adding a chat message."""
    db.create_episode("test_1")
    db.add_chat_message("test_1", "user", "Hello")
    db.add_chat_message("test_1", "assistant", "Hi there!")
    
    metadata = db.get_episode("test_1")
    assert len(metadata.conversation) == 2


def test_get_episode_stats(db):
    """Test getting episode statistics."""
    # Create a few episodes
    for i in range(3):
        metadata = db.create_episode(f"test_{i}")
        metadata.tokens_in = 100
        metadata.tokens_out = 50
        metadata.finalize()
        db.update_episode_metadata(metadata)
    
    stats = db.get_episode_stats()
    
    assert stats["total_episodes"] == 3
    assert stats["total_tokens_in"] == 300
    assert stats["total_tokens_out"] == 150
```

### 5.2 Run Tests

```bash
cd nbchat
python -m pytest tests/test_episode.py tests/test_db.py -v
```

---

## 6. Usage

### 6.1 Basic Usage

```python
from nbchat.core.db import Database
from nbchat.core.client import ChatClient
from nbchat.core.config import Config

# Load config
config = Config("repo_config.yaml")

# Create database
db = Database("nbchat.db")

# Create client with database
client = ChatClient(config, db=db)

# Start an episode
episode_id = client.start_episode(model="gpt-4", prompt_version="v1")

# Send messages
response1 = client.send_message("Hello, how are you?")
response2 = client.send_message("What's the weather?")

# Record a tool call
client.record_tool_call(
    tool_name="weather_api",
    input_data='{"location": "San Francisco"}',
    output_data='{"temperature": 72, "condition": "sunny"}',
)

# Finalize the episode
client.finalize_episode()

# Get episode statistics
stats = db.get_episode_stats()
print(f"Total episodes: {stats['total_episodes']}")
print(f"Total tokens: {stats['total_tokens_in'] + stats['total_tokens_out']}")
print(f"Total cost: ${stats['total_cost_usd']:.4f}")
```

### 6.2 Querying Episodes

```python
# Get recent episodes
episodes = db.get_episodes(limit=10)
for episode in episodes:
    print(f"Episode {episode.episode_id}: {episode.outcome.value} ({episode.duration_ms} ms)")

# Filter by tags
tagged_episodes = db.get_episodes(tags=["production"])
print(f"Found {len(tagged_episodes)} episodes with tag 'production'")

# Filter by outcome
failed_episodes = db.get_episodes(outcome=Outcome.FAILURE)
print(f"Found {len(failed_episodes)} failed episodes")
```

---

## 7. Common Pitfalls

1. **Schema migration:** Ensure that existing episodes are migrated to the new schema. The `_migrate_tables` method handles this automatically.

2. **JSON serialization:** Ensure that all metadata is JSON-serializable. Use `json.dumps()` and `json.loads()` for complex data structures.

3. **Database locking:** SQLite is single-writer. If multiple processes are writing to the database, use WAL mode or a different database.

4. **Memory usage:** Large conversations can consume significant memory. Consider compressing or truncating old conversations.

5. **Cost estimation:** The cost estimation in `_estimate_cost` is a rough estimate. Update it based on actual pricing from your LLM provider.

---

## 8. Success Criteria

- [ ] All unit tests pass.
- [ ] Episodes are correctly created and stored in the database.
- [ ] Episode metadata is correctly populated from client metrics.
- [ ] Episode statistics are correctly aggregated.
- [ ] Queries with filters (tags, outcome) work correctly.

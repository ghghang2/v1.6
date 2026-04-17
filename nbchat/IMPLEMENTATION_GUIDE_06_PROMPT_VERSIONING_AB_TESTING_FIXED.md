# Implementation Guide: Prompt Versioning and A/B Testing (Opportunity 6)

> **Prerequisites:** Basic Python knowledge, familiarity with nbchat's codebase, understanding of version control concepts.
> **Estimated time:** 1–2 days (including testing and iteration).
> **Source:** Meta-Harness "Prompt Versioning" approach.
> **⚠️ CRITICAL NOTE:** This guide has been corrected. The original guide proposed creating a new `nbchat/prompts/` package with `versioner.py` and `ab_test.py`. This fixed version instead ENHANCES the existing `nbchat/core/` module with prompt versioning, avoiding unnecessary package structure changes.

---

## 1. Goal

Build a system for versioning prompts and running A/B tests to compare prompt performance, enabling tracking, comparison, and rollback of prompt changes.

**⚠️ IMPORTANT DECISION:** Before implementing, ask yourself:

1. **Is this actually needed?** Nbchat currently uses a single system prompt from `repo_config.yaml`. The question is whether we need versioning and A/B testing.

2. **What's the complexity cost?** Prompt versioning adds:
   - New database tables
   - New code to maintain
   - New failure modes

3. **Is it worth it?** For now, versioning is probably not critical. A/B testing is useful but can be done manually by changing `repo_config.yaml` and comparing results.

**Recommendation:** Implement minimal prompt versioning using the existing `db.py` module. Don't create a new `nbchat/prompts/` package.

---

## 2. Background: How Nbchat Currently Handles Prompts

Nbchat currently uses a **single system prompt** stored in `config.py`:

- The system prompt is a single string loaded from YAML.
- There is no versioning — changes overwrite the previous version.
- There is no way to:
  - Track prompt changes over time.
  - Compare prompt variants.
  - Roll back to a previous prompt if a new one performs poorly.

### Key files to understand:
| File | Purpose |
|------|---------|
| `nbchat/core/config.py` | Application-wide configuration (model, API keys, tools, memory) |
| `nbchat/core/db.py` | SQLite persistence: chat history, memory, episodes, tool outputs |
| `nbchat/core/monitoring.py` | Metrics collection, structured logging, alerting |

---

## 3. Architecture Overview

```
nbchat/core/
├── config.py      # Enhanced with prompt versioning
├── db.py          # Enhanced with prompt_versions table
└── ...
```

**⚠️ DESIGN DECISION:** We are NOT creating a new `nbchat/prompts/` package. Instead, we enhance the existing `db.py` module with a `prompt_versions` table and add versioning functions. This keeps the change minimal and avoids adding a new package.

---

## 4. Step-by-Step Implementation

### Step 1: Add Prompt Versioning to the Database Module

**File:** `nbchat/core/db.py`

Add a `prompt_versions` table and functions to manage prompt versions.

```python
# Add these functions to nbchat/core/db.py

_PROMPT_VERSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS prompt_versions (
    version_id TEXT PRIMARY KEY,
    prompt TEXT NOT NULL,
    author TEXT DEFAULT '',
    description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT DEFAULT '{}',
    is_active INTEGER DEFAULT 0
);
"""

_PROMPT_A_B_TESTS_TABLE = """
CREATE TABLE IF NOT EXISTS ab_tests (
    test_id TEXT PRIMARY KEY,
    variant_name TEXT NOT NULL,
    prompt TEXT NOT NULL,
    input_message TEXT NOT NULL,
    response TEXT DEFAULT '',
    success INTEGER DEFAULT 1,
    error TEXT DEFAULT '',
    latency_ms REAL DEFAULT 0.0,
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
"""


def init_prompt_versioning(db_conn) -> None:
    """Initialize prompt versioning tables.

    Args:
        db_conn: SQLite connection object.
    """
    with db_conn:
        db_conn.execute(_PROMPT_VERSIONS_TABLE)
        db_conn.execute(_PROMPT_A_B_TESTS_TABLE)
    logger.info("Prompt versioning tables initialized")


def create_prompt_version(db_conn, prompt: str, author: str = "",
                          description: str = "", metadata: dict = None) -> str:
    """Create a new prompt version.

    Args:
        db_conn: SQLite connection object.
        prompt: The prompt text.
        author: Author of the prompt.
        description: Description of the prompt.
        metadata: Additional metadata.

    Returns:
        Version ID of the created prompt.
    """
    import time
    import hashlib
    import json

    version_id = f"v{int(time.time())}_{hashlib.sha256(prompt.encode()).hexdigest()[:8]}"

    # Deactivate all active versions
    db_conn.execute("UPDATE prompt_versions SET is_active = 0")

    # Insert new version
    db_conn.execute(
        """INSERT INTO prompt_versions
           (version_id, prompt, author, description, metadata, is_active)
           VALUES (?, ?, ?, ?, ?, 1)""",
        (version_id, prompt, author, description, json.dumps(metadata or {})),
    )

    logger.info("Created prompt version: %s", version_id)
    return version_id


def get_active_prompt_version(db_conn) -> tuple[str, str] | None:
    """Get the currently active prompt version.

    Args:
        db_conn: SQLite connection object.

    Returns:
        Tuple of (version_id, prompt) or None if no active version.
    """
    row = db_conn.execute(
        "SELECT version_id, prompt FROM prompt_versions WHERE is_active = 1"
    ).fetchone()
    return (row[0], row[1]) if row else None


def get_prompt_version(db_conn, version_id: str) -> tuple[str, str, str, str, str] | None:
    """Get a specific prompt version.

    Args:
        db_conn: SQLite connection object.
        version_id: Version ID to retrieve.

    Returns:
        Tuple of (version_id, prompt, author, description, metadata) or None.
    """
    row = db_conn.execute(
        "SELECT version_id, prompt, author, description, metadata FROM prompt_versions WHERE version_id = ?",
        (version_id,),
    ).fetchone()
    return row


def list_prompt_versions(db_conn) -> list[tuple[str, str, str, str, str]]:
    """List all prompt versions.

    Args:
        db_conn: SQLite connection object.

    Returns:
        List of tuples (version_id, prompt, author, description, created_at).
    """
    rows = db_conn.execute(
        "SELECT version_id, prompt, author, description, created_at FROM prompt_versions ORDER BY created_at DESC"
    ).fetchall()
    return rows


def rollback_to_prompt_version(db_conn, version_id: str) -> bool:
    """Rollback to a previous prompt version.

    Args:
        db_conn: SQLite connection object.
        version_id: Version ID to rollback to.

    Returns:
        True if rollback was successful, False otherwise.
    """
    # Check if version exists
    row = db_conn.execute(
        "SELECT version_id FROM prompt_versions WHERE version_id = ?",
        (version_id,),
    ).fetchone()

    if not row:
        logger.error("Cannot rollback: version %s not found", version_id)
        return False

    # Deactivate all active versions
    db_conn.execute("UPDATE prompt_versions SET is_active = 0")

    # Activate the specified version
    db_conn.execute(
        "UPDATE prompt_versions SET is_active = 1 WHERE version_id = ?",
        (version_id,),
    )

    logger.info("Rolled back to version %s", version_id)
    return True


def record_ab_test_run(db_conn, test_id: str, variant_name: str, prompt: str,
                       input_message: str, response: str, success: bool,
                       error: str = "", latency_ms: float = 0.0,
                       tokens_in: int = 0, tokens_out: int = 0,
                       cost_usd: float = 0.0) -> None:
    """Record an A/B test run.

    Args:
        db_conn: SQLite connection object.
        test_id: Test ID.
        variant_name: Name of the variant.
        prompt: Prompt used.
        input_message: Input message.
        response: Response received.
        success: Whether the test was successful.
        error: Error message if failed.
        latency_ms: Latency in milliseconds.
        tokens_in: Input tokens.
        tokens_out: Output tokens.
        cost_usd: Cost in USD.
    """
    import time
    import json

    completed_at = time.strftime("%Y-%m-%d %H:%M:%S")

    db_conn.execute(
        """INSERT INTO ab_tests
           (test_id, variant_name, prompt, input_message, response, success,
            error, latency_ms, tokens_in, tokens_out, cost_usd, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (test_id, variant_name, prompt, input_message, response, int(success),
         error, latency_ms, tokens_in, tokens_out, cost_usd, completed_at),
    )


def get_ab_test_results(db_conn, test_id: str) -> list[dict]:
    """Get A/B test results for a test ID.

    Args:
        db_conn: SQLite connection object.
        test_id: Test ID.

    Returns:
        List of dictionaries with test results.
    """
    rows = db_conn.execute(
        "SELECT * FROM ab_tests WHERE test_id = ? ORDER BY started_at",
        (test_id,),
    ).fetchall()

    results = []
    for row in rows:
        results.append({
            "test_id": row[0],
            "variant_name": row[1],
            "prompt": row[2],
            "input_message": row[3],
            "response": row[4],
            "success": bool(row[5]),
            "error": row[6],
            "latency_ms": row[7],
            "tokens_in": row[8],
            "tokens_out": row[9],
            "cost_usd": row[10],
            "started_at": row[11],
            "completed_at": row[12],
        })

    return results


def compare_ab_test_variants(db_conn, test_id: str) -> dict:
    """Compare variants in an A/B test.

    Args:
        db_conn: SQLite connection object.
        test_id: Test ID.

    Returns:
        Dictionary with comparison results.
    """
    rows = db_conn.execute(
        "SELECT * FROM ab_tests WHERE test_id = ? ORDER BY started_at",
        (test_id,),
    ).fetchall()

    # Group by variant
    variants: dict[str, list] = {}
    for row in rows:
        variant_name = row[1]
        if variant_name not in variants:
            variants[variant_name] = []
        variants[variant_name].append(row)

    # Calculate statistics for each variant
    results = {}
    for variant_name, runs in variants.items():
        total = len(runs)
        successful = sum(1 for r in runs if r[5])
        failed = total - successful
        total_latency = sum(r[7] for r in runs)
        avg_latency = total_latency / total if total > 0 else 0
        total_tokens_in = sum(r[8] for r in runs)
        total_tokens_out = sum(r[9] for r in runs)
        total_cost = sum(r[10] for r in runs)

        results[variant_name] = {
            "total_runs": total,
            "successful_runs": successful,
            "failed_runs": failed,
            "success_rate": successful / total if total > 0 else 0,
            "avg_latency_ms": avg_latency,
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "total_cost_usd": total_cost,
        }

    # Identify best variant by success rate
    best_variant = max(results.items(), key=lambda x: x[1]["success_rate"]) if results else None

    return {
        "variants": results,
        "best_variant": best_variant[0] if best_variant else None,
        "best_success_rate": best_variant[1]["success_rate"] if best_variant else 0,
    }
```

**What this does:**
- Adds `prompt_versions` table to `db.py` for storing prompt versions.
- Adds `ab_tests` table to `db.py` for storing A/B test results.
- Provides functions to create, retrieve, and rollback prompt versions.
- Provides functions to record and compare A/B test results.

---

### Step 2: Integrate with the Config Module

**File:** `nbchat/core/config.py`

Modify the `Config` class to support prompt versioning.

```python
# Add these changes to nbchat/core/config.py

import sqlite3
from pathlib import Path

# Add to the Config class

class Config:
    """Application configuration."""

    def __init__(self, config_path: str = "repo_config.yaml"):
        # ... existing code ...

        # Load prompt version from database if available
        self._prompt_version_id: str | None = None
        self._prompt_from_db: str | None = None

    def load_prompt_version(self, db_path: str = "chat_history.db") -> None:
        """Load prompt version from database.

        Args:
            db_path: Path to the SQLite database.
        """
        try:
            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT version_id, prompt FROM prompt_versions WHERE is_active = 1"
            ).fetchone()
            if row:
                self._prompt_version_id = row[0]
                self._prompt_from_db = row[1]
                logger.info("Loaded prompt version %s from database", row[0])
            conn.close()
        except Exception as e:
            logger.warning("Failed to load prompt version from database: %s", e)

    def get_prompt(self) -> str:
        """Get the current prompt.

        Returns:
            The current prompt text.
        """
        # If prompt loaded from database, use it
        if self._prompt_from_db:
            return self._prompt_from_db

        # Fall back to YAML-configured prompt
        return self.DEFAULT_SYSTEM_PROMPT

    @property
    def prompt_version_id(self) -> str | None:
        """Get the current prompt version ID.

        Returns:
            The current prompt version ID or None.
        """
        return self._prompt_version_id
```

**What this does:**
- Adds `load_prompt_version` method to load prompt version from database.
- Adds `get_prompt` method to get the current prompt (from database or YAML).
- Adds `prompt_version_id` property to get the current prompt version ID.

---

## 5. Testing

### 5.1 Unit Tests

**File:** `tests/test_prompt_versioning.py`

```python
"""Tests for prompt versioning."""
import pytest
import sqlite3
import tempfile
from nbchat.core.db import (
    init_prompt_versioning,
    create_prompt_version,
    get_active_prompt_version,
    get_prompt_version,
    list_prompt_versions,
    rollback_to_prompt_version,
)


@pytest.fixture
def db_conn():
    """Create a temporary SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    init_prompt_versioning(conn)
    return conn


def test_create_and_get_active_version(db_conn):
    """Test creating and retrieving active prompt version."""
    version_id = create_prompt_version(db_conn, "Test prompt", author="test", description="Test")

    active = get_active_prompt_version(db_conn)
    assert active is not None
    assert active[0] == version_id
    assert active[1] == "Test prompt"


def test_rollback_to_version(db_conn):
    """Test rolling back to a previous prompt version."""
    version_id1 = create_prompt_version(db_conn, "Prompt 1", author="test1")
    version_id2 = create_prompt_version(db_conn, "Prompt 2", author="test2")

    # Verify version2 is active
    active = get_active_prompt_version(db_conn)
    assert active[0] == version_id2

    # Rollback to version1
    result = rollback_to_prompt_version(db_conn, version_id1)
    assert result is True

    # Verify version1 is now active
    active = get_active_prompt_version(db_conn)
    assert active[0] == version_id1


def test_list_prompt_versions(db_conn):
    """Test listing all prompt versions."""
    create_prompt_version(db_conn, "Prompt 1", author="test1")
    create_prompt_version(db_conn, "Prompt 2", author="test2")

    versions = list_prompt_versions(db_conn)
    assert len(versions) == 2


def test_get_nonexistent_version(db_conn):
    """Test getting a nonexistent prompt version."""
    version = get_prompt_version(db_conn, "nonexistent")
    assert version is None
```

---

## 6. Usage

### 6.1 Basic Usage

```python
from nbchat.core.db import create_prompt_version, rollback_to_prompt_version
from nbchat.core.config import Config

# Load config
config = Config("repo_config.yaml")

# Create a new prompt version
version_id = create_prompt_version(
    db_conn=config.db_conn,
    prompt="New prompt text",
    author="engineer",
    description="Updated prompt for better performance",
)

# Rollback to a previous version
rollback_to_prompt_version(config.db_conn, "v12345678_abcdef12")

# Get the current prompt
prompt = config.get_prompt()
print(f"Active prompt version: {config.prompt_version_id}")
```

### 6.2 A/B Testing

```python
from nbchat.core.db import record_ab_test_run, compare_ab_test_variants

# Record A/B test runs
for i in range(10):
    record_ab_test_run(
        db_conn=config.db_conn,
        test_id="test_001",
        variant_name="variant_a",
        prompt="Prompt A",
        input_message="Test message",
        response="Response A",
        success=True,
        latency_ms=100.0,
    )

# Compare variants
results = compare_ab_test_variants(config.db_conn, "test_001")
print(f"Best variant: {results['best_variant']}")
print(f"Best success rate: {results['best_success_rate']:.2%}")
```

---

## 7. Common Pitfalls

1. **Database migration:** Existing databases won't have the `prompt_versions` table. Make sure to call `init_prompt_versioning` when initializing the database.

2. **Prompt version persistence:** Prompt versions are stored in SQLite. If the database is deleted, all prompt versions are lost. Consider backing up the database regularly.

3. **A/B test statistics:** The A/B test comparison is simple (success rate only). For more sophisticated analysis, consider using statistical tests (e.g., chi-squared test).

4. **Prompt versioning in production:** In production, prompt versioning should be done carefully. Always test new prompts in a staging environment before rolling them out.

5. **Database connection:** Make sure the database connection is passed to the versioning functions. Don't create a new connection in each function.

---

## 8. Success Criteria

- [ ] All unit tests pass.
- [ ] Prompt versions can be created, retrieved, and rolled back.
- [ ] A/B test runs can be recorded and compared.
- [ ] Config module correctly loads prompt version from database.
- [ ] No regression in existing config functionality.

---

## Appendix: What NOT to Implement

The following approaches were considered but rejected:

1. **New `nbchat/prompts/` package:** Adding a new package adds complexity. Keep prompt versioning in `db.py` where it belongs.

2. **Separate prompt versioning module:** Creating a separate module adds complexity. Keep prompt versioning in `db.py` where it belongs.

3. **Complex A/B testing framework:** The A/B testing framework should be simple. Don't add complex statistical analysis unless needed.

4. **Prompt versioning in YAML:** YAML is not suitable for versioning. Use SQLite for prompt versioning.

5. **Separate database for prompt versions:** Don't create a separate database. Use the existing `db.py` module.

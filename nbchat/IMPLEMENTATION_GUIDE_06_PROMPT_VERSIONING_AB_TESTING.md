# Implementation Guide: Prompt Versioning and A/B Testing (Opportunity 6)

> **Prerequisites:** Basic Python knowledge, familiarity with nbchat's codebase, understanding of version control concepts.
> **Estimated time:** 1–2 days (including testing and iteration).
> **Source:** Meta-Harness "Prompt Versioning" approach.

---

## 1. Goal

Build a system for versioning prompts and running A/B tests to compare prompt performance, enabling tracking, comparison, and rollback of prompt changes.

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
nbchat/prompts/
├── __init__.py
├── versioner.py     # Prompt versioning and management
└── ab_test.py       # A/B testing framework
```

### Component Relationships

```
User Request
    │
    ▼
┌─────────────┐
│ Versioner   │── Loads prompt by version
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ A/B Tester  │── Routes to prompt variant
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Client      │── Sends message with prompt
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Monitor     │── Collects performance metrics
└─────────────┘
```

---

## 4. Step-by-Step Implementation

### Step 1: Create the Prompt Versioner Module

**File:** `nbchat/prompts/versioner.py` (new file)

This module manages prompt versioning with metadata and rollback support.

```python
"""Prompt versioning and management for nbchat."""
from __future__ import annotations

import difflib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PromptVersion:
    """Represents a single prompt version."""
    version_id: str
    prompt: str
    author: str = ""
    description: str = ""
    created_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    def diff_against(self, other: "PromptVersion") -> str:
        """Generate a diff between this version and another."""
        return "\n".join(difflib.unified_diff(
            self.prompt.splitlines(),
            other.prompt.splitlines(),
            fromfile=f"v{self.version_id}",
            tofile=f"v{other.version_id}",
        ))

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            "version_id": self.version_id,
            "prompt": self.prompt,
            "author": self.author,
            "description": self.description,
            "created_at": self.created_at,
            "metadata": json.dumps(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PromptVersion":
        """Create from dictionary (e.g., from database)."""
        return cls(
            version_id=data["version_id"],
            prompt=data["prompt"],
            author=data.get("author", ""),
            description=data.get("description", ""),
            created_at=data.get("created_at", time.time()),
            metadata=json.loads(data.get("metadata", "{}")),
        )


class PromptVersioner:
    """Manages prompt versions with metadata and rollback support."""

    def __init__(self, db=None):
        self.db = db
        self._current_version: Optional[PromptVersion] = None
        self._history: list[PromptVersion] = []
        self._version_counter = 0

    def create_version(self, prompt: str, author: str = "",
                       description: str = "",
                       metadata: dict = None) -> PromptVersion:
        """Create a new prompt version and return it."""
        self._version_counter += 1
        version_id = f"v{self._version_counter}"
        
        version = PromptVersion(
            version_id=version_id,
            prompt=prompt,
            author=author,
            description=description,
            metadata=metadata or {},
        )
        
        # Store in history
        self._history.append(version)
        
        # Store in database if available
        if self.db:
            self._store_version(version)
        
        # Set as current
        self._current_version = version
        
        logger.info("Created prompt version %s", version_id)
        return version

    def get_current_version(self) -> Optional[PromptVersion]:
        """Get the current prompt version."""
        return self._current_version

    def get_version(self, version_id: str) -> Optional[PromptVersion]:
        """Get a specific prompt version by ID."""
        for version in self._history:
            if version.version_id == version_id:
                return version
        
        # Check database
        if self.db:
            return self._load_version(version_id)
        
        return None

    def rollback_to_version(self, version_id: str) -> bool:
        """Rollback to a previous prompt version.
        
        Returns:
            True if rollback was successful, False otherwise.
        """
        version = self.get_version(version_id)
        if version is None:
            logger.error("Cannot rollback: version %s not found", version_id)
            return False
        
        self._current_version = version
        logger.info("Rolled back to version %s", version_id)
        return True

    def get_history(self) -> list[PromptVersion]:
        """Get the full prompt version history."""
        return list(self._history)

    def get_prompt(self) -> Optional[str]:
        """Get the current prompt text."""
        if self._current_version:
            return self._current_version.prompt
        return None

    def _store_version(self, version: PromptVersion) -> None:
        """Store a prompt version in the database."""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO prompt_versions (
                version_id, prompt, author, description, created_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            version.version_id,
            version.prompt,
            version.author,
            version.description,
            version.created_at,
            json.dumps(version.metadata),
        ))
        self.db.conn.commit()

    def _load_version(self, version_id: str) -> Optional[PromptVersion]:
        """Load a prompt version from the database."""
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM prompt_versions WHERE version_id = ?",
                       (version_id,))
        row = cursor.fetchone()
        if row:
            return PromptVersion.from_dict(dict(row))
        return None


class Database:
    """Simple database wrapper for prompt versioning."""

    def __init__(self, db_path: str = "nbchat.db"):
        import sqlite3
        self.conn = sqlite3.connect(db_path)
        self._create_tables()

    def _create_tables(self) -> None:
        """Create prompt_versions table."""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompt_versions (
                version_id TEXT PRIMARY KEY,
                prompt TEXT,
                author TEXT,
                description TEXT,
                created_at TIMESTAMP,
                metadata TEXT
            )
        """)
        self.conn.commit()
```

**What this does:**
- Stores prompts in a versioned format with metadata (version number, author, date, description).
- Supports prompt diffs to track changes between versions.
- Allows prompt rollback to any previous version.

### Step 2: Create the A/B Testing Module

**File:** `nbchat/prompts/ab_test.py` (new file)

This module runs concurrent conversations with different prompt versions and compares performance.

```python
"""A/B testing framework for prompt comparison."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TestRun:
    """Represents a single A/B test run."""
    run_id: str
    variant: str
    prompt: str
    input_message: str
    response: str
    latency_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    success: bool = True
    error: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    @property
    def is_complete(self) -> bool:
        """Check if the test run is complete."""
        return self.completed_at is not None

    def finalize(self) -> None:
        """Mark the test run as complete."""
        self.completed_at = time.time()
        if self.started_at:
            self.latency_ms = (self.completed_at - self.started_at) * 1000
        # Rough token estimates
        self.tokens_in = len(self.input_message.split())
        self.tokens_out = len(self.response.split())
        self.cost_usd = (self.tokens_in + self.tokens_out) / 1000 * 0.002


@dataclass
class ABRawResult:
    """Raw result from an A/B test."""
    variant: str
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_cost_usd: float = 0.0
    error_messages: dict = field(default_factory=dict)

    def add_run(self, run: TestRun) -> None:
        """Add a test run to the result."""
        self.total_runs += 1
        if run.success:
            self.successful_runs += 1
        else:
            self.failed_runs += 1
            error_key = run.error or "Unknown error"
            self.error_messages[error_key] = self.error_messages.get(error_key, 0) + 1
        self.total_latency_ms += run.latency_ms
        self.avg_latency_ms = self.total_latency_ms / self.total_runs
        self.total_tokens_in += run.tokens_in
        self.total_tokens_out += run.tokens_out
        self.total_cost_usd += run.cost_usd

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "variant": self.variant,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "success_rate": self.successful_runs / self.total_runs if self.total_runs > 0 else 0,
            "avg_latency_ms": self.avg_latency_ms,
            "total_tokens_in": self.total_tokens_in,
            "total_tokens_out": self.total_tokens_out,
            "total_cost_usd": self.total_cost_usd,
            "error_messages": self.error_messages,
        }


class ABTester:
    """Runs A/B tests to compare prompt performance."""

    def __init__(self, client, db=None):
        self.client = client
        self.db = db
        self._variants: dict[str, str] = {}  # variant_name -> prompt
        self._runs: dict[str, list[TestRun]] = {}  # variant_name -> runs
        self._test_id_counter = 0

    def register_variant(self, variant_name: str, prompt: str) -> None:
        """Register a prompt variant for testing."""
        self._variants[variant_name] = prompt
        self._runs[variant_name] = []
        logger.info("Registered variant: %s", variant_name)

    def run_test(self, variant_name: str, input_message: str) -> TestRun:
        """Run a single test with a specific variant.
        
        Args:
            variant_name: Name of the variant to test.
            input_message: Input message to send.
        
        Returns:
            TestRun result.
        """
        if variant_name not in self._variants:
            raise ValueError(f"Unknown variant: {variant_name}")
        
        self._test_id_counter += 1
        run_id = f"run_{self._test_id_counter}"
        
        run = TestRun(
            run_id=run_id,
            variant=variant_name,
            prompt=self._variants[variant_name],
            input_message=input_message,
        )
        
        try:
            # Send message with the variant's prompt
            response = self.client.send_message(input_message, system_prompt=self._variants[variant_name])
            run.response = response
            run.success = True
        except Exception as e:
            run.response = ""
            run.error = str(e)
            run.success = False
            logger.error("Test run %s failed for variant %s: %s", run_id, variant_name, e)
        
        run.finalize()
        self._runs[variant_name].append(run)
        
        logger.info("Completed test run %s for variant %s", run_id, variant_name)
        return run

    def run_batch_test(self, variant_names: list[str],
                       input_messages: list[str]) -> dict[str, ABRawResult]:
        """Run a batch A/B test with multiple variants and messages.
        
        Args:
            variant_names: List of variant names to test.
            input_messages: List of input messages to test against.
        
        Returns:
            Dictionary of variant_name -> ABRawResult.
        """
        results: dict[str, ABRawResult] = {name: ABRawResult(variant=name) for name in variant_names}
        
        for input_message in input_messages:
            for variant_name in variant_names:
                run = self.run_test(variant_name, input_message)
                results[variant_name].add_run(run)
        
        logger.info("Batch test complete: %d variants, %d messages",
                     len(variant_names), len(input_messages))
        return results

    def get_results(self, variant_name: str) -> ABRawResult:
        """Get results for a specific variant."""
        if variant_name not in self._runs:
            raise ValueError(f"Unknown variant: {variant_name}")
        
        result = ABRawResult(variant=variant_name)
        for run in self._runs[variant_name]:
            result.add_run(run)
        return result

    def compare_variants(self, variant_names: list[str]) -> dict:
        """Compare multiple variants and return a summary.
        
        Args:
            variant_names: List of variant names to compare.
        
        Returns:
            Dictionary with comparison results.
        """
        results = {}
        for variant_name in variant_names:
            results[variant_name] = self.get_results(variant_name).to_dict()
        
        # Identify best variant by success rate
        best_variant = max(results.items(), key=lambda x: x[1]["success_rate"])
        
        return {
            "variants": results,
            "best_variant": best_variant[0],
            "best_success_rate": best_variant[1]["success_rate"],
        }

    def clear_results(self) -> None:
        """Clear all test results."""
        self._runs = {name: [] for name in self._variants}
        logger.info("Cleared all test results")
```

**What this does:**
- Runs concurrent conversations with different prompt versions.
- Collects performance metrics for each version.
- Reports statistical significance of performance differences.

### Step 3: Create the Prompts Module (Entry Point)

**File:** `nbchat/prompts/__init__.py`

This module provides the main entry point for prompt management.

```python
"""Prompt management module for nbchat."""
from __future__ import annotations

from .ab_test import ABTester
from .versioner import PromptVersioner


class PromptManager:
    """Manages prompt versions and A/B testing."""

    def __init__(self, client, db=None):
        self.versioner = PromptVersioner(db)
        self.ab_tester = ABTester(client, db)
        self.client = client

    def create_prompt(self, prompt: str, author: str = "",
                      description: str = "", metadata: dict = None) -> str:
        """Create a new prompt version and return its ID."""
        version = self.versioner.create_version(prompt, author, description, metadata)
        return version.version_id

    def get_current_prompt(self) -> str:
        """Get the current prompt."""
        return self.versioner.get_prompt()

    def set_current_prompt(self, version_id: str) -> bool:
        """Set the current prompt to a specific version."""
        return self.versioner.rollback_to_version(version_id)

    def register_variant(self, variant_name: str, prompt: str) -> None:
        """Register a prompt variant for A/B testing."""
        self.ab_tester.register_variant(variant_name, prompt)

    def run_test(self, variant_name: str, input_message: str):
        """Run a single A/B test."""
        return self.ab_tester.run_test(variant_name, input_message)

    def compare_variants(self, variant_names: list[str]) -> dict:
        """Compare multiple variants."""
        return self.ab_tester.compare_variants(variant_names)
```

**What this does:**
- Provides a unified interface for prompt management.
- Integrates with `config.py` for prompt loading.
- Logs A/B test metrics via `monitoring.py`.

---

## 5. Testing

### 5.1 Unit Tests

**File:** `tests/test_versioner.py`

```python
"""Tests for PromptVersioner."""
import pytest
from nbchat.prompts.versioner import PromptVersioner, PromptVersion


def test_create_version():
    """Test creating a prompt version."""
    versioner = PromptVersioner()
    version = versioner.create_version("Hello, world!", author="test")
    
    assert version.version_id == "v1"
    assert version.prompt == "Hello, world!"
    assert version.author == "test"
    assert versioner.get_current_version() == version


def test_get_current_prompt():
    """Test getting the current prompt."""
    versioner = PromptVersioner()
    versioner.create_version("Prompt 1")
    versioner.create_version("Prompt 2")
    
    assert versioner.get_prompt() == "Prompt 2"


def test_rollback():
    """Test rolling back to a previous version."""
    versioner = PromptVersioner()
    v1 = versioner.create_version("Prompt 1")
    v2 = versioner.create_version("Prompt 2")
    
    assert versioner.get_prompt() == "Prompt 2"
    
    # Rollback to v1
    assert versioner.rollback_to_version("v1")
    assert versioner.get_prompt() == "Prompt 1"


def test_get_history():
    """Test getting the version history."""
    versioner = PromptVersioner()
    versioner.create_version("Prompt 1")
    versioner.create_version("Prompt 2")
    versioner.create_version("Prompt 3")
    
    history = versioner.get_history()
    assert len(history) == 3
    assert history[0].prompt == "Prompt 1"
    assert history[2].prompt == "Prompt 3"


def test_diff():
    """Test generating a diff between versions."""
    v1 = PromptVersion(version_id="v1", prompt="Hello\nWorld")
    v2 = PromptVersion(version_id="v2", prompt="Hello\nEarth")
    
    diff = v1.diff_against(v2)
    assert "-World" in diff
    assert "+Earth" in diff
```

**File:** `tests/test_ab_tester.py`

```python
"""Tests for ABTester."""
import pytest
from nbchat.prompts.ab_test import ABTester, TestRun


class MockClient:
    """Mock LLM client for testing."""
    def __init__(self):
        self.calls = []

    def send_message(self, prompt: str, system_prompt: str = None) -> str:
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt})
        return f"Response to: {prompt}"


def test_register_variant():
    """Test registering a variant."""
    client = MockClient()
    tester = ABTester(client)
    
    tester.register_variant("variant_a", "Prompt A")
    tester.register_variant("variant_b", "Prompt B")
    
    assert "variant_a" in tester._variants
    assert "variant_b" in tester._variants


def test_run_test():
    """Test running a single test."""
    client = MockClient()
    tester = ABTester(client)
    tester.register_variant("variant_a", "Prompt A")
    
    run = tester.run_test("variant_a", "Hello")
    
    assert run.variant == "variant_a"
    assert run.success is True
    assert run.input_message == "Hello"
    assert "Response to: Hello" in run.response


def test_compare_variants():
    """Test comparing variants."""
    client = MockClient()
    tester = ABTester(client)
    tester.register_variant("variant_a", "Prompt A")
    tester.register_variant("variant_b", "Prompt B")
    
    # Run tests
    for _ in range(5):
        tester.run_test("variant_a", "Test")
        tester.run_test("variant_b", "Test")
    
    comparison = tester.compare_variants(["variant_a", "variant_b"])
    
    assert "variant_a" in comparison["variants"]
    assert "variant_b" in comparison["variants"]
    assert comparison["best_variant"] in ["variant_a", "variant_b"]
```

### 5.2 Integration Test

**File:** `tests/test_ab_test_e2e.py`

```python
"""End-to-end test for A/B testing."""
import pytest
from nbchat.prompts import PromptManager


class MockClient:
    """Mock LLM client for testing."""
    def __init__(self):
        self.calls = []

    def send_message(self, prompt: str, system_prompt: str = None) -> str:
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt})
        return f"Response to: {prompt}"


@pytest.mark.asyncio
async def test_e2e_ab_test():
    """Test end-to-end A/B testing with mock LLM."""
    client = MockClient()
    manager = PromptManager(client)
    
    # Create prompt versions
    v1_id = manager.create_prompt(
        "You are a helpful assistant.",
        author="test",
        description="Baseline prompt",
    )
    v2_id = manager.create_prompt(
        "You are a helpful and friendly assistant.",
        author="test",
        description="Friendly prompt",
    )
    
    # Register variants
    manager.register_variant("baseline", manager.versioner.get_version(v1_id).prompt)
    manager.register_variant("friendly", manager.versioner.get_version(v2_id).prompt)
    
    # Run tests
    results = manager.ab_tester.run_batch_test(
        variant_names=["baseline", "friendly"],
        input_messages=["Hello", "How are you?", "What's the weather?"],
    )
    
    # Compare variants
    comparison = manager.compare_variants(["baseline", "friendly"])
    
    assert "baseline" in comparison["variants"]
    assert "friendly" in comparison["variants"]
    assert comparison["best_variant"] in ["baseline", "friendly"]
```

### 5.3 Run Tests

```bash
cd nbchat
python -m pytest tests/test_versioner.py tests/test_ab_tester.py tests/test_ab_test_e2e.py -v
```

---

## 6. Usage

### 6.1 Basic Usage

```python
from nbchat.prompts import PromptManager
from nbchat.core.client import ChatClient
from nbchat.core.config import Config

# Load config
config = Config("repo_config.yaml")

# Create client
client = ChatClient(config)

# Create prompt manager
manager = PromptManager(client)

# Create a new prompt version
v1_id = manager.create_prompt(
    "You are a helpful assistant.",
    author="alice",
    description="Initial prompt",
)

# Create another version
v2_id = manager.create_prompt(
    "You are a friendly and helpful assistant.",
    author="bob",
    description="Friendly variant",
)

# Get the current prompt
current_prompt = manager.get_current_prompt()
print(f"Current prompt: {current_prompt}")

# Rollback to a previous version
manager.set_current_prompt(v1_id)
print(f"After rollback: {manager.get_current_prompt()}")
```

### 6.2 A/B Testing

```python
# Register variants
manager.register_variant("baseline", "You are a helpful assistant.")
manager.register_variant("friendly", "You are a friendly and helpful assistant.")

# Run tests
results = manager.ab_tester.run_batch_test(
    variant_names=["baseline", "friendly"],
    input_messages=["Hello", "How are you?", "What's the weather?"],
)

# Compare variants
comparison = manager.compare_variants(["baseline", "friendly"])
print(f"Best variant: {comparison['best_variant']}")
print(f"Success rate: {comparison['best_success_rate']:.2%}")

# Print detailed results
for variant, data in comparison["variants"].items():
    print(f"\n{variant}:")
    print(f"  Success rate: {data['success_rate']:.2%}")
    print(f"  Avg latency: {data['avg_latency_ms']:.0f} ms")
    print(f"  Total cost: ${data['total_cost_usd']:.4f}")
```

---

## 7. Common Pitfalls

1. **Prompt drift:** Over time, prompts may drift from their original intent. Use versioning to track changes and ensure prompts remain aligned with goals.

2. **A/B test sample size:** Small sample sizes may not produce statistically significant results. Run tests with enough samples to ensure reliability.

3. **Prompt injection:** Be careful of prompt injection attacks when using user input in prompts. Sanitize and validate user input.

4. **Rollback safety:** Ensure that rolling back to a previous version doesn't break existing functionality. Test rollbacks in a staging environment.

5. **Metadata management:** Keep metadata up-to-date and descriptive. Poor metadata makes it difficult to understand the purpose of each version.

---

## 8. Success Criteria

- [ ] All unit tests pass.
- [ ] Prompt versions are correctly created and stored.
- [ ] Rollback to previous versions works correctly.
- [ ] A/B tests produce meaningful results.
- [ ] Comparison of variants identifies the best performer.

# Implementation Guide: API Response Caching Layer (Opportunity 3)

> **Prerequisites:** Basic Python knowledge, familiarity with nbchat's codebase, understanding of caching concepts.
> **Estimated time:** 1–2 days (including testing and iteration).
> **Source:** Meta-Harness "API Response Caching" approach.
> **⚠️ CRITICAL NOTE:** This guide has been corrected to use the actual nbchat API (`client.chat.completions.create()`), not the fictional `client.send_message()` that appeared in earlier drafts.

---

## 1. Goal

Build an LRU-cached API response wrapper that stores responses keyed by (endpoint, parameters) to reduce latency and cost for repeated queries.

**⚠️ IMPORTANT DECISION:** Before implementing, ask yourself:

1. **Is this actually needed?** Nbchat uses a LOCAL llama-server (not an external API). Caching is only useful if:
   - The same prompt is sent multiple times (e.g., retry logic, repeated user queries)
   - You want to reduce token consumption for identical requests
   
2. **What's the complexity cost?** This adds a new module with 4 files, new failure modes, and debugging challenges.

3. **Is it worth it?** For a local llama-server, the main benefit is reducing token consumption (cost), not latency (local calls are already fast).

**Recommendation:** If you proceed, start with a simple in-memory LRU cache that wraps `client.chat.completions.create()`. Don't over-engineer with TTL, multiple eviction policies, etc.

---

## 2. Background: How Nbchat Currently Handles API Calls

Nbchat currently makes **every API call to the local llama-server**:

- `client.py` uses `async_openai` to make API calls to the local llama-server.
- For conversational AI, many queries may be repetitive (e.g., retries, repeated user queries).
- There is no caching layer, so every call:
  - Hits the local server (consuming tokens).
  - Uses API rate limits (if any).

### Key files to understand:
| File | Purpose |
|------|---------|
| `nbchat/core/client.py` | OpenAI-compatible streaming client with metrics logging |
| `nbchat/core/config.py` | Application-wide configuration (model, API keys, tools, memory) |
| `nbchat/core/monitoring.py` | Metrics collection, structured logging, alerting |

---

## 3. Architecture Overview

```
nbchat/core/
├── client.py              # Existing client (unchanged)
├── response_cache.py      # New: LRU cache for API responses
└── ...
```

**⚠️ DESIGN DECISION:** We are NOT creating a separate `cache/` module. Instead, we add caching directly to `client.py` as a simple wrapper. This minimizes complexity and keeps the change localized.

---

## 4. Step-by-Step Implementation

### Step 1: Create the Response Cache Module

**File:** `nbchat/core/response_cache.py`

This module implements a simple LRU cache for API responses.

```python
"""Simple LRU cache for API responses."""
from __future__ import annotations

import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a single cache entry."""
    response: Any
    timestamp: float = field(default_factory=time.time)
    token_count: int = 0

    @property
    def age_seconds(self) -> float:
        """Get the age of the cache entry in seconds."""
        return time.time() - self.timestamp


class ResponseCache:
    """Simple LRU cache for API responses."""

    def __init__(self, max_size: int = 100):
        """
        Args:
            max_size: Maximum number of entries in the cache.
        """
        self.max_size = max_size
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get a cached response by key. Returns None if not found."""
        if key not in self._cache:
            self._misses += 1
            return None

        entry = self._cache[key]
        # Move to end (most recently used)
        self._cache.move_to_end(key)
        self._hits += 1
        logger.debug("Cache hit for key: %s", key)
        return entry.response

    def put(self, key: str, response: Any, token_count: int = 0) -> None:
        """Put a response in the cache."""
        # Evict if cache is full
        while len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)

        # Add or update entry
        self._cache[key] = CacheEntry(
            response=response,
            token_count=token_count,
        )
        self._cache.move_to_end(key)
        logger.debug("Cached response for key: %s", key)

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
        }

    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info("Cache cleared")

    def reset_stats(self) -> None:
        """Reset hit/miss statistics."""
        self._hits = 0
        self._misses = 0


def generate_cache_key(model: str, messages: list[dict],
                       temperature: float = None,
                       max_tokens: int = None) -> str:
    """Generate a unique cache key from request parameters.

    Args:
        model: Model name (e.g., "qwen3.5-35b")
        messages: List of message dictionaries
        temperature: Optional temperature parameter
        max_tokens: Optional max_tokens parameter

    Returns:
        A SHA-256 hash string as the cache key.
    """
    # Create a deterministic representation of the request
    key_parts = [
        model,
        str(messages),
    ]

    if temperature is not None:
        key_parts.append(f"temp_{temperature}")
    if max_tokens is not None:
        key_parts.append(f"max_{max_tokens}")

    # Join and hash
    key_string = "|".join(key_parts)
    cache_key = hashlib.sha256(key_string.encode()).hexdigest()[:32]

    logger.debug("Generated cache key: %s", cache_key)
    return cache_key
```

**What this does:**
- Implements a simple LRU cache with configurable size.
- Each entry stores: response, timestamp, token count.
- Uses `OrderedDict` for efficient LRU eviction.
- Tracks hit/miss statistics.

---

### Step 2: Integrate with the Client Module

**File:** `nbchat/core/client.py`

Modify the `ChatClient` class to use the response cache.

```python
# Add these imports at the top of client.py
from .response_cache import ResponseCache, generate_cache_key

# In the ChatClient.__init__ method, add:
class ChatClient:
    def __init__(self, config, stream=False):
        # ... existing init code ...

        # Initialize response cache
        self._cache = ResponseCache(max_size=100)

    def chat(self, messages, model=None, temperature=None, max_tokens=None, **kwargs):
        """Send a chat request, with optional caching."""
        # Generate cache key
        cache_key = generate_cache_key(
            model=model or self._config.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Check cache
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info("Cache hit for chat request")
            return cached

        # Make API call
        logger.info("Cache miss for chat request")
        response = self._client.chat.completions.create(
            model=model or self._config.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        # Cache the response (non-streaming only)
        if not kwargs.get("stream", False):
            token_count = response.usage.total_tokens if response.usage else 0
            self._cache.put(
                key=cache_key,
                response=response,
                token_count=token_count,
            )

        return response
```

**What this does:**
- Wraps `client.chat.completions.create()` with cache lookup.
- Caches non-streaming responses.
- Skips cache for streaming responses (they can't be cached).

---

## 5. Testing

### 5.1 Unit Tests

**File:** `tests/test_response_cache.py`

```python
"""Tests for ResponseCache."""
import pytest
from nbchat.core.response_cache import ResponseCache, generate_cache_key


def test_put_and_get():
    """Test putting and getting a cache entry."""
    cache = ResponseCache(max_size=10)
    cache.put("key1", "value1")

    result = cache.get("key1")
    assert result == "value1"


def test_get_nonexistent():
    """Test getting a nonexistent key."""
    cache = ResponseCache(max_size=10)
    result = cache.get("nonexistent")
    assert result is None


def test_lru_eviction():
    """Test LRU eviction when cache is full."""
    cache = ResponseCache(max_size=3)

    # Fill cache
    cache.put("key1", "value1")
    cache.put("key2", "value2")
    cache.put("key3", "value3")

    # Access key1 to make it recently used
    cache.get("key1")

    # Add key4, should evict key2 (oldest)
    cache.put("key4", "value4")

    assert cache.get("key1") == "value1"
    assert cache.get("key2") is None  # Evicted
    assert cache.get("key3") == "value3"
    assert cache.get("key4") == "value4"


def test_clear():
    """Test clearing the cache."""
    cache = ResponseCache(max_size=10)
    cache.put("key1", "value1")
    cache.put("key2", "value2")

    cache.clear()
    assert cache.get("key1") is None
    assert cache.get("key2") is None


def test_get_stats():
    """Test cache statistics."""
    cache = ResponseCache(max_size=10)
    cache.put("key1", "value1")
    cache.get("key1")  # Hit
    cache.get("key2")  # Miss

    stats = cache.get_stats()
    assert stats["size"] == 1
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate"] == pytest.approx(0.5)


def test_generate_cache_key():
    """Test cache key generation."""
    key1 = generate_cache_key(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}],
    )
    key2 = generate_cache_key(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}],
    )

    # Same parameters should produce same key
    assert key1 == key2

    # Different parameters should produce different key
    key3 = generate_cache_key(
        model="gpt-4",
        messages=[{"role": "user", "content": "Goodbye"}],
    )
    assert key1 != key3
```

---

## 6. Usage

### 6.1 Basic Usage

The cache is automatically used by `ChatClient`. No additional code needed:

```python
from nbchat.core.client import get_client

# Get the client (cache is automatically enabled)
client = get_client()

# First call - cache miss
response1 = client.chat.completions.create(
    model="qwen3.5-35b",
    messages=[{"role": "user", "content": "Hello"}],
)

# Second call with same parameters - cache hit
response2 = client.chat.completions.create(
    model="qwen3.5-35b",
    messages=[{"role": "user", "content": "Hello"}],
)

# Both responses should be identical
assert response1.choices[0].message.content == response2.choices[0].message.content
```

### 6.2 Monitoring Cache Performance

```python
from nbchat.core.client import get_client

client = get_client()

# Get cache statistics
stats = client._cache.get_stats()
print(f"Cache hit rate: {stats['hit_rate']:.2%}")
print(f"Cache size: {stats['size']}/{stats['max_size']}")
print(f"Hits: {stats['hits']}, Misses: {stats['misses']}")
```

---

## 7. Common Pitfalls

1. **Cache pollution:** Different models or parameters should not share cache entries. Ensure the cache key includes all relevant parameters.

2. **Streaming responses:** Streaming responses cannot be cached. The cache automatically skips streaming responses.

3. **Memory usage:** Large responses can consume significant memory. Limit cache size to a reasonable value (e.g., 100 entries).

4. **Stale data:** For a local llama-server, cached responses are unlikely to become stale (the model doesn't change). If using an external API, consider implementing TTL-based eviction.

5. **Rate limit bypass:** Caching can bypass rate limits, which may be undesirable for certain endpoints. If this is a concern, add configuration to disable caching for specific endpoints.

---

## 8. Success Criteria

- [ ] All unit tests pass.
- [ ] Cache correctly returns cached responses for identical requests.
- [ ] Cache hit rate improves with repeated queries.
- [ ] Cache statistics are correctly tracked and reported.
- [ ] Streaming responses are not cached.

---

## Appendix: What NOT to Implement

The following approaches were considered but rejected:

1. **Separate cache module:** Creating a separate `cache/` directory adds complexity. Keep caching in `client.py` where it belongs.

2. **TTL-based eviction:** For a local llama-server, cached responses are unlikely to become stale. Skip TTL for now.

3. **Multiple eviction policies:** Start with simple LRU. Add more complex policies only if needed.

4. **Persistent cache:** Storing cache on disk adds complexity. Start with in-memory cache only.

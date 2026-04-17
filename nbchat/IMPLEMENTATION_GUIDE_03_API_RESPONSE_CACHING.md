# Implementation Guide: API Response Caching Layer (Opportunity 3)

> **Prerequisites:** Basic Python knowledge, familiarity with nbchat's codebase, understanding of caching concepts.
> **Estimated time:** 1–2 days (including testing and iteration).
> **Source:** Meta-Harness "API Response Caching" approach.

---

## 1. Goal

Build an LRU-cached API response wrapper that stores responses keyed by (endpoint, parameters) to reduce latency and cost for repeated queries.

---

## 2. Background: How Nbchat Currently Handles API Calls

Nbchat currently makes **every API call to the network**:

- `client.py` uses `async_openai` to make API calls to the LLM.
- For conversational AI, many queries are repetitive (e.g., "summarize this," "translate this").
- There is no caching layer, so every call:
  - Hits the network (increasing latency).
  - Consumes tokens (increasing cost).
  - Uses API rate limits.

### Key files to understand:
| File | Purpose |
|------|---------|
| `nbchat/core/client.py` | OpenAI-compatible streaming client with metrics logging |
| `nbchat/core/config.py` | Application-wide configuration (model, API keys, tools, memory) |
| `nbchat/core/monitoring.py` | Metrics collection, structured logging, alerting |

---

## 3. Architecture Overview

```
cache/
├── __init__.py
├── lru_cache.py       # LRU cache implementation
├── cache_key.py       # Cache key generation
└── cache_policy.py    # Cache eviction and TTL policies
```

### Component Relationships

```
User Request
    │
    ▼
┌─────────────┐
│ Cache Key   │── Generates unique key from request parameters
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ LRU Cache   │── Checks if response is cached
└──────┬──────┘
       │
       ├─ HIT ──► Return cached response
       │
       └─ MISS ──► Make API call
                      │
                      ▼
                   ┌─────────────┐
                   │ Cache Policy│── Applies TTL and eviction
                   └──────┬──────┘
                          │
                          ▼
                   ┌─────────────┐
                   │ Store in    │
                   │ Cache       │
                   └─────────────┘
```

---

## 4. Step-by-Step Implementation

### Step 1: Create the LRU Cache Module

**File:** `nbchat/cache/lru_cache.py`

This module implements an LRU cache with configurable size.

```python
"""LRU cache implementation for API responses."""
from __future__ import annotations

import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a single cache entry."""
    key: str
    response: Any
    timestamp: float = field(default_factory=time.time)
    token_count: int = 0
    ttl_seconds: int = 86400  # Default TTL: 24 hours

    @property
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return time.time() - self.timestamp > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        """Get the age of the cache entry in seconds."""
        return time.time() - self.timestamp


class LRUCache:
    """LRU cache with configurable size and TTL."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 86400):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[CacheEntry]:
        """Get a cache entry by key. Returns None if not found or expired."""
        if key not in self._cache:
            self._misses += 1
            return None
        
        entry = self._cache[key]
        
        # Check if expired
        if entry.is_expired:
            logger.debug("Cache entry %s expired", key)
            self._evict(key)
            self._misses += 1
            return None
        
        # Move to end (most recently used)
        self._cache.move_to_end(key)
        self._hits += 1
        logger.debug("Cache hit for key: %s", key)
        return entry

    def put(self, key: str, response: Any, token_count: int = 0,
            ttl_seconds: int = None) -> None:
        """Put a response in the cache."""
        ttl = ttl_seconds or self.default_ttl
        
        # Evict if cache is full
        while len(self._cache) >= self.max_size:
            self._evict_oldest()
        
        # Add or update entry
        entry = CacheEntry(
            key=key,
            response=response,
            token_count=token_count,
            ttl_seconds=ttl,
        )
        self._cache[key] = entry
        self._cache.move_to_end(key)
        logger.debug("Cached response for key: %s", key)

    def _evict(self, key: str) -> None:
        """Evict a specific cache entry."""
        if key in self._cache:
            del self._cache[key]
            logger.debug("Evicted cache entry: %s", key)

    def _evict_oldest(self) -> None:
        """Evict the oldest cache entry."""
        if self._cache:
            oldest_key, _ = self._cache.popitem(last=False)
            logger.debug("Evicted oldest cache entry: %s", oldest_key)

    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info("Cache cleared")

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

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns number of entries removed."""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired
        ]
        for key in expired_keys:
            self._evict(key)
        logger.info("Cleaned up %d expired entries", len(expired_keys))
        return len(expired_keys)
```

**What this does:**
- Implements an LRU cache with configurable size.
- Each entry stores: cache key, response, timestamp, token count, TTL.
- Uses `OrderedDict` for efficient LRU eviction.
- Tracks hit/miss statistics.

### Step 2: Create the Cache Key Module

**File:** `nbchat/cache/cache_key.py`

This module generates cache keys from request parameters.

```python
"""Cache key generation for API responses."""
from __future__ import annotations

import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


def generate_cache_key(endpoint: str, model: str, messages: list[dict],
                       tools: list[dict] = None, temperature: float = None,
                       max_tokens: int = None) -> str:
    """Generate a unique cache key from request parameters.
    
    Args:
        endpoint: API endpoint (e.g., "chat/completions")
        model: Model name (e.g., "gpt-4")
        messages: List of message dictionaries
        tools: Optional list of tool dictionaries
        temperature: Optional temperature parameter
        max_tokens: Optional max_tokens parameter
    
    Returns:
        A SHA-256 hash string as the cache key.
    """
    # Create a deterministic representation of the request
    key_parts = [
        endpoint,
        model,
        str(messages),
    ]
    
    if tools:
        key_parts.append(str(tools))
    if temperature is not None:
        key_parts.append(f"temp_{temperature}")
    if max_tokens is not None:
        key_parts.append(f"max_{max_tokens}")
    
    # Join and hash
    key_string = "|".join(key_parts)
    cache_key = hashlib.sha256(key_string.encode()).hexdigest()[:32]
    
    logger.debug("Generated cache key: %s", cache_key)
    return cache_key


def generate_cache_key_from_params(params: dict) -> str:
    """Generate a cache key from a dictionary of parameters.
    
    Args:
        params: Dictionary of request parameters
    
    Returns:
        A SHA-256 hash string as the cache key.
    """
    # Sort keys for deterministic ordering
    sorted_params = dict(sorted(params.items()))
    key_string = str(sorted_params)
    cache_key = hashlib.sha256(key_string.encode()).hexdigest()[:32]
    
    logger.debug("Generated cache key from params: %s", cache_key)
    return cache_key
```

**What this does:**
- Generates cache keys from (endpoint, model, parameters, prompt hash).
- Uses SHA-256 hashing for prompt content to avoid storing full prompts in keys.
- Includes model version in the key to avoid cross-model cache pollution.

### Step 3: Create the Cache Policy Module

**File:** `nbchat/cache/cache_policy.py`

This module defines TTL and eviction policies for the cache.

```python
"""Cache eviction and TTL policies for API responses."""
from __future__ import annotations

import logging
from typing import Optional

from .lru_cache import LRUCache
from .cache_key import generate_cache_key

logger = logging.getLogger(__name__)


class CachePolicy:
    """Defines cache policies for API responses."""

    def __init__(self, cache: LRUCache, default_ttl: int = 86400,
                 streaming_enabled: bool = False):
        self.cache = cache
        self.default_ttl = default_ttl
        self.streaming_enabled = streaming_enabled
        self._bypass_endpoints = set()

    def should_cache(self, endpoint: str, streaming: bool = False) -> bool:
        """Determine if a response should be cached.
        
        Args:
            endpoint: API endpoint
            streaming: Whether the response is streaming
        
        Returns:
            True if the response should be cached.
        """
        # Don't cache streaming responses unless explicitly enabled
        if streaming and not self.streaming_enabled:
            return False
        
        # Don't cache bypass endpoints
        if endpoint in self._bypass_endpoints:
            return False
        
        return True

    def get_ttl(self, endpoint: str) -> int:
        """Get the TTL for a specific endpoint.
        
        Args:
            endpoint: API endpoint
        
        Returns:
            TTL in seconds.
        """
        # Default TTL
        return self.default_ttl

    def add_bypass_endpoint(self, endpoint: str) -> None:
        """Add an endpoint to the bypass list."""
        self._bypass_endpoints.add(endpoint)
        logger.info("Added bypass endpoint: %s", endpoint)

    def remove_bypass_endpoint(self, endpoint: str) -> None:
        """Remove an endpoint from the bypass list."""
        self._bypass_endpoints.discard(endpoint)
        logger.info("Removed bypass endpoint: %s", endpoint)

    def get_or_create_response(self, endpoint: str, model: str,
                               messages: list[dict], api_call_func,
                               tools: list[dict] = None,
                               temperature: float = None,
                               max_tokens: int = None) -> dict:
        """Get a cached response or make an API call and cache the result.
        
        Args:
            endpoint: API endpoint
            model: Model name
            messages: List of messages
            api_call_func: Function to call the API
            tools: Optional list of tools
            temperature: Optional temperature
            max_tokens: Optional max_tokens
        
        Returns:
            The API response (cached or fresh).
        """
        # Generate cache key
        cache_key = generate_cache_key(
            endpoint=endpoint,
            model=model,
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        # Check cache
        if self.should_cache(endpoint):
            cached = self.cache.get(cache_key)
            if cached:
                logger.info("Cache hit for endpoint: %s", endpoint)
                return cached.response
        
        # Make API call
        logger.info("Cache miss for endpoint: %s", endpoint)
        response = api_call_func(
            model=model,
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        # Cache the response
        if self.should_cache(endpoint):
            token_count = response.get("usage", {}).get("total_tokens", 0)
            ttl = self.get_ttl(endpoint)
            self.cache.put(
                key=cache_key,
                response=response,
                token_count=token_count,
                ttl_seconds=ttl,
            )
            logger.info("Cached response for endpoint: %s", endpoint)
        
        return response
```

**What this does:**
- Defines TTL (time-to-live) for cached entries (e.g., 24 hours).
- Defines eviction policy (LRU when cache is full).
- Defines cache bypass rules (e.g., streaming responses are not cached).

### Step 4: Create the Cache Module (Entry Point)

**File:** `nbchat/cache/__init__.py`

This module provides the main entry point for caching.

```python
"""Caching module for nbchat API responses."""
from __future__ import annotations

from .cache_policy import CachePolicy
from .lru_cache import LRUCache


class CacheManager:
    """Manages the cache and cache policy."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 86400,
                 streaming_enabled: bool = False):
        self.cache = LRUCache(max_size=max_size, default_ttl=default_ttl)
        self.policy = CachePolicy(
            cache=self.cache,
            default_ttl=default_ttl,
            streaming_enabled=streaming_enabled,
        )

    def get_or_create_response(self, endpoint: str, model: str,
                               messages: list[dict], api_call_func,
                               tools: list[dict] = None,
                               temperature: float = None,
                               max_tokens: int = None) -> dict:
        """Get a cached response or make an API call and cache the result."""
        return self.policy.get_or_create_response(
            endpoint=endpoint,
            model=model,
            messages=messages,
            api_call_func=api_call_func,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def get_stats(self) -> dict:
        """Get cache statistics."""
        return self.cache.get_stats()

    def clear(self) -> None:
        """Clear the cache."""
        self.cache.clear()

    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        return self.cache.cleanup_expired()
```

**What this does:**
- Provides a unified interface for cache management.
- Integrates with `client.py` for API calls.
- Logs cache hit/miss rates via `monitoring.py`.

---

## 5. Testing

### 5.1 Unit Tests

**File:** `tests/test_lru_cache.py`

```python
"""Tests for LRUCache."""
import pytest
import time
from nbchat.cache.lru_cache import LRUCache, CacheEntry


def test_put_and_get():
    """Test putting and getting a cache entry."""
    cache = LRUCache(max_size=10)
    cache.put("key1", "value1")
    
    entry = cache.get("key1")
    assert entry is not None
    assert entry.response == "value1"


def test_get_nonexistent():
    """Test getting a nonexistent key."""
    cache = LRUCache(max_size=10)
    entry = cache.get("nonexistent")
    assert entry is None


def test_lru_eviction():
    """Test LRU eviction when cache is full."""
    cache = LRUCache(max_size=3)
    
    # Fill cache
    cache.put("key1", "value1")
    cache.put("key2", "value2")
    cache.put("key3", "value3")
    
    # Access key1 to make it recently used
    cache.get("key1")
    
    # Add key4, should evict key2 (oldest)
    cache.put("key4", "value4")
    
    assert cache.get("key1") is not None
    assert cache.get("key2") is None  # Evicted
    assert cache.get("key3") is not None
    assert cache.get("key4") is not None


def test_ttl_expiry():
    """Test TTL-based expiration."""
    cache = LRUCache(max_size=10, default_ttl=1)
    cache.put("key1", "value1", ttl_seconds=1)
    
    # Should be cached
    assert cache.get("key1") is not None
    
    # Wait for expiry
    time.sleep(1.1)
    
    # Should be expired
    assert cache.get("key1") is None


def test_clear():
    """Test clearing the cache."""
    cache = LRUCache(max_size=10)
    cache.put("key1", "value1")
    cache.put("key2", "value2")
    
    cache.clear()
    assert cache.get("key1") is None
    assert cache.get("key2") is None


def test_get_stats():
    """Test cache statistics."""
    cache = LRUCache(max_size=10)
    cache.put("key1", "value1")
    cache.get("key1")  # Hit
    cache.get("key2")  # Miss
    
    stats = cache.get_stats()
    assert stats["size"] == 1
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate"] == pytest.approx(0.5)
```

**File:** `tests/test_cache_key.py`

```python
"""Tests for cache key generation."""
import pytest
from nbchat.cache.cache_key import generate_cache_key, generate_cache_key_from_params


def test_generate_cache_key():
    """Test cache key generation."""
    key1 = generate_cache_key(
        endpoint="chat/completions",
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}],
    )
    key2 = generate_cache_key(
        endpoint="chat/completions",
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}],
    )
    
    # Same parameters should produce same key
    assert key1 == key2
    
    # Different parameters should produce different key
    key3 = generate_cache_key(
        endpoint="chat/completions",
        model="gpt-4",
        messages=[{"role": "user", "content": "Goodbye"}],
    )
    assert key1 != key3


def test_generate_cache_key_from_params():
    """Test cache key generation from parameters."""
    params1 = {"model": "gpt-4", "messages": ["Hello"]}
    params2 = {"model": "gpt-4", "messages": ["Hello"]}
    
    key1 = generate_cache_key_from_params(params1)
    key2 = generate_cache_key_from_params(params2)
    
    assert key1 == key2


def test_cache_key_length():
    """Test that cache keys are a reasonable length."""
    key = generate_cache_key(
        endpoint="chat/completions",
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}],
    )
    assert len(key) == 32
```

### 5.2 Integration Test

**File:** `tests/test_cache_integration.py`

```python
"""Integration tests for caching."""
import pytest
from nbchat.cache import CacheManager


class MockAPI:
    """Mock API for testing."""
    def __init__(self):
        self.call_count = 0

    def call(self, model: str, messages: list[dict], **kwargs) -> dict:
        self.call_count += 1
        return {
            "model": model,
            "content": f"Response {self.call_count}",
            "usage": {"total_tokens": 10},
        }


def test_cache_hit():
    """Test that cached responses are returned."""
    manager = CacheManager(max_size=10)
    api = MockAPI()
    
    # First call should be a cache miss
    response1 = manager.get_or_create_response(
        endpoint="chat/completions",
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}],
        api_call_func=api.call,
    )
    assert api.call_count == 1
    assert response1["content"] == "Response 1"
    
    # Second call should be a cache hit
    response2 = manager.get_or_create_response(
        endpoint="chat/completions",
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}],
        api_call_func=api.call,
    )
    assert api.call_count == 1  # No additional API call
    assert response2["content"] == "Response 1"  # Same response


def test_cache_miss_different_params():
    """Test that different parameters result in cache misses."""
    manager = CacheManager(max_size=10)
    api = MockAPI()
    
    # First call
    manager.get_or_create_response(
        endpoint="chat/completions",
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}],
        api_call_func=api.call,
    )
    
    # Second call with different message
    manager.get_or_create_response(
        endpoint="chat/completions",
        model="gpt-4",
        messages=[{"role": "user", "content": "Goodbye"}],
        api_call_func=api.call,
    )
    
    assert api.call_count == 2
```

### 5.3 Run Tests

```bash
cd nbchat
python -m pytest tests/test_lru_cache.py tests/test_cache_key.py tests/test_cache_integration.py -v
```

---

## 6. Usage

### 6.1 Basic Usage

```python
from nbchat.cache import CacheManager
from nbchat.core.client import ChatClient
from nbchat.core.config import Config

# Load config
config = Config("repo_config.yaml")

# Create client
client = ChatClient(config)

# Create cache manager
cache_manager = CacheManager(
    max_size=1000,
    default_ttl=86400,  # 24 hours
)

# Make a cached API call
def api_call(model, messages, **kwargs):
    return client.send_message(messages[0]["content"], system_prompt=None)

response = cache_manager.get_or_create_response(
    endpoint="chat/completions",
    model=config.model,
    messages=[{"role": "user", "content": "Hello"}],
    api_call_func=api_call,
)
print(response["content"])
```

### 6.2 Monitoring Cache Performance

```python
# Get cache statistics
stats = cache_manager.get_stats()
print(f"Cache hit rate: {stats['hit_rate']:.2%}")
print(f"Cache size: {stats['size']}/{stats['max_size']}")
print(f"Hits: {stats['hits']}, Misses: {stats['misses']}")
```

---

## 7. Common Pitfalls

1. **Cache pollution:** Different models or parameters should not share cache entries. Ensure the cache key includes all relevant parameters.

2. **Stale data:** Cached responses may become stale. Implement TTL-based eviction and consider invalidating cache on model/API changes.

3. **Memory usage:** Large responses can consume significant memory. Consider compressing responses or limiting cache size.

4. **Streaming responses:** Streaming responses cannot be cached by default. Enable streaming caching only if appropriate for your use case.

5. **Rate limit bypass:** Caching can bypass rate limits, which may be undesirable for certain endpoints. Use bypass endpoints to exclude rate-limited endpoints from caching.

---

## 8. Success Criteria

- [ ] All unit tests pass.
- [ ] Integration test shows the cache correctly returns cached responses.
- [ ] Cache hit rate improves with repeated queries.
- [ ] Cache statistics are correctly tracked and reported.
- [ ] TTL-based eviction works correctly.

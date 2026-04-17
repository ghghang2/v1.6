# Implementation Guide: Advanced Context Compression with Fact Preservation (Opportunity 5)

> **Prerequisites:** Basic Python knowledge, familiarity with nbchat's codebase, understanding of LLM-based summarization.
> **Estimated time:** 2–3 days (including testing and iteration).
> **Source:** Meta-Harness "Context Compression" approach with fact preservation.

---

## 1. Goal

Enhance nbchat's context compression to preserve key facts, decisions, and tool outputs during summarization, going beyond naive truncation.

---

## 2. Background: How Nbchat Currently Handles Context Compression

Nbchat currently implements **sliding window + LLM-based summarization** in `compressor.py`:

- When the token budget is exceeded, the compressor summarizes older conversation turns.
- However, critical information (tool outputs, decisions, extracted facts) may be lost during summarization.
- Meta-Harness adds **fact preservation** — ensuring that critical information is not lost during compression.

### Key files to understand:
| File | Purpose |
|------|---------|
| `nbchat/core/compressor.py` | Token-bounded context compression (sliding window + summarization) |
| `nbchat/core/config.py` | Application-wide configuration (model, API keys, tools, memory) |
| `nbchat/core/db.py` | SQLite persistence: chat history, memory, episodes, tool outputs |

---

## 3. Architecture Overview

```
nbchat/core/
├── compressor.py      # Enhanced with two-phase compression
├── fact_extractor.py  # Fact extraction logic (new)
└── ...
```

### Component Relationships

```
Conversation History
    │
    ▼
┌─────────────┐
│ Fact        │── Phase 1: Extract key facts
│ Extractor   │   - Tool call results
└──────┬──────┘   - Decisions made
       │           - Extracted facts
       ▼
┌─────────────┐
│ Summarizer  │── Phase 2: Summarize old turns
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Compressed  │── Facts + Summary
│ Context     │
└─────────────┘
```

---

## 4. Step-by-Step Implementation

### Step 1: Create the Fact Extractor Module

**File:** `nbchat/core/fact_extractor.py` (new file)

This module extracts key facts from conversation turns before compression.

```python
"""Fact extraction from conversation turns for context compression."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Prompt for fact extraction
FACT_EXTRACTION_PROMPT = """You are a fact extraction expert. Given a conversation, extract key facts that should be preserved during context compression.

Conversation:
{conversation}

Extract the following types of facts:
1. Tool calls: Full output for small results (< 500 chars), summaries for large ones.
2. Decisions: Key decisions made by the agent.
3. Facts: Important facts extracted from user input or tool outputs.

Return a JSON object with the following structure:
{{
  "tool_calls": [
    {{"tool": "tool_name", "input": "...", "output_summary": "..."}}
  ],
  "decisions": [
    {{"description": "What was decided", "reasoning": "Why"}}
  ],
  "facts": [
    {{"description": "Important fact"}}
  ]
}}

Return only the JSON object, no other text."""


@dataclass
class ExtractedFact:
    """Represents an extracted fact."""
    category: str  # "tool_call", "decision", "fact"
    description: str
    details: dict = field(default_factory=dict)
    source: str = ""  # Which turn this came from


class FactExtractor:
    """Extracts key facts from conversation turns."""

    def __init__(self, client, max_fact_length: int = 500):
        self.client = client
        self.max_fact_length = max_fact_length

    def extract_facts(self, conversation: list[dict]) -> list[ExtractedFact]:
        """Extract key facts from a conversation.
        
        Args:
            conversation: List of message dictionaries with 'role' and 'content'.
        
        Returns:
            List of ExtractedFact objects.
        """
        if not conversation:
            return []
        
        # Build conversation text
        conversation_text = self._build_conversation_text(conversation)
        
        # Call LLM to extract facts
        prompt = FACT_EXTRACTION_PROMPT.format(conversation=conversation_text)
        response = self.client.send_message(prompt)
        
        # Parse JSON response
        try:
            facts_data = json.loads(response)
        except json.JSONDecodeError:
            logger.error("Failed to parse fact extraction response: %s", response)
            return []
        
        # Convert to ExtractedFact objects
        facts = []
        
        # Extract tool call facts
        for tool_call in facts_data.get("tool_calls", []):
            fact = ExtractedFact(
                category="tool_call",
                description=f"Tool call: {tool_call.get('tool', 'unknown')}",
                details=tool_call,
            )
            facts.append(fact)
        
        # Extract decision facts
        for decision in facts_data.get("decisions", []):
            fact = ExtractedFact(
                category="decision",
                description=decision.get("description", ""),
                details={"reasoning": decision.get("reasoning", "")},
            )
            facts.append(fact)
        
        # Extract fact facts
        for fact_entry in facts_data.get("facts", []):
            fact = ExtractedFact(
                category="fact",
                description=fact_entry.get("description", ""),
            )
            facts.append(fact)
        
        logger.info("Extracted %d facts from conversation", len(facts))
        return facts

    def _build_conversation_text(self, conversation: list[dict]) -> str:
        """Build a text representation of the conversation."""
        lines = []
        for msg in conversation:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def format_facts_for_context(self, facts: list[ExtractedFact]) -> str:
        """Format extracted facts for inclusion in the compressed context.
        
        Args:
            facts: List of ExtractedFact objects.
        
        Returns:
            Formatted string of facts.
        """
        if not facts:
            return ""
        
        lines = ["=== PRESERVED FACTS ==="]
        
        # Group by category
        tool_calls = [f for f in facts if f.category == "tool_call"]
        decisions = [f for f in facts if f.category == "decision"]
        facts_only = [f for f in facts if f.category == "fact"]
        
        if tool_calls:
            lines.append("\nTool Calls:")
            for fact in tool_calls:
                tool_name = fact.details.get("tool", "unknown")
                output = fact.details.get("output_summary", fact.details.get("output", ""))
                # Truncate if too long
                if len(output) > self.max_fact_length:
                    output = output[:self.max_fact_length] + "..."
                lines.append(f"  - {tool_name}: {output}")
        
        if decisions:
            lines.append("\nDecisions:")
            for fact in decisions:
                lines.append(f"  - {fact.description}")
                if fact.details.get("reasoning"):
                    lines.append(f"    Reasoning: {fact.details['reasoning']}")
        
        if facts_only:
            lines.append("\nFacts:")
            for fact in facts_only:
                lines.append(f"  - {fact.description}")
        
        lines.append("=== END PRESERVED FACTS ===")
        return "\n".join(lines)
```

**What this does:**
- Extracts key facts from conversation turns before compression.
- Identifies tool call results, decisions, and important facts.
- Formats facts for inclusion in the compressed context.

### Step 2: Update the Compressor Module

**File:** `nbchat/core/compressor.py`

This module is enhanced with two-phase compression (fact extraction + summarization).

```python
"""Enhanced context compression with fact preservation."""
from __future__ import annotations

import logging
from typing import Optional

from .fact_extractor import FactExtractor

logger = logging.getLogger(__name__)


class ContextCompressor:
    """Enhanced context compressor with fact preservation."""

    def __init__(self, client, max_tokens: int = 128000,
                 compression_threshold: float = 0.8,
                 fact_extractor: FactExtractor = None):
        self.client = client
        self.max_tokens = max_tokens
        self.compression_threshold = compression_threshold
        self.fact_extractor = fact_extractor or FactExtractor(client)
        self._current_context: list[dict] = []
        self._token_count = 0

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the context."""
        self._current_context.append({
            "role": role,
            "content": content,
        })
        # Rough token estimate (4 chars per token)
        self._token_count += len(content) // 4

    def get_context(self) -> list[dict]:
        """Get the current context."""
        return self._current_context

    def should_compress(self) -> bool:
        """Check if compression is needed."""
        return self._token_count > self.max_tokens * self.compression_threshold

    def compress(self) -> list[dict]:
        """Compress the context with fact preservation.
        
        Returns:
            Compressed context as a list of messages.
        """
        if not self.should_compress():
            return self._current_context
        
        logger.info("Compressing context (%d tokens, max %d)",
                     self._token_count, self.max_tokens)
        
        # Phase 1: Extract facts from the oldest half of the conversation
        half_point = len(self._current_context) // 2
        old_turns = self._current_context[:half_point]
        new_turns = self._current_context[half_point:]
        
        facts = self.fact_extractor.extract_facts(old_turns)
        facts_text = self.fact_extractor.format_facts_for_context(facts)
        
        # Phase 2: Summarize old turns
        summary = self._summarize_old_turns(old_turns)
        
        # Build compressed context
        compressed_context = [
            {"role": "system", "content": facts_text},
            {"role": "system", "content": f"Summary of older conversation:\n{summary}"},
        ] + new_turns
        
        # Update token count (rough estimate)
        self._token_count = sum(len(msg["content"]) // 4 for msg in compressed_context)
        self._current_context = compressed_context
        
        logger.info("Context compressed to %d tokens", self._token_count)
        return compressed_context

    def _summarize_old_turns(self, old_turns: list[dict]) -> str:
        """Summarize old conversation turns."""
        # Build conversation text
        conversation_text = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in old_turns
        ])
        
        # Build summarization prompt
        prompt = f"""Summarize the following conversation, preserving key information:

{conversation_text}

Provide a concise summary that captures:
- What the user asked for
- What the agent did
- Any important results or outputs

Keep the summary under 500 characters."""
        
        # Call LLM to summarize
        response = self.client.send_message(prompt)
        
        return response

    def reset(self) -> None:
        """Reset the context."""
        self._current_context = []
        self._token_count = 0
        logger.info("Context reset")
```

**What this does:**
- Extends `compressor.py` with fact extraction logic.
- Implements two-phase compression: fact extraction + summarization.
- Preserves critical information during compression.

### Step 3: Add Configuration Support

**File:** `nbchat/core/config.py`

This module is enhanced with compression configuration.

```python
"""Configuration for context compression."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CompressionConfig:
    """Configuration for context compression."""
    max_tokens: int = 128000
    compression_threshold: float = 0.8
    fact_preservation_enabled: bool = True
    max_fact_length: int = 500
    summarization_model: str = "gpt-4"

    @classmethod
    def from_dict(cls, data: dict) -> CompressionConfig:
        """Create from dictionary (e.g., from YAML config)."""
        return cls(
            max_tokens=data.get("max_tokens", 128000),
            compression_threshold=data.get("compression_threshold", 0.8),
            fact_preservation_enabled=data.get("fact_preservation_enabled", True),
            max_fact_length=data.get("max_fact_length", 500),
            summarization_model=data.get("summarization_model", "gpt-4"),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "max_tokens": self.max_tokens,
            "compression_threshold": self.compression_threshold,
            "fact_preservation_enabled": self.fact_preservation_enabled,
            "max_fact_length": self.max_fact_length,
            "summarization_model": self.summarization_model,
        }
```

**What this does:**
- Allows fact preservation rules to be configured.
- Provides configuration for compression settings.

---

## 5. Testing

### 5.1 Unit Tests

**File:** `tests/test_fact_extractor.py`

```python
"""Tests for FactExtractor."""
import pytest
from nbchat.core.fact_extractor import FactExtractor, ExtractedFact


class MockClient:
    """Mock LLM client for testing."""
    def __init__(self, response: str):
        self.response = response

    def send_message(self, prompt: str, system_prompt: str = None) -> str:
        return self.response


def test_extract_facts():
    """Test fact extraction."""
    client = MockClient('''
    {
      "tool_calls": [
        {"tool": "file_reader", "input": "read file.txt", "output_summary": "File contains: Hello World"}
      ],
      "decisions": [
        {"description": "Use file_reader to read file.txt", "reasoning": "Need to see file contents"}
      ],
      "facts": [
        {"description": "The file contains 'Hello World'"}
      ]
    }
    ''')
    
    extractor = FactExtractor(client)
    conversation = [
        {"role": "user", "content": "Read file.txt"},
        {"role": "assistant", "content": "I'll use file_reader to read file.txt"},
    ]
    
    facts = extractor.extract_facts(conversation)
    
    assert len(facts) == 3
    assert facts[0].category == "tool_call"
    assert facts[1].category == "decision"
    assert facts[2].category == "fact"


def test_format_facts():
    """Test formatting facts for context."""
    client = MockClient("[]")
    extractor = FactExtractor(client)
    
    facts = [
        ExtractedFact(
            category="tool_call",
            description="Tool call: file_reader",
            details={"tool": "file_reader", "output_summary": "Hello World"},
        ),
        ExtractedFact(
            category="decision",
            description="Read file.txt",
            details={"reasoning": "Need to see contents"},
        ),
    ]
    
    formatted = extractor.format_facts_for_context(facts)
    
    assert "PRESERVED FACTS" in formatted
    assert "file_reader" in formatted
    assert "Read file.txt" in formatted


def test_extract_facts_empty():
    """Test fact extraction with empty conversation."""
    client = MockClient("[]")
    extractor = FactExtractor(client)
    
    facts = extractor.extract_facts([])
    assert facts == []


def test_extract_facts_invalid_json():
    """Test fact extraction with invalid JSON."""
    client = MockClient("Invalid JSON")
    extractor = FactExtractor(client)
    
    conversation = [{"role": "user", "content": "Hello"}]
    facts = extractor.extract_facts(conversation)
    assert facts == []
```

**File:** `tests/test_compressor.py`

```python
"""Tests for ContextCompressor."""
import pytest
from nbchat.core.compressor import ContextCompressor


class MockClient:
    """Mock LLM client for testing."""
    def __init__(self, response: str = "Summary of conversation..."):
        self.response = response

    def send_message(self, prompt: str, system_prompt: str = None) -> str:
        return self.response


def test_add_message():
    """Test adding a message to the context."""
    client = MockClient()
    compressor = ContextCompressor(client, max_tokens=1000)
    
    compressor.add_message("user", "Hello")
    compressor.add_message("assistant", "Hi there!")
    
    context = compressor.get_context()
    assert len(context) == 2
    assert context[0]["role"] == "user"
    assert context[1]["role"] == "assistant"


def test_should_compress():
    """Test should_compress method."""
    client = MockClient()
    compressor = ContextCompressor(client, max_tokens=100, compression_threshold=0.8)
    
    # Add a short message
    compressor.add_message("user", "Hi")
    assert not compressor.should_compress()
    
    # Add a long message to exceed threshold
    long_content = "x" * 100
    compressor.add_message("user", long_content)
    assert compressor.should_compress()


def test_compress():
    """Test compression."""
    client = MockClient("Summary: User asked about weather.")
    compressor = ContextCompressor(client, max_tokens=100, compression_threshold=0.5)
    
    # Add messages to exceed threshold
    for i in range(10):
        compressor.add_message("user", f"Message {i}")
        compressor.add_message("assistant", f"Response {i}")
    
    compressed = compressor.compress()
    
    # Should have fewer messages than original
    assert len(compressed) < 20
    
    # Should contain system messages with facts and summary
    assert any(msg["role"] == "system" for msg in compressed)


def test_reset():
    """Test resetting the context."""
    client = MockClient()
    compressor = ContextCompressor(client)
    
    compressor.add_message("user", "Hello")
    compressor.reset()
    
    assert compressor.get_context() == []
    assert compressor._token_count == 0
```

### 5.2 Integration Test

**File:** `tests/test_compression_e2e.py`

```python
"""End-to-end test for context compression."""
import pytest
from nbchat.core.compressor import ContextCompressor


class MockClient:
    """Mock LLM client for testing."""
    def __init__(self):
        self.calls = []

    def send_message(self, prompt: str, system_prompt: str = None) -> str:
        self.calls.append(prompt)
        if "fact" in prompt.lower() or "extract" in prompt.lower():
            return '''
            {
              "tool_calls": [],
              "decisions": [{"description": "User asked for summary", "reasoning": "Need to summarize"}],
              "facts": [{"description": "Conversation is about summarization"}]
            }
            '''
        return "Summary: User asked for a summary of the conversation."


@pytest.mark.asyncio
async def test_e2e_compression():
    """Test end-to-end compression with mock LLM."""
    client = MockClient()
    compressor = ContextCompressor(client, max_tokens=100, compression_threshold=0.5)
    
    # Add messages to exceed threshold
    for i in range(10):
        compressor.add_message("user", f"Message {i}")
        compressor.add_message("assistant", f"Response {i}")
    
    # Compress
    compressed = compressor.compress()
    
    # Verify compression happened
    assert len(compressed) < 20
    
    # Verify facts were extracted
    system_messages = [msg for msg in compressed if msg["role"] == "system"]
    assert len(system_messages) >= 1
    assert "PRESERVED FACTS" in system_messages[0]["content"]
```

### 5.3 Run Tests

```bash
cd nbchat
python -m pytest tests/test_fact_extractor.py tests/test_compressor.py tests/test_compression_e2e.py -v
```

---

## 6. Usage

### 6.1 Basic Usage

```python
from nbchat.core.compressor import ContextCompressor
from nbchat.core.client import ChatClient
from nbchat.core.config import Config

# Load config
config = Config("repo_config.yaml")

# Create client
client = ChatClient(config)

# Create compressor
compressor = ContextCompressor(
    client=client,
    max_tokens=128000,
    compression_threshold=0.8,
)

# Add messages
compressor.add_message("user", "Hello, how are you?")
compressor.add_message("assistant", "I'm doing well, thank you!")

# Check if compression is needed
if compressor.should_compress():
    compressed = compressor.compress()
    context = compressor.get_context()
else:
    context = compressor.get_context()

# Use context for next API call
# response = client.send_message(context)
```

### 6.2 Advanced Usage

```python
# Configure compression with custom settings
from nbchat.core.config import CompressionConfig

compression_config = CompressionConfig(
    max_tokens=64000,
    compression_threshold=0.7,
    fact_preservation_enabled=True,
    max_fact_length=1000,
)

compressor = ContextCompressor(
    client=client,
    max_tokens=compression_config.max_tokens,
    compression_threshold=compression_config.compression_threshold,
)
```

---

## 7. Common Pitfalls

1. **Over-summarization:** Aggressive summarization may lose critical information. Start with conservative thresholds and adjust based on performance.

2. **Fact extraction accuracy:** The LLM-based fact extraction may miss or misrepresent critical information. Use human-in-the-loop validation for fact extraction prompts.

3. **Token estimation:** The token estimation (4 chars per token) is rough. Use a more accurate tokenizer (e.g., `tiktoken`) for production.

4. **Summarization quality:** The summarization prompt may produce poor results for certain types of conversations. Iterate on the prompt to improve quality.

5. **Context window pressure:** Even after compression, the context may still exceed the window. Implement additional truncation if needed.

---

## 8. Success Criteria

- [ ] All unit tests pass.
- [ ] Integration test shows the compressor correctly compresses context.
- [ ] Facts are correctly extracted and preserved during compression.
- [ ] Summarization produces coherent results.
- [ ] Compressed context fits within the token budget.

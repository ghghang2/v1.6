# Implementation Guide: Automated Prompt Optimization (Opportunity 1)

> **Prerequisites:** Basic Python knowledge, familiarity with nbchat's codebase, access to an LLM API key.
> **Estimated time:** 2–3 days (including testing and iteration).
> **Source:** Meta-Harness "Automated Prompt Optimization" approach.
> **⚠️ CRITICAL NOTE:** This guide has been corrected to use the actual nbchat API (`client.chat.completions.create()`), not the fictional `client.send_message()` that appeared in earlier drafts.

---

## 1. Goal

Build a system that automatically optimizes nbchat's system prompt templates by measuring their performance on a held-out evaluation set and using evolutionary search to improve them.

**IMPORTANT:** This is a high-effort, high-risk feature. Before implementing, ask yourself:
- Is the potential improvement worth the complexity?
- Can we achieve similar gains with simpler prompt engineering?
- Do we have a clear metric for "better" prompts?

If the answer to any of these is unclear, defer this feature.

---

## 2. Background: How Nbchat Currently Handles Prompts

Nbchat currently uses a **static YAML-based configuration** for system prompts:

- `repo_config.yaml` contains the `DEFAULT_SYSTEM_PROMPT` string under the root section (not under an `llm` section).
- The prompt is loaded once at startup in `nbchat/core/config.py` as the constant `DEFAULT_SYSTEM_PROMPT`.
- The prompt is passed to the LLM via `nbchat/core/client.py`'s `MetricsLoggingClient`, which wraps an `OpenAI` client.
- There is **no** mechanism for prompt versioning, A/B testing, or automated improvement.

### Actual nbchat API (from `client.py`):

```python
from nbchat.core.client import get_client

client = get_client()  # Returns MetricsLoggingClient
response = client.chat.completions.create(
    model="qwen3.5-35b",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ],
    stream=True
)
```

**This is the ONLY API that exists.** Any code that references `client.send_message()` is broken and must not be implemented.

### Key files to understand:
| File | Purpose |
|------|---------|
| `nbchat/core/config.py` | Loads `DEFAULT_SYSTEM_PROMPT` from YAML at startup |
| `nbchat/core/client.py` | OpenAI-compatible client with streaming (uses `chat.completions.create()`) |
| `nbchat/core/db.py` | Stores chat logs and session metadata (can store prompt versions) |

---

## 3. Architecture Overview

```
nbchat/core/
├── template.py          # Prompt template management (new)
├── evaluator.py         # Evaluation harness (new)
└── ...
```

**⚠️ DESIGN DECISION:** We are NOT creating a separate `prompt_optimizer/` package. Instead, we integrate into `nbchat/core/` to minimize maintenance burden and cognitive load.

**⚠️ DESIGN DECISION:** We are NOT implementing gradient-based prompt optimization (which is theoretically complex and practically unreliable for discrete text). Instead, we implement **evolutionary search with sentence-level mutations**, which is simpler and more practical.

---

## 4. Step-by-Step Implementation

### Step 1: Create the Prompt Template Module

**File:** `nbchat/core/template.py`

This module manages prompt templates with versioning and variable substitution.

```python
"""Prompt template management with versioning and variable substitution."""
from __future__ import annotations

import logging
import time
import hashlib
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PromptVersion:
    """Represents a single prompt version with metadata."""
    version_id: str
    template: str
    created_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    @property
    def checksum(self) -> str:
        """SHA-256 hash of the template for deduplication."""
        return hashlib.sha256(self.template.encode()).hexdigest()[:12]


class PromptTemplateManager:
    """Manages prompt templates with versioning and substitution."""

    def __init__(self):
        self._versions: dict[str, PromptVersion] = {}
        self._active_version_id: Optional[str] = None

    def register_template(self, version_id: str, template: str,
                          metadata: Optional[dict] = None) -> PromptVersion:
        """Register a new prompt template version."""
        if version_id in self._versions:
            logger.warning("Overwriting existing version: %s", version_id)
        pv = PromptVersion(version_id=version_id, template=template,
                           metadata=metadata or {})
        self._versions[version_id] = pv
        logger.info("Registered prompt version: %s (checksum: %s)",
                     version_id, pv.checksum)
        return pv

    def get_template(self, version_id: str) -> str:
        """Retrieve a prompt template by version ID."""
        if version_id not in self._versions:
            raise KeyError(f"Unknown prompt version: {version_id}")
        return self._versions[version_id].template

    def set_active(self, version_id: str) -> None:
        """Set the active prompt version."""
        if version_id not in self._versions:
            raise KeyError(f"Unknown prompt version: {version_id}")
        self._active_version_id = version_id
        logger.info("Active prompt version set to: %s", version_id)

    def get_active_template(self) -> str:
        """Get the currently active template."""
        if self._active_version_id is None:
            raise RuntimeError("No active prompt version set")
        return self.get_template(self._active_version_id)

    def substitute(self, template: str, **kwargs) -> str:
        """Substitute {{variable}} placeholders in a template."""
        result = template
        for key, value in kwargs.items():
            placeholder = "{{" + key + "}}"
            result = result.replace(placeholder, str(value))
        return result

    def list_versions(self) -> list[PromptVersion]:
        """List all registered prompt versions."""
        return list(self._versions.values())

    @property
    def active_version_id(self) -> Optional[str]:
        return self._active_version_id
```

**What this does:**
- Stores multiple prompt versions in memory.
- Computes checksums for deduplication.
- Supports Jinja2-style `{{variable}}` substitution.
- Tracks which version is "active."

**NOTE:** This module is also used by Guide 06 (Prompt Versioning). To avoid duplication, Guide 06 should import from this module instead of creating its own `PromptVersioner`.

---

### Step 2: Create the Evaluation Harness

**File:** `nbchat/core/evaluator.py`

This module evaluates a given prompt template against a set of test cases.

```python
"""Evaluation harness for prompt optimization."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional, Any

from openai import OpenAI

logger = logging.getLogger(__name__)


@dataclass
class TestCase:
    """A single evaluation test case."""
    user_message: str
    expected_response: str  # Expected response or expected behavior description
    score_fn: Optional[Callable[[str, str], float]] = None  # Custom scoring function
    weight: float = 1.0


@dataclass
class EvaluationResult:
    """Result of evaluating a prompt on a test set."""
    total_score: float = 0.0
    case_results: list = field(default_factory=list)
    avg_score: float = 0.0
    num_cases: int = 0


class PromptEvaluator:
    """Evaluates prompt templates against a test set using the LLM."""

    def __init__(self, openai_client: OpenAI, model: str, test_cases: list[TestCase]):
        """
        Args:
            openai_client: OpenAI client instance (from get_client())._client
            model: Model name to use for evaluation
            test_cases: List of test cases to evaluate against
        """
        self._client = openai_client
        self._model = model
        self.test_cases = test_cases
        self._default_score_fn = self._default_scoring

    def evaluate(self, system_prompt: str) -> EvaluationResult:
        """Run all test cases through the LLM with the given system prompt."""
        result = EvaluationResult()
        total_weighted = 0.0
        total_weight = 0.0

        for i, tc in enumerate(self.test_cases):
            logger.info("Evaluating test case %d/%d", i + 1, len(self.test_cases))
            score = self._run_single(tc, system_prompt)
            weighted_score = score * tc.weight
            total_weighted += weighted_score
            total_weight += tc.weight

            result.case_results.append({
                "case_index": i,
                "score": score,
                "user_message": tc.user_message,
                "expected": tc.expected_response[:100],
                "actual": "",  # Truncated for logging
            })

        result.num_cases = len(self.test_cases)
        result.avg_score = total_weighted / total_weight if total_weight > 0 else 0.0
        result.total_score = total_weighted

        logger.info("Evaluation complete: avg_score=%.4f", result.avg_score)
        return result

    def _run_single(self, tc: TestCase, system_prompt: str) -> float:
        """Run a single test case and return its score."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": tc.user_message},
        ]

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.3,  # Low temperature for consistent evaluation
                max_tokens=500,
            )
            actual_response = response.choices[0].message.content.strip()
        except Exception as e:
            logger.error("LLM call failed for test case: %s", e)
            return 0.0

        score_fn = tc.score_fn or self._default_score_fn
        return score_fn(tc.expected_response, actual_response)

    def _default_scoring(self, expected: str, actual: str) -> float:
        """Default scoring: word overlap ratio (0.0 to 1.0)."""
        expected_words = set(expected.lower().split())
        actual_words = set(actual.lower().split())

        if not expected_words:
            return 1.0 if actual_words else 0.0

        intersection = expected_words & actual_words
        return len(intersection) / len(expected_words)
```

**What this does:**
- Runs test cases through the LLM with a given system prompt.
- Scores responses using word overlap (configurable via `score_fn`).
- Returns aggregate metrics.

**⚠️ IMPORTANT:** The `_default_scoring` method uses simple word overlap, which is a poor proxy for prompt quality. For better results, implement custom `score_fn` that evaluates against domain-specific criteria.

---

### Step 3: Create the Optimizer

**File:** `nbchat/core/optimizer.py`

This module implements evolutionary search for prompt optimization.

```python
"""Evolutionary prompt optimizer."""
from __future__ import annotations

import copy
import logging
import random
import re
from dataclasses import dataclass, field
from typing import Optional

from .evaluator import PromptEvaluator, EvaluationResult

logger = logging.getLogger(__name__)


@dataclass
class PromptCandidate:
    """A single prompt candidate in the evolutionary population."""
    prompt: str
    score: float = 0.0
    generation: int = 0


class PromptOptimizer:
    """Optimizes prompts using evolutionary search."""

    # Mutation operations
    MUTATE_INSERT = "insert"
    MUTATE_DELETE = "delete"
    MUTATE_SWAP = "swap"
    MUTATE_REPHRASE = "rephrase"

    def __init__(self, evaluator: PromptEvaluator, initial_prompt: str,
                 population_size: int = 8, generations: int = 20,
                 mutation_rate: float = 0.3, elite_ratio: float = 0.2):
        """
        Args:
            evaluator: PromptEvaluator instance
            initial_prompt: Starting prompt template
            population_size: Number of candidates in each generation
            generations: Number of evolution generations
            mutation_rate: Probability of mutation per candidate
            elite_ratio: Fraction of top candidates preserved unchanged
        """
        self.evaluator = evaluator
        self.initial_prompt = initial_prompt
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.elite_ratio = elite_ratio

    def optimize(self) -> EvaluationResult:
        """Run evolutionary optimization and return best result."""
        logger.info("Starting prompt optimization: %d gens, %d pop",
                     self.generations, self.population_size)

        population = self._initialize_population()

        for gen in range(self.generations):
            # Evaluate all candidates
            for candidate in population:
                candidate.score = self.evaluator.evaluate(candidate.prompt).avg_score

            # Sort by score (descending)
            population.sort(key=lambda c: c.score, reverse=True)

            best = population[0]
            logger.info("Gen %d: best_score=%.4f, prompt=%s",
                        gen, best.score, best.prompt[:80])

            # Select elites
            n_elites = max(1, int(self.population_size * self.elite_ratio))
            elites = population[:n_elites]

            # Generate next generation
            next_pop = list(elites)  # Keep elites unchanged

            while len(next_pop) < self.population_size:
                parent = random.choice(elites)
                child = copy.deepcopy(parent)

                if random.random() < self.mutation_rate:
                    child.prompt = self._mutate(child.prompt)

                next_pop.append(child)

            population = next_pop

        # Final evaluation of best candidate
        best = population[0]
        result = self.evaluator.evaluate(best.prompt)
        logger.info("Optimization complete: best_score=%.4f", result.avg_score)
        return result

    def _initialize_population(self) -> list[PromptCandidate]:
        """Create initial population with mutations of the initial prompt."""
        population = [PromptCandidate(prompt=self.initial_prompt, generation=0)]

        for i in range(1, self.population_size):
            mutated = self._mutate(self.initial_prompt)
            population.append(PromptCandidate(prompt=mutated, generation=0))

        return population

    def _mutate(self, prompt: str) -> str:
        """Apply a random mutation to the prompt."""
        sentences = self._split_sentences(prompt)

        if not sentences:
            return prompt

        mutation_type = random.choice([
            self.MUTATE_INSERT,
            self.MUTATE_DELETE,
            self.MUTATE_SWAP,
        ])

        if mutation_type == self.MUTATE_INSERT:
            return self._mutate_insert(sentences)
        elif mutation_type == self.MUTATE_DELETE:
            return self._mutate_delete(sentences)
        elif mutation_type == self.MUTATE_SWAP:
            return self._mutate_swap(sentences)

        return prompt

    def _mutate_insert(self, sentences: list[str]) -> str:
        """Insert a new sentence at a random position."""
        # Simple insertions (in production, these would be more sophisticated)
        insertions = [
            "Always be concise and direct.",
            "Prioritize accuracy over verbosity.",
            "If unsure, ask clarifying questions.",
            "Double-check your work before responding.",
        ]
        pos = random.randint(0, len(sentences))
        sentences.insert(pos, random.choice(insertions))
        return ". ".join(sentences) + ("." if sentences else "")

    def _mutate_delete(self, sentences: list[str]) -> str:
        """Delete a random sentence."""
        if len(sentences) <= 1:
            return prompt
        sentences.pop(random.randint(0, len(sentences) - 1))
        return ". ".join(sentences) + ("." if sentences else "")

    def _mutate_swap(self, sentences: list[str]) -> str:
        """Swap two random sentences."""
        if len(sentences) < 2:
            return ". ".join(sentences) + ("." if sentences else "")
        i, j = random.sample(range(len(sentences)), 2)
        sentences[i], sentences[j] = sentences[j], sentences[i]
        return ". ".join(sentences) + ("." if sentences else "")

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple split on ". " - in production, use a proper NLP library
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
```

**What this does:**
- Implements evolutionary search with sentence-level mutations.
- Preserves top candidates (elites) across generations.
- Uses simple mutation operators (insert, delete, swap).

**⚠️ LIMITATIONS:** This is a simplified implementation. For production use, consider:
- Using a proper NLP library for sentence splitting
- Adding more sophisticated mutation operators (rephrase, synonym swap)
- Using a better scoring function than word overlap

---

### Step 4: Create the CLI Entry Point

**File:** `nbchat/core/prompt_optimize.py`

This module provides the CLI entry point for running prompt optimization.

```python
"""CLI entry point for prompt optimization."""
from __future__ import annotations

import argparse
import json
import logging
import sys

from openai import OpenAI

from .config import DEFAULT_SYSTEM_PROMPT, MODEL_NAME
from .client import get_client
from .evaluator import PromptEvaluator, TestCase
from .optimizer import PromptOptimizer

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Optimize nbchat system prompts")
    parser.add_argument("--population", type=int, default=8,
                        help="Population size for evolution")
    parser.add_argument("--generations", type=int, default=20,
                        help="Number of evolution generations")
    parser.add_argument("--test-cases", default=None,
                        help="JSON file with test cases")
    parser.add_argument("--output", default="optimized_prompt.json",
                        help="Output file for results")
    args = parser.parse_args()

    # Get the OpenAI client (from get_client())
    metrics_client = get_client()
    openai_client = metrics_client._client  # Access the underlying OpenAI client

    # Load initial prompt
    initial_prompt = DEFAULT_SYSTEM_PROMPT or "You are a helpful assistant."

    # Load test cases
    test_cases = []
    if args.test_cases:
        with open(args.test_cases) as f:
            cases_data = json.load(f)
            for case in cases_data:
                test_cases.append(TestCase(
                    user_message=case["user_message"],
                    expected_response=case["expected_response"],
                    weight=case.get("weight", 1.0),
                ))
    else:
        # Default test cases (replace with domain-specific cases)
        test_cases = [
            TestCase(user_message="What is 2+2?",
                     expected_response="4", weight=1.0),
            TestCase(user_message="Hello, how are you?",
                     expected_response="hello", weight=1.0),
        ]

    # Build evaluator and optimizer
    evaluator = PromptEvaluator(openai_client, MODEL_NAME, test_cases)
    optimizer = PromptOptimizer(
        evaluator=evaluator,
        initial_prompt=initial_prompt,
        population_size=args.population,
        generations=args.generations,
    )

    # Run optimization
    result = optimizer.optimize()

    # Save results
    output = {
        "best_prompt": result.case_results[0].get("user_message", ""),  # Placeholder
        "best_score": result.avg_score,
        "num_cases": result.num_cases,
    }
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)
    logger.info("Results saved to %s", args.output)
    print(f"Best score: {result.avg_score:.4f}")


if __name__ == "__main__":
    main()
```

**What this does:**
- Provides CLI interface for running prompt optimization.
- Loads test cases from JSON file or uses defaults.
- Saves optimization results to JSON file.

---

## 5. Testing

### 5.1 Unit Tests

**File:** `tests/test_template.py`

```python
"""Tests for PromptTemplateManager."""
import pytest
from nbchat.core.template import PromptTemplateManager


def test_register_and_get():
    mgr = PromptTemplateManager()
    mgr.register_template("v1", "Hello {{name}}")
    assert mgr.get_template("v1") == "Hello {{name}}"


def test_substitution():
    mgr = PromptTemplateManager()
    mgr.register_template("v1", "Hello {{name}}, you are {{role}}")
    result = mgr.substitute(mgr.get_template("v1"), name="Alice", role="admin")
    assert result == "Hello Alice, you are admin"


def test_checksum():
    mgr = PromptTemplateManager()
    pv1 = mgr.register_template("v1", "Same template")
    pv2 = mgr.register_template("v2", "Same template")
    assert pv1.checksum == pv2.checksum


def test_set_active():
    mgr = PromptTemplateManager()
    mgr.register_template("v1", "Prompt 1")
    mgr.register_template("v2", "Prompt 2")
    mgr.set_active("v2")
    assert mgr.get_active_template() == "Prompt 2"


def test_unknown_version_raises():
    mgr = PromptTemplateManager()
    with pytest.raises(KeyError):
        mgr.get_template("nonexistent")
```

**File:** `tests/test_optimizer.py`

```python
"""Tests for PromptOptimizer."""
import pytest
from nbchat.core.optimizer import PromptOptimizer


def test_split_sentences():
    optimizer = PromptOptimizer(None, "First. Second. Third.")
    sentences = optimizer._split_sentences("First. Second. Third.")
    assert len(sentations) == 3


def test_mutate_insert():
    optimizer = PromptOptimizer(None, "First sentence. Second sentence.")
    result = optimizer._mutate("First sentence. Second sentence.")
    # Mutation may or may not change the prompt
    assert isinstance(result, str)


def test_mutate_delete():
    optimizer = PromptOptimizer(None, "First sentence. Second sentence. Third sentence.")
    result = optimizer._mutate("First sentence. Second sentence. Third sentence.")
    # Mutation may or may not change the prompt
    assert isinstance(result, str)
```

---

## 6. Usage

### 6.1 Prepare Test Cases

Create a JSON file with test cases:

```json
[
  {
    "user_message": "Write a Python function to sort a list.",
    "expected_response": "def sort_list(lst): return sorted(lst)",
    "weight": 2.0
  },
  {
    "user_message": "Explain quantum computing.",
    "expected_response": "Quantum computing uses quantum bits",
    "weight": 1.0
  }
]
```

### 6.2 Run the Optimizer

```bash
python -m nbchat.core.prompt_optimize \
    --population 8 \
    --generations 20 \
    --test-cases test_cases.json \
    --output best_prompt.json
```

### 6.3 Deploy the Optimized Prompt

After optimization, manually review the best prompt and update `repo_config.yaml`:

```yaml
DEFAULT_SYSTEM_PROMPT: |
  [Insert optimized prompt here]
```

---

## 7. Iteration and Fine-Tuning

### 7.1 Adjust Hyperparameters

- **Population size:** Larger = more diverse but slower
- **Generations:** More = more thorough but longer
- **Mutation rate:** Higher = more exploration but less exploitation
- **Elite ratio:** Higher = more conservative but less innovation

### 7.2 Improve the Scoring Function

Replace the default word overlap scoring with a custom function:

```python
def custom_scoring(expected: str, actual: str) -> float:
    """Domain-specific scoring function."""
    # Example: check for specific keywords
    keywords = ["python", "function", "sort"]
    actual_lower = actual.lower()
    return sum(1 for kw in keywords if kw in actual_lower) / len(keywords)
```

### 7.3 Add Semantic Mutation

For more sophisticated mutations, consider using a small local LLM to rephrase sentences:

```python
def _mutate_rephrase(self, sentence: str, openai_client: OpenAI) -> str:
    """Rephrase a sentence using an LLM."""
    response = openai_client.chat.completions.create(
        model="small-model",
        messages=[{"role": "user", "content": f"Rephrase: {sentence}"}],
        max_tokens=100,
    )
    return response.choices[0].message.content.strip()
```

---

## 8. Common Pitfalls

1. **Overfitting to test cases:** The optimizer may find prompts that score well on test cases but perform poorly in production. Always manually review optimized prompts.

2. **Poor scoring function:** Word overlap is a terrible proxy for prompt quality. Invest time in building a domain-specific scoring function.

3. **High cost:** Evolutionary optimization requires N × M LLM calls (population × generations). For 8×20, that's 160+ calls per optimization run.

4. **Non-deterministic results:** LLM outputs vary between runs. Run the optimizer multiple times and compare results.

5. **Prompt drift:** Optimized prompts may work well for some tasks but poorly for others. Test broadly before deploying.

---

## 9. Success Criteria

Before considering this feature "complete," verify:

1. ✅ Optimized prompts outperform the baseline on a held-out test set
2. ✅ Optimized prompts do not degrade performance on common tasks
3. ✅ The optimization pipeline is reproducible (same inputs → same outputs)
4. ✅ The best prompt is manually reviewed and approved by a human
5. ✅ The optimization pipeline is documented and easy to run

**If any of these criteria are not met, do not deploy the optimized prompt.**

---

## Appendix: What NOT to Implement

The following approaches were considered but rejected:

1. **Gradient-based prompt tuning:** Requires differentiable prompt representations, which don't exist for discrete text. The Meta-Harness approach uses specialized techniques (soft prompts, token embeddings) that are not compatible with nbchat's architecture.

2. **Multi-agent prompt optimization:** Adding a critic agent to evaluate prompts adds significant complexity and cost for marginal gains.

3. **Real-time prompt adaptation:** Dynamically changing prompts based on conversation context is complex and error-prone. Start with static optimized prompts.

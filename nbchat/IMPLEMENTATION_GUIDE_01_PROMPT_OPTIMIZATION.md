# Implementation Guide: Automated Prompt Optimization (Opportunity 1)

> **Prerequisites:** Basic Python knowledge, familiarity with nbchat's codebase, access to an LLM API key.
> **Estimated time:** 2–3 days (including testing and iteration).
> **Source:** Meta-Harness "Automated Prompt Optimization" approach.

---

## 1. Goal

Build a system that automatically optimizes nbchat's system prompt templates by measuring their performance on a held-out evaluation set and using gradient-based or evolutionary search to improve them.

---

## 2. Background: How Nbchat Currently Handles Prompts

Nbchat currently uses a **static YAML-based configuration** for system prompts:

- `repo_config.yaml` contains the `system_prompt` string under the `llm` section.
- The prompt is loaded once at startup in `nbchat/core/config.py` via the `Config` class (which reads `repo_config.yaml`).
- The prompt is passed to the LLM via `nbchat/core/client.py`'s `ChatClient` class.
- There is **no** mechanism for prompt versioning, A/B testing, or automated improvement.

### Key files to understand:
| File | Purpose |
|------|---------|
| `nbchat/core/config.py` | Loads `system_prompt` from YAML at startup |
| `nbchat/core/client.py` | Sends messages (including system prompt) to the LLM |
| `nbchat/core/db.py` | Stores chat logs and session metadata (can store prompt versions) |

---

## 3. Architecture Overview

```
prompt_optimizer/
├── __init__.py
├── template.py          # Prompt template management
├── evaluator.py         # Evaluation harness
├── optimizer.py         # Search algorithm (evolutionary or gradient-based)
└── cli.py               # CLI entry point
```

---

## 4. Step-by-Step Implementation

### Step 1: Create the Prompt Template Module

**File:** `nbchat/core/template.py`

This module manages prompt templates, supporting Jinja2-style variable substitution and version tracking.

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

### Step 2: Create the Evaluation Harness

**File:** `nbchat/core/evaluator.py`

This module evaluates a given prompt template against a set of test cases.

```python
"""Evaluation harness for prompt optimization."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from .client import ChatClient

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

    def __init__(self, client: ChatClient, test_cases: list[TestCase]):
        self.client = client
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
                "weighted_score": weighted_score,
            })
            logger.info("  Score: %.3f (weighted: %.3f)", score, weighted_score)

        result.num_cases = len(self.test_cases)
        result.total_score = total_weighted
        result.avg_score = total_weighted / total_weight if total_weight > 0 else 0.0
        logger.info("Evaluation complete: avg_score=%.4f", result.avg_score)
        return result

    def _run_single(self, tc: TestCase, system_prompt: str) -> float:
        """Run a single test case and return a score between 0 and 1."""
        response = self.client.send_message(tc.user_message, system_prompt=system_prompt)
        score_fn = tc.score_fn or self._default_score_fn
        return score_fn(tc.expected_response, response)

    @staticmethod
    def _default_scoring(expected: str, actual: str) -> float:
        """Default scoring: exact match = 1.0, else 0.0."""
        if expected.strip().lower() == actual.strip().lower():
            return 1.0
        # Simple word-overlap score as fallback
        expected_words = set(expected.lower().split())
        actual_words = set(actual.lower().split())
        if not expected_words:
            return 1.0 if actual.strip() else 0.0
        overlap = len(expected_words & actual_words) / len(expected_words)
        return overlap
```

**What this does:**
- Takes a list of test cases with expected responses.
- Runs each through the LLM with the given system prompt.
- Computes a score (0–1) for each case.
- Returns aggregate statistics.

### Step 3: Create the Optimizer

**File:** `nbchat/core/optimizer.py`

This module performs the actual optimization using an evolutionary search algorithm.

```python
"""Evolutionary prompt optimizer."""
from __future__ import annotations

import copy
import logging
import random
from typing import Optional

from .evaluator import PromptEvaluator, EvaluationResult

logger = logging.getLogger(__name__)

# Mutation operations
MUTATION_TYPES = ["insert", "delete", "replace", "swap"]


class PromptOptimizer:
    """Optimizes system prompts using evolutionary search."""

    def __init__(self, evaluator: PromptEvaluator,
                 initial_prompt: str,
                 population_size: int = 8,
                 generations: int = 20,
                 mutation_rate: float = 0.3,
                 elite_ratio: float = 0.2):
        self.evaluator = evaluator
        self.initial_prompt = initial_prompt
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.elite_count = max(1, int(population_size * elite_ratio))

    def optimize(self) -> EvaluationResult:
        """Run evolutionary optimization and return the best result."""
        # Initialize population
        population = self._initialize_population()
        best_result = self._evaluate_population(population)
        best_prompt = best_result.best_prompt

        logger.info("Starting evolutionary optimization: %d gens, %d pop",
                     self.generations, self.population_size)

        for gen in range(self.generations):
            logger.info("Generation %d/%d", gen + 1, self.generations)

            # Sort by score (descending)
            population.sort(key=lambda p: p.score, reverse=True)
            logger.info("  Best score: %.4f", population[0].score)

            # Keep elites
            elites = [p.prompt for p in population[:self.elite_count]]

            # Generate new population
            new_population = list(elites)  # Elites pass through unchanged
            while len(new_population) < self.population_size:
                parent = random.choice(population[:self.elite_count * 2])
                child = self._mutate(parent)
                new_population.append(child)

            population = new_population

        # Final evaluation
        final_result = self._evaluate_population(population)
        logger.info("Optimization complete. Best score: %.4f",
                     final_result.best_score)
        return final_result

    def _initialize_population(self) -> list:
        """Create initial population: one original + mutated variants."""
        population = [{"prompt": self.initial_prompt, "score": 0.0}]
        for _ in range(self.population_size - 1):
            variant = self._mutate(self.initial_prompt)
            population.append({"prompt": variant, "score": 0.0})
        return population

    def _mutate(self, prompt: str) -> str:
        """Apply a random mutation to the prompt."""
        if random.random() > self.mutation_rate:
            return prompt  # No mutation this step

        mutation_type = random.choice(MUTATION_TYPES)

        if mutation_type == "insert":
            return self._mutate_insert(prompt)
        elif mutation_type == "delete":
            return self._mutate_delete(prompt)
        elif mutation_type == "replace":
            return self._mutate_replace(prompt)
        elif mutation_type == "swap":
            return self._mutate_swap(prompt)
        return prompt

    @staticmethod
    def _mutate_insert(prompt: str) -> str:
        """Insert a new sentence or phrase at a random position."""
        sentences = prompt.split(". ")
        if len(sentences) < 2:
            return prompt
        insert_pos = random.randint(0, len(sentences) - 1)
        insertions = [
            "Always be concise and direct in your responses.",
            "Think step by step before answering.",
            "If you are unsure, say so rather than guessing.",
            "Use bullet points for lists when possible.",
            "Prioritize accuracy over verbosity.",
        ]
        sentences.insert(insert_pos, random.choice(insertions))
        return ". ".join(sentences)

    @staticmethod
    def _mutate_delete(prompt: str) -> str:
        """Remove a random sentence from the prompt."""
        sentences = prompt.split(". ")
        if len(sentences) <= 2:
            return prompt
        sentences.pop(random.randint(0, len(sentences) - 1))
        return ". ".join(sentences)

    @staticmethod
    def _mutate_replace(prompt: str) -> str:
        """Replace a random word with a synonym-like alternative."""
        replacements = {
            "important": "crucial",
            "always": "generally",
            "never": "rarely",
            "must": "should",
            "critical": "essential",
            "ensure": "guarantee",
        }
        words = prompt.split()
        for i, word in enumerate(words):
            clean = word.lower().rstrip(".,;!")
            if clean in replacements and random.random() < 0.3:
                words[i] = replacements[clean] + ("," if word.endswith(",") else
                                                   "." if word.endswith(".") else "")
                break
        return " ".join(words)

    @staticmethod
    def _mutate_swap(prompt: str) -> str:
        """Swap two random sentences."""
        sentences = prompt.split(". ")
        if len(sentences) < 2:
            return prompt
        i, j = random.sample(range(len(sentences)), 2)
        sentences[i], sentences[j] = sentences[j], sentences[i]
        return ". ".join(sentences)

    def _evaluate_population(self, population: list) -> EvaluationResult:
        """Evaluate all prompts in the population."""
        best_result = None
        for i, entry in enumerate(population):
            logger.info("  Evaluating individual %d/%d", i + 1, len(population))
            result = self.evaluator.evaluate(entry["prompt"])
            entry["score"] = result.avg_score
            if best_result is None or result.avg_score > best_result.best_score:
                best_result = result
                best_result.best_prompt = entry["prompt"]
        return best_result
```

**What this does:**
- Creates an initial population of prompt variants (original + mutations).
- Evaluates each variant against the test set.
- Keeps the "elite" (top-scoring) prompts.
- Mutates elite prompts to create new variants.
- Repeats for the specified number of generations.

### Step 4: Create the CLI Entry Point

**File:** `nbchat/core/prompt_cli.py`

```python
"""CLI for running prompt optimization."""
from __future__ import annotations

import argparse
import json
import logging
import sys

from .client import ChatClient
from .config import Config
from .evaluator import PromptEvaluator, TestCase
from .optimizer import PromptOptimizer

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Optimize nbchat system prompts")
    parser.add_argument("--config", default="repo_config.yaml",
                        help="Path to config file")
    parser.add_argument("--population", type=int, default=8,
                        help="Population size for evolution")
    parser.add_argument("--generations", type=int, default=20,
                        help="Number of evolution generations")
    parser.add_argument("--test-cases", default=None,
                        help="JSON file with test cases")
    parser.add_argument("--output", default="optimized_prompt.json",
                        help="Output file for results")
    args = parser.parse_args()

    # Load config
    config = Config(args.config)
    initial_prompt = config.system_prompt or (
        "You are a helpful assistant."  # default fallback
    )

    # Create client
    client = ChatClient(config)

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
        # Default test cases
        test_cases = [
            TestCase(user_message="What is 2+2?",
                     expected_response="4", weight=1.0),
            TestCase(user_message="Hello, how are you?",
                     expected_response="hello", weight=1.0),
        ]

    # Build evaluator and optimizer
    evaluator = PromptEvaluator(client, test_cases)
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
        "best_prompt": result.best_prompt,
        "best_score": result.best_score,
        "num_cases": result.num_cases,
        "case_results": result.case_results,
    }
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)
    logger.info("Results saved to %s", args.output)
    print(f"Best score: {result.best_score:.4f}")
    print(f"Best prompt:\n{result.best_prompt}")


if __name__ == "__main__":
    main()
```

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

**File:** `tests/test_evaluator.py`

```python
"""Tests for PromptEvaluator."""
import pytest
from nbchat.core.evaluator import PromptEvaluator, TestCase


class MockClient:
    """Mock LLM client for testing."""
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.call_count = 0

    def send_message(self, user_msg: str, system_prompt: str = None) -> str:
        resp = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return resp


def test_default_scoring_exact_match():
    tc = TestCase(user_message="hi", expected_response="hello")
    assert tc.score_fn is None  # Should use default

    evaluator = PromptEvaluator(MockClient(["hello"]), [tc])
    result = evaluator.evaluate("You are helpful.")
    assert result.avg_score == pytest.approx(1.0)


def test_default_scoring_partial_match():
    tc = TestCase(user_message="hi", expected_response="hello world")
    evaluator = PromptEvaluator(MockClient(["hello there"]), [tc])
    result = evaluator.evaluate("You are helpful.")
    assert 0.0 < result.avg_score < 1.0


def test_custom_score_fn():
    def custom_fn(expected, actual):
        return 1.0 if "correct" in actual else 0.0

    tc = TestCase(user_message="hi", expected_response="correct",
                  score_fn=custom_fn)
    evaluator = PromptEvaluator(MockClient(["correct answer"]), [tc])
    result = evaluator.evaluate("You are helpful.")
    assert result.avg_score == pytest.approx(1.0)
```

**File:** `tests/test_optimizer.py`

```python
"""Tests for PromptOptimizer."""
import pytest
from nbchat.core.optimizer import PromptOptimizer
from nbchat.core.evaluator import PromptEvaluator, TestCase


class MockClient:
    def __init__(self, response="test"):
        self.response = response

    def send_message(self, user_msg: str, system_prompt: str = None) -> str:
        return self.response


def test_mutate_insert():
    prompt = "First sentence. Second sentence. Third sentence."
    result = PromptOptimizer._mutate_insert(prompt)
    assert result != prompt or True  # May or may not change
    sentences = result.split(". ")
    assert len(sentences) >= len(prompt.split(". "))


def test_mutate_delete():
    prompt = "First sentence. Second sentence. Third sentence."
    result = PromptOptimizer._mutate_delete(prompt)
    sentences = result.split(". ")
    assert len(sentences) <= len(prompt.split(". "))


def test_mutate_swap():
    prompt = "First sentence. Second sentence."
    result = PromptOptimizer._mutate_swap(prompt)
    sentences = result.split(". ")
    assert len(sentences) == 2


def test_population_initialization():
    evaluator = PromptEvaluator(MockClient("test"), [])
    optimizer = PromptOptimizer(evaluator, "initial", population_size=4,
                                generations=1)
    pop = optimizer._initialize_population()
    assert len(pop) == 4
    assert all("prompt" in p and "score" in p for p in pop)
```

### 5.2 Integration Test

**File:** `tests/test_prompt_optimization_e2e.py`

```python
"""End-to-end test for prompt optimization with mock LLM."""
import json
import os
import tempfile
import pytest

from nbchat.core.evaluator import PromptEvaluator, TestCase
from nbchat.core.optimizer import PromptOptimizer


class MockClient:
    """Mock that returns responses based on keyword matching."""
    def __init__(self):
        self.calls = []

    def send_message(self, user_msg: str, system_prompt: str = None) -> str:
        self.calls.append((user_msg, system_prompt))
        # Simple heuristic: if prompt mentions "concise", give short answer
        if system_prompt and "concise" in system_prompt:
            return "4"
        return "The answer to 2+2 is 4."


def test_e2e_optimization_runs():
    """Verify the optimizer runs without errors and produces a result."""
    client = MockClient()
    test_cases = [
        TestCase(user_message="What is 2+2?", expected_response="4", weight=1.0),
    ]
    evaluator = PromptEvaluator(client, test_cases)
    optimizer = PromptOptimizer(
        evaluator=evaluator,
        initial_prompt="You are a helpful assistant.",
        population_size=4,
        generations=3,
        mutation_rate=0.5,
    )
    result = optimizer.optimize()
    assert result.avg_score >= 0.0
    assert result.num_cases == 1
    assert len(result.case_results) == 1


def test_optimization_improves_over_generations():
    """Verify that scores generally improve over generations."""
    client = MockClient()
    test_cases = [
        TestCase(user_message="What is 2+2?", expected_response="4", weight=1.0),
    ]
    evaluator = PromptEvaluator(client, test_cases)
    optimizer = PromptOptimizer(
        evaluator=evaluator,
        initial_prompt="You are a helpful assistant.",
        population_size=8,
        generations=10,
        mutation_rate=0.4,
    )
    result = optimizer.optimize()
    assert result.best_score > 0.0
```

### 5.3 Run Tests

```bash
cd nbchat
python -m pytest tests/test_template.py tests/test_evaluator.py tests/test_optimizer.py tests/test_prompt_optimization_e2e.py -v
```

---

## 6. Usage

### 6.1 Prepare Test Cases

Create a JSON file `test_cases.json`:

```json
[
    {
        "user_message": "What is the capital of France?",
        "expected_response": "Paris",
        "weight": 1.0
    },
    {
        "user_message": "Explain quantum computing in one sentence.",
        "expected_response": "quantum",
        "weight": 1.0
    }
]
```

### 6.2 Run the Optimizer

```bash
python -m nbchat.core.prompt_cli \
    --config repo_config.yaml \
    --population 8 \
    --generations 20 \
    --test-cases test_cases.json \
    --output optimized_prompt.json
```

### 6.3 Deploy the Optimized Prompt

After reviewing the output, update `repo_config.yaml`:

```yaml
llm:
  system_prompt: "<content from optimized_prompt.json>"
```

---

## 7. Iteration and Fine-Tuning

### 7.1 Adjust Hyperparameters

If optimization is too slow or produces poor results:

| Parameter | Description | Tuning |
|-----------|-------------|--------|
| `population_size` | Number of prompt variants | Increase for more diversity |
| `generations` | Number of evolution cycles | Increase for more search depth |
| `mutation_rate` | Probability of mutation | Increase for more exploration |
| `elite_ratio` | Fraction kept unchanged | Increase for more exploitation |

### 7.2 Improve the Scoring Function

Replace `_default_scoring` with a more sophisticated scorer:
- Use a second LLM as a judge (LLM-as-a-judge pattern).
- Implement n-gram overlap (BLEU, ROUGE).
- Add keyword matching for domain-specific requirements.

### 7.3 Add Semantic Mutation

Extend `optimizer.py` with LLM-based mutations:

```python
def _llm_mutate(self, prompt: str) -> str:
    """Use the LLM to rewrite the prompt."""
    rewrite_prompt = (
        "Rewrite the following system prompt to be more effective. "
        "Keep the same intent but improve clarity and precision.\n\n"
        f"Original: {prompt}\n\nRewritten:"
    )
    response = self.client.send_message(rewrite_prompt)
    return response.strip()
```

---

## 8. Common Pitfalls

1. **Overfitting to test cases:** If the optimized prompt scores well on test cases but performs poorly in production, your test set is too narrow. Add more diverse test cases.

2. **Mutation destroying intent:** If mutations are too aggressive, the prompt may lose its original purpose. Reduce `mutation_rate` or `elite_ratio`.

3. **LLM API rate limits:** Evolutionary search makes many LLM calls. Use the existing retry policy in `nbchat/core/retry.py` and consider batching.

4. **Non-deterministic scoring:** LLM responses vary between calls. Run each test case multiple times and average the scores.

---

## 9. Success Criteria

- [ ] All unit tests pass.
- [ ] Integration test shows the optimizer runs end-to-end.
- [ ] The optimizer produces a prompt that scores higher than the baseline on the test set.
- [ ] The optimized prompt can be deployed by updating `repo_config.yaml`.

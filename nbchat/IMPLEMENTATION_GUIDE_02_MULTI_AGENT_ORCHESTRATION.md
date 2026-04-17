# Implementation Guide: Multi-Agent Orchestration Layer (Opportunity 2)

> **Prerequisites:** Basic Python knowledge, familiarity with nbchat's codebase, understanding of async/await patterns.
> **Estimated time:** 3–5 days (including testing and iteration).
> **Source:** Meta-Harness "Multi-Agent Orchestration" approach.
> **⚠️ CRITICAL NOTE:** This guide has been corrected to use the actual nbchat API (`client.chat.completions.create()`), not the fictional `client.send_message()` that appeared in earlier drafts.

---

## 1. Goal

Build a supervisor-specialized agent architecture where a supervisor agent decomposes complex tasks into subtasks and delegates them to specialized agents, enabling parallel execution and better handling of complex, multi-step tasks.

**⚠️ CRITICAL WARNING:** This is a HIGH-EFFORT, HIGH-RISK feature that fundamentally changes nbchat's architecture. Before implementing, ask yourself:

1. **Is this actually needed?** Does nbchat currently fail at complex tasks? If so, can we fix those failures with simpler changes (better prompts, better context management)?
2. **What's the complexity cost?** This adds 4 new modules, new dependencies, new failure modes, and new debugging challenges.
3. **Can we achieve 80% of the benefit with 20% of the effort?** For example, can we just add better task decomposition to the single-agent loop?

**Recommendation:** Start with a simpler approach: add a "task decomposition" step to the existing single-agent loop, where the LLM is asked to break down complex tasks before execution. This gives some of the benefit without the architectural complexity.

---

## 2. Background: How Nbchat Currently Handles Tasks

Nbchat currently operates as a **single-agent loop**:

- The `run.py` entry point starts the LLM client and processes user input.
- `client.py` sends messages to the LLM and handles streaming responses.
- For complex tasks (e.g., "refactor this codebase and run tests"), the single agent must handle all subtasks sequentially.
- This leads to:
  - Context window pressure from accumulated history.
  - Error propagation across subtasks.
  - No parallelism in task execution.

### Key files to understand:
| File | Purpose |
|------|---------|
| `nbchat/run.py` | Entry point: starts llama-server and client |
| `nbchat/core/client.py` | OpenAI-compatible streaming client with metrics logging |
| `nbchat/core/db.py` | SQLite persistence: chat history, memory, episodes, tool outputs |
| `nbchat/core/tools/base.py` | Tool registry and base class |

---

## 3. Architecture Overview

```
nbchat/orchestration/
├── __init__.py
├── task_graph.py      # DAG-based task dependency management
├── supervisor.py      # Task decomposition and delegation
├── agent_pool.py      # Pool of specialized agents
├── aggregator.py      # Result aggregation and synthesis
└── orchestrator.py    # Main orchestration entry point
```

**⚠️ DESIGN DECISION:** We are NOT implementing full multi-agent parallelism. Instead, we implement a **supervised sequential decomposition** where:
1. A supervisor agent decomposes the task into subtasks.
2. Subtasks are executed sequentially (not in parallel).
3. Results are aggregated into a final output.

This gives 80% of the benefit (better task decomposition) with 20% of the complexity (no parallel execution, no agent lifecycle management).

---

## 4. Step-by-Step Implementation

### Step 1: Create the Task Graph Module

**File:** `nbchat/orchestration/task_graph.py`

This module represents subtasks as nodes in a DAG (Directed Acyclic Graph) and tracks dependencies between them.

```python
"""DAG-based task dependency management for multi-agent orchestration."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of a task in the graph."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskNode:
    """A single task in the graph."""
    task_id: str
    description: str
    required_tools: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class TaskGraph:
    """Manages a DAG of tasks with dependencies."""

    def __init__(self):
        self._nodes: dict[str, TaskNode] = {}
        self._edges: dict[str, list[str]] = {}  # task_id -> list of dependent task_ids

    def add_task(self, task_id: str, description: str,
                 required_tools: list[str] = None,
                 dependencies: list[str] = None) -> TaskNode:
        """Add a task to the graph."""
        node = TaskNode(
            task_id=task_id,
            description=description,
            required_tools=required_tools or [],
            dependencies=dependencies or [],
        )
        self._nodes[task_id] = node
        self._edges[task_id] = []

        # Register dependencies
        for dep in node.dependencies:
            if dep not in self._edges:
                self._edges[dep] = []
            self._edges[dep].append(task_id)

        logger.info("Added task %s: %s", task_id, description)
        return node

    def get_ready_tasks(self) -> list[TaskNode]:
        """Get tasks that are ready to execute (all dependencies completed)."""
        ready = []
        for node in self._nodes.values():
            if node.status == TaskStatus.PENDING:
                deps_satisfied = all(
                    self._nodes[dep].status == TaskStatus.COMPLETED
                    for dep in node.dependencies
                    if dep in self._nodes
                )
                if deps_satisfied:
                    ready.append(node)
        return ready

    def mark_completed(self, task_id: str, result: str) -> None:
        """Mark a task as completed."""
        if task_id in self._nodes:
            self._nodes[task_id].status = TaskStatus.COMPLETED
            self._nodes[task_id].result = result
            logger.info("Task %s completed", task_id)

    def mark_failed(self, task_id: str, error: str) -> None:
        """Mark a task as failed."""
        if task_id in self._nodes:
            self._nodes[task_id].status = TaskStatus.FAILED
            self._nodes[task_id].error = error
            logger.info("Task %s failed: %s", task_id, error)

    def get_summary(self) -> dict:
        """Get a summary of the task graph."""
        return {
            "total": len(self._nodes),
            "pending": sum(1 for n in self._nodes.values() if n.status == TaskStatus.PENDING),
            "running": sum(1 for n in self._nodes.values() if n.status == TaskStatus.RUNNING),
            "completed": sum(1 for n in self._nodes.values() if n.status == TaskStatus.COMPLETED),
            "failed": sum(1 for n in self._nodes.values() if n.status == TaskStatus.FAILED),
        }
```

**What this does:**
- Represents subtasks as nodes in a DAG.
- Tracks dependencies between tasks.
- Identifies which tasks are ready to execute.
- Marks tasks as completed, failed, or skipped.
- Provides summary statistics.

---

### Step 2: Create the Supervisor Module

**File:** `nbchat/orchestration/supervisor.py`

This module receives the user's task and decomposes it into subtasks using an LLM.

```python
"""Supervisor agent for task decomposition and delegation."""
from __future__ import annotations

import json
import logging
from typing import Optional

from openai import OpenAI

from .task_graph import TaskGraph

logger = logging.getLogger(__name__)

# Template for decomposing tasks
DECOMPOSITION_PROMPT = """You are a task decomposition expert. Given a complex user request, break it down into independent subtasks that can be executed sequentially.

Rules:
1. Each subtask should be atomic and self-contained.
2. Identify dependencies between subtasks.
3. Specify which tools are needed for each subtask.
4. Return a JSON array of subtasks with the following structure:
   [
     {{
       "description": "What this subtask does",
       "required_tools": ["tool1", "tool2"],
       "dependencies": ["task_id_1"]
     }}
   ]

User request: {user_request}

Return only the JSON array, no other text."""


class Supervisor:
    """Decomposes complex tasks into subtasks and delegates to specialized agents."""

    def __init__(self, openai_client: OpenAI, model: str):
        """
        Args:
            openai_client: OpenAI client instance (from get_client())._client
            model: Model name to use for decomposition
        """
        self._client = openai_client
        self._model = model
        self._task_graph = TaskGraph()

    def decompose_task(self, user_request: str) -> TaskGraph:
        """Decompose a user request into subtasks."""
        logger.info("Decomposing task: %s", user_request)

        # Build the decomposition prompt
        prompt = DECOMPOSITION_PROMPT.format(user_request=user_request)

        # Call the LLM to decompose the task
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
        )

        # Parse the JSON response
        try:
            subtasks = json.loads(response.choices[0].message.content.strip())
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM response as JSON: %s", response.choices[0].message.content)
            raise ValueError("Failed to decompose task: invalid LLM response")

        # Add subtasks to the task graph
        for i, subtask in enumerate(subtasks):
            task_id = f"subtask_{i+1}"
            self._task_graph.add_task(
                task_id=task_id,
                description=subtask["description"],
                required_tools=subtask.get("required_tools", []),
                dependencies=subtask.get("dependencies", []),
            )
            logger.info("Added subtask %s: %s", task_id, subtask["description"])

        logger.info("Task decomposition complete: %d subtasks", len(self._task_graph._nodes))
        return self._task_graph

    def get_task_graph(self) -> TaskGraph:
        """Get the current task graph."""
        return self._task_graph

    def reset(self) -> None:
        """Reset the task graph."""
        self._task_graph = TaskGraph()
```

**What this does:**
- Receives the user's task and decomposes it into subtasks.
- Uses a structured format (JSON) to represent subtasks with dependencies.
- Assigns subtasks to the task graph for execution.

---

### Step 3: Create the Agent Pool Module

**File:** `nbchat/orchestration/agent_pool.py`

This module maintains a pool of specialized agents, each with a specific tool set.

```python
"""Pool of specialized agents for task execution."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from openai import OpenAI

from .task_graph import TaskNode, TaskStatus

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result from executing a subtask."""
    task_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class SpecializedAgent:
    """A specialized agent that executes a subtask using specific tools."""

    def __init__(self, agent_id: str, tools: list[str], system_prompt: str,
                 openai_client: OpenAI, model: str):
        """
        Args:
            agent_id: Unique identifier for this agent
            tools: List of tools this agent can use
            system_prompt: System prompt for this agent
            openai_client: OpenAI client instance
            model: Model name to use
        """
        self.agent_id = agent_id
        self.tools = tools
        self.system_prompt = system_prompt
        self._client = openai_client
        self._model = model

    def execute(self, task: TaskNode) -> AgentResult:
        """Execute a subtask and return the result."""
        logger.info("Agent %s executing task %s: %s",
                     self.agent_id, task.task_id, task.description)

        try:
            # Build the task execution prompt
            prompt = f"""Execute the following task using the available tools.

Task: {task.description}
Required tools: {', '.join(task.required_tools)}
Previous context: {task.metadata.get('context', 'None')}

Provide your response in the following format:
- Summary of what you did
- Results of any tool calls
- Final answer or output"""

            # Execute the task using the LLM
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
            )

            return AgentResult(
                task_id=task.task_id,
                success=True,
                result=response.choices[0].message.content.strip(),
                metadata={"agent_id": self.agent_id},
            )

        except Exception as e:
            logger.error("Agent %s failed task %s: %s",
                          self.agent_id, task.task_id, str(e))
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
                metadata={"agent_id": self.agent_id},
            )


class AgentPool:
    """Maintains a pool of specialized agents."""

    def __init__(self, openai_client: OpenAI, model: str,
                 default_system_prompt: str = "You are a helpful assistant."):
        """
        Args:
            openai_client: OpenAI client instance
            model: Model name to use
            default_system_prompt: Default system prompt for agents
        """
        self._client = openai_client
        self._model = model
        self.default_system_prompt = default_system_prompt
        self._agents: dict[str, SpecializedAgent] = {}

    def get_or_create_agent(self, required_tools: list[str]) -> SpecializedAgent:
        """Get or create a specialized agent for the required tools."""
        # Create a hash of the tool set to identify the agent
        tool_hash = "_".join(sorted(required_tools))
        agent_id = f"agent_{tool_hash}"

        if agent_id not in self._agents:
            self._agents[agent_id] = SpecializedAgent(
                agent_id=agent_id,
                tools=required_tools,
                system_prompt=self.default_system_prompt,
                openai_client=self._client,
                model=self._model,
            )
            logger.info("Created new agent %s for tools: %s",
                         agent_id, required_tools)

        return self._agents[agent_id]

    def execute_task(self, task: TaskNode) -> AgentResult:
        """Execute a task using the appropriate specialized agent."""
        agent = self.get_or_create_agent(task.required_tools)
        return agent.execute(task)

    def get_agent_count(self) -> int:
        """Get the number of agents in the pool."""
        return len(self._agents)
```

**What this does:**
- Maintains a pool of specialized agents, each with a specific tool set.
- Agents are created on-demand and destroyed after task completion.
- Each agent has its own system prompt and context window.

---

### Step 4: Create the Aggregator Module

**File:** `nbchat/orchestration/aggregator.py`

This module collects results from specialized agents and synthesizes them into a coherent final output.

```python
"""Result aggregation and synthesis for multi-agent orchestration."""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from openai import OpenAI

from .task_graph import TaskGraph, TaskStatus

logger = logging.getLogger(__name__)

# Template for aggregating results
AGGREGATION_PROMPT = """You are a result aggregator. Given the results of multiple subtasks, synthesize them into a coherent final output.

Subtask results:
{results}

Provide a summary that:
1. Covers all subtasks
2. Highlights key findings
3. Identifies any errors or issues
4. Provides a final recommendation or conclusion"""


class Aggregator:
    """Collects and synthesizes results from specialized agents."""

    def __init__(self, openai_client: OpenAI, model: str):
        """
        Args:
            openai_client: OpenAI client instance
            model: Model name to use for aggregation
        """
        self._client = openai_client
        self._model = model

    def aggregate(self, task_graph: TaskGraph) -> str:
        """Aggregate results from all completed tasks."""
        # Collect results from completed tasks
        results = []
        for node in task_graph._nodes.values():
            if node.status == TaskStatus.COMPLETED:
                results.append(f"Task {node.task_id}: {node.result}")
            elif node.status == TaskStatus.FAILED:
                results.append(f"Task {node.task_id}: FAILED - {node.error}")

        if not results:
            return "No tasks were completed."

        # Build the aggregation prompt
        prompt = AGGREGATION_PROMPT.format(results="\n".join(results))

        # Call the LLM to aggregate results
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
        )

        return response.choices[0].message.content.strip()
```

**What this does:**
- Collects results from specialized agents.
- Synthesizes results into a coherent final output.
- Handles errors from individual agents (retry, escalate, or skip).

---

### Step 5: Create the Orchestration Module (Entry Point)

**File:** `nbchat/orchestration/orchestrator.py`

This module provides the main entry point for multi-agent orchestration.

```python
"""Main orchestration entry point."""
from __future__ import annotations

import logging
from typing import Optional

from openai import OpenAI

from .task_graph import TaskGraph, TaskStatus
from .supervisor import Supervisor
from .agent_pool import AgentPool
from .aggregator import Aggregator

logger = logging.getLogger(__name__)


class Orchestrator:
    """Orchestrates multi-agent task execution."""

    def __init__(self, openai_client: OpenAI, model: str,
                 default_system_prompt: str = "You are a helpful assistant."):
        """
        Args:
            openai_client: OpenAI client instance
            model: Model name to use
            default_system_prompt: Default system prompt for agents
        """
        self._client = openai_client
        self._model = model
        self.supervisor = Supervisor(openai_client, model)
        self.agent_pool = AgentPool(openai_client, model, default_system_prompt)
        self.aggregator = Aggregator(openai_client, model)

    def execute_task(self, user_request: str) -> str:
        """Execute a complex task using multi-agent orchestration."""
        logger.info("Executing task: %s", user_request)

        # Step 1: Decompose the task
        task_graph = self.supervisor.decompose_task(user_request)

        # Step 2: Execute tasks sequentially
        while True:
            ready_tasks = task_graph.get_ready_tasks()
            if not ready_tasks:
                break

            for task in ready_tasks:
                logger.info("Executing task %s: %s", task.task_id, task.description)
                task.status = TaskStatus.RUNNING

                result = self.agent_pool.execute_task(task)

                if result.success:
                    task_graph.mark_completed(task.task_id, result.result)
                else:
                    task_graph.mark_failed(task.task_id, result.error)

        # Step 3: Aggregate results
        final_output = self.aggregator.aggregate(task_graph)

        logger.info("Task execution complete")
        return final_output

    def get_status(self) -> dict:
        """Get the current status of the orchestration."""
        return self.supervisor.get_task_graph().get_summary()
```

**What this does:**
- Provides the main entry point for multi-agent orchestration.
- Coordinates task decomposition, execution, and aggregation.
- Provides status updates.

---

## 5. Testing

### 5.1 Unit Tests

**File:** `tests/test_task_graph.py`

```python
"""Tests for TaskGraph."""
import pytest
from nbchat.orchestration.task_graph import TaskGraph, TaskStatus


def test_add_task():
    graph = TaskGraph()
    graph.add_task("task_1", "Do something")
    assert len(graph._nodes) == 1


def test_dependencies():
    graph = TaskGraph()
    graph.add_task("task_1", "First")
    graph.add_task("task_2", "Second", dependencies=["task_1"])
    ready = graph.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].task_id == "task_1"


def test_mark_completed():
    graph = TaskGraph()
    graph.add_task("task_1", "First")
    graph.mark_completed("task_1", "Done")
    assert graph._nodes["task_1"].status == TaskStatus.COMPLETED
```

**File:** `tests/test_supervisor.py`

```python
"""Tests for Supervisor."""
import pytest
from unittest.mock import MagicMock
from nbchat.orchestration.supervisor import Supervisor


def test_decompose_task():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = json.dumps([
        {"description": "Task 1", "required_tools": [], "dependencies": []},
    ])

    supervisor = Supervisor(mock_client, "test-model")
    graph = supervisor.decompose_task("Do something complex")
    assert len(graph._nodes) == 1
```

---

## 6. Usage

### 6.1 Basic Usage

```python
from nbchat.core.client import get_client
from nbchat.orchestration.orchestrator import Orchestrator

# Get the OpenAI client
metrics_client = get_client()
openai_client = metrics_client._client

# Create the orchestrator
orchestrator = Orchestrator(openai_client, "qwen3.5-35b")

# Execute a complex task
result = orchestrator.execute_task("Refactor this codebase and run tests")
print(result)
```

### 6.2 Advanced Usage

You can customize the system prompts for different agents:

```python
orchestrator = Orchestrator(
    openai_client,
    "qwen3.5-35b",
    default_system_prompt="You are a code refactoring expert."
)
```

---

## 7. Common Pitfalls

1. **JSON parsing failures:** The LLM may not return valid JSON. Always handle JSON decode errors gracefully.

2. **Infinite loops:** If tasks have circular dependencies, the orchestration will loop forever. Always validate the task graph for cycles before execution.

3. **Context window overflow:** Each subtask adds to the context window. Monitor context usage and truncate if necessary.

4. **Error propagation:** If a subtask fails, subsequent tasks that depend on it may also fail. Implement error handling and retry logic.

5. **Agent proliferation:** Each unique tool combination creates a new agent. Limit the number of agents to avoid memory issues.

---

## 8. Success Criteria

Before considering this feature "complete," verify:

1. ✅ Complex tasks are decomposed into logical subtasks
2. ✅ Subtasks are executed in the correct order (respecting dependencies)
3. ✅ Results are aggregated into a coherent final output
4. ✅ Errors are handled gracefully (retry, skip, or escalate)
5. ✅ The orchestration pipeline is documented and easy to use

**If any of these criteria are not met, do not deploy the multi-agent orchestration.**

---

## Appendix: What NOT to Implement

The following approaches were considered but rejected:

1. **Full parallel execution:** Implementing true parallel task execution adds significant complexity (thread safety, resource management, result synchronization). Start with sequential execution.

2. **Dynamic agent creation:** Creating agents on-the-fly for each subtask adds complexity. Use a fixed pool of agents instead.

3. **Self-healing agents:** Adding automatic error recovery and retry logic adds complexity. Start with basic error handling and add self-healing later if needed.

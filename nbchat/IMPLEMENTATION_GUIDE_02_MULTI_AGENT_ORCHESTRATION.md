# Implementation Guide: Multi-Agent Orchestration Layer (Opportunity 2)

> **Prerequisites:** Basic Python knowledge, familiarity with nbchat's codebase, understanding of async/await patterns.
> **Estimated time:** 3–5 days (including testing and iteration).
> **Source:** Meta-Harness "Multi-Agent Orchestration" approach.

---

## 1. Goal

Build a supervisor-specialized agent architecture where a supervisor agent decomposes complex tasks into subtasks and delegates them to specialized agents, enabling parallel execution and better handling of complex, multi-step tasks.

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
orchestration/
├── __init__.py
├── supervisor.py      # Task decomposition and delegation
├── agent_pool.py      # Pool of specialized agents
├── aggregator.py      # Result aggregation and synthesis
└── task_graph.py      # DAG-based task dependency management
```

### Component Relationships

```
User Request
    │
    ▼
┌─────────────┐
│  Supervisor │── Decomposes task into subtasks
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Task Graph │── Manages dependencies and parallelism
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Agent Pool  │── Creates specialized agents for each subtask
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Aggregator │── Collects and synthesizes results
└─────────────┘
```

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
    """Represents a single subtask in the DAG."""
    task_id: str
    description: str
    required_tools: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # task_ids
    result: Optional[Any] = None
    error: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    metadata: dict = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        """Check if all dependencies are completed."""
        if not self.dependencies:
            return True
        for dep_id in self.dependencies:
            # We'll add a method to check dependency status
            pass
        return True  # Placeholder


class TaskGraph:
    """Manages a DAG of tasks with dependency tracking."""

    def __init__(self, task_id_prefix: str = "task"):
        self._nodes: dict[str, TaskNode] = {}
        self._task_id_counter = 0
        self._prefix = task_id_prefix

    def add_task(self, description: str, required_tools: list[str] = None,
                 dependencies: list[str] = None) -> str:
        """Add a new task to the graph and return its ID."""
        self._task_id_counter += 1
        task_id = f"{self._prefix}_{self._task_id_counter}"
        
        node = TaskNode(
            task_id=task_id,
            description=description,
            required_tools=required_tools or [],
            dependencies=dependencies or [],
        )
        self._nodes[task_id] = node
        logger.info("Added task %s: %s (deps: %s)",
                     task_id, description, dependencies)
        return task_id

    def get_task(self, task_id: str) -> TaskNode:
        """Get a task by ID."""
        if task_id not in self._nodes:
            raise KeyError(f"Unknown task: {task_id}")
        return self._nodes[task_id]

    def get_ready_tasks(self) -> list[TaskNode]:
        """Get all tasks that are ready to execute (dependencies met)."""
        ready = []
        for node in self._nodes.values():
            if node.status == TaskStatus.PENDING:
                deps_met = all(
                    self._nodes[dep_id].status == TaskStatus.COMPLETED
                    for dep_id in node.dependencies
                    if dep_id in self._nodes
                )
                if deps_met:
                    ready.append(node)
        return ready

    def mark_completed(self, task_id: str, result: Any = None) -> None:
        """Mark a task as completed with a result."""
        node = self.get_task(task_id)
        node.status = TaskStatus.COMPLETED
        node.result = result
        logger.info("Task %s completed", task_id)

    def mark_failed(self, task_id: str, error: str) -> None:
        """Mark a task as failed and skip dependent tasks."""
        node = self.get_task(task_id)
        node.status = TaskStatus.FAILED
        node.error = error
        logger.warning("Task %s failed: %s", task_id, error)
        
        # Skip dependent tasks
        for dep_id, dep_node in self._nodes.items():
            if task_id in dep_node.dependencies:
                dep_node.status = TaskStatus.SKIPPED
                dep_node.error = f"Dependency {task_id} failed"
                logger.info("Task %s skipped due to dependency failure", dep_id)

    def get_completed_tasks(self) -> list[TaskNode]:
        """Get all completed tasks."""
        return [n for n in self._nodes.values() if n.status == TaskStatus.COMPLETED]

    def get_failed_tasks(self) -> list[TaskNode]:
        """Get all failed tasks."""
        return [n for n in self._nodes.values() if n.status == TaskStatus.FAILED]

    def is_complete(self) -> bool:
        """Check if all tasks are completed or skipped."""
        for node in self._nodes.values():
            if node.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                return False
        return True

    def get_summary(self) -> dict:
        """Get a summary of the task graph."""
        return {
            "total": len(self._nodes),
            "completed": len(self.get_completed_tasks()),
            "failed": len(self.get_failed_tasks()),
            "pending": sum(1 for n in self._nodes.values() if n.status == TaskStatus.PENDING),
            "running": sum(1 for n in self._nodes.values() if n.status == TaskStatus.RUNNING),
            "skipped": sum(1 for n in self._nodes.values() if n.status == TaskStatus.SKIPPED),
        }
```

**What this does:**
- Represents subtasks as nodes in a DAG.
- Tracks dependencies between tasks.
- Identifies which tasks are ready to execute.
- Marks tasks as completed, failed, or skipped.
- Provides summary statistics.

### Step 2: Create the Supervisor Module

**File:** `nbchat/orchestration/supervisor.py`

This module receives the user's task and decomposes it into subtasks using an LLM.

```python
"""Supervisor agent for task decomposition and delegation."""
from __future__ import annotations

import json
import logging
from typing import Optional

from .task_graph import TaskGraph

logger = logging.getLogger(__name__)

# Template for decomposing tasks
DECOMPOSITION_PROMPT = """You are a task decomposition expert. Given a complex user request, break it down into independent subtasks that can be executed in parallel.

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

    def __init__(self, client, available_tools: list[str] = None):
        self.client = client
        self.available_tools = available_tools or []
        self._task_graph = TaskGraph()

    def decompose_task(self, user_request: str) -> TaskGraph:
        """Decompose a user request into subtasks."""
        logger.info("Decomposing task: %s", user_request)
        
        # Build the decomposition prompt
        prompt = DECOMPOSITION_PROMPT.format(user_request=user_request)
        
        # Call the LLM to decompose the task
        response = self.client.send_message(prompt)
        
        # Parse the JSON response
        try:
            subtasks = json.loads(response)
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM response as JSON: %s", response)
            raise ValueError("Failed to decompose task: invalid LLM response")
        
        # Add subtasks to the task graph
        for i, subtask in enumerate(subtasks):
            task_id = f"subtask_{i+1}"
            self._task_graph.add_task(
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

### Step 3: Create the Agent Pool Module

**File:** `nbchat/orchestration/agent_pool.py`

This module maintains a pool of specialized agents, each with a specific tool set.

```python
"""Pool of specialized agents for task execution."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

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
                 client):
        self.agent_id = agent_id
        self.tools = tools
        self.system_prompt = system_prompt
        self.client = client

    async def execute(self, task: TaskNode) -> AgentResult:
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
            response = self.client.send_message(prompt, system_prompt=self.system_prompt)
            
            return AgentResult(
                task_id=task.task_id,
                success=True,
                result=response,
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

    def __init__(self, client, default_system_prompt: str = "You are a helpful assistant."):
        self.client = client
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
                client=self.client,
            )
            logger.info("Created new agent %s for tools: %s",
                         agent_id, required_tools)
        
        return self._agents[agent_id]

    async def execute_task(self, task: TaskNode) -> AgentResult:
        """Execute a task using the appropriate specialized agent."""
        agent = self.get_or_create_agent(task.required_tools)
        return await agent.execute(task)

    def get_agent_count(self) -> int:
        """Get the number of agents in the pool."""
        return len(self._agents)
```

**What this does:**
- Maintains a pool of specialized agents, each with a specific tool set.
- Agents are created on-demand and destroyed after task completion.
- Each agent has its own system prompt and context window.

### Step 4: Create the Aggregator Module

**File:** `nbchat/orchestration/aggregator.py`

This module collects results from specialized agents and synthesizes them into a coherent final output.

```python
"""Result aggregation and synthesis for multi-agent orchestration."""
from __future__ import annotations

import logging
from typing import Any, Optional

from .task_graph import TaskGraph, TaskStatus

logger = logging.getLogger(__name__)

# Template for synthesizing results
SYNTHESIS_PROMPT = """You are a result synthesizer. Given the results of multiple subtasks, synthesize them into a coherent final output.

Subtask results:
{results}

Provide a final answer that:
1. Summarizes the results of each subtask.
2. Identifies any errors or failures.
3. Provides a coherent final output.

User request: {user_request}

Final output:"""


class Aggregator:
    """Collects results from specialized agents and synthesizes them."""

    def __init__(self, client, task_graph: TaskGraph):
        self.client = client
        self.task_graph = task_graph

    def aggregate_results(self) -> dict:
        """Aggregate results from all completed tasks."""
        completed = self.task_graph.get_completed_tasks()
        failed = self.task_graph.get_failed_tasks()
        skipped = [n for n in self.task_graph._nodes.values() if n.status == TaskStatus.SKIPPED]
        
        return {
            "completed_tasks": [
                {"task_id": n.task_id, "result": n.result}
                for n in completed
            ],
            "failed_tasks": [
                {"task_id": n.task_id, "error": n.error}
                for n in failed
            ],
            "skipped_tasks": [
                {"task_id": n.task_id, "reason": n.error}
                for n in skipped
            ],
            "summary": self.task_graph.get_summary(),
        }

    def synthesize_final_output(self, user_request: str) -> str:
        """Synthesize results into a final output using the LLM."""
        aggregated = self.aggregate_results()
        
        # Format the results for the synthesis prompt
        results_text = "\n".join([
            f"- Task {r['task_id']}: {r['result']}"
            for r in aggregated["completed_tasks"]
        ])
        
        if aggregated["failed_tasks"]:
            results_text += "\n\nFailed tasks:\n" + "\n".join([
                f"- Task {r['task_id']}: {r['error']}"
                for r in aggregated["failed_tasks"]
            ])
        
        # Build the synthesis prompt
        prompt = SYNTHESIS_PROMPT.format(
            results=results_text,
            user_request=user_request,
        )
        
        # Call the LLM to synthesize the final output
        response = self.client.send_message(prompt)
        
        return response

    def has_failures(self) -> bool:
        """Check if any tasks failed."""
        return len(self.task_graph.get_failed_tasks()) > 0

    def has_skipped(self) -> bool:
        """Check if any tasks were skipped."""
        return len([n for n in self.task_graph._nodes.values() if n.status == TaskStatus.SKIPPED]) > 0
```

**What this does:**
- Collects results from specialized agents.
- Synthesizes results into a coherent final output.
- Handles errors from individual agents (retry, escalate, or skip).

### Step 5: Create the Orchestration Module (Entry Point)

**File:** `nbchat/orchestration/__init__.py`

This module provides the main entry point for multi-agent orchestration.

```python
"""Multi-agent orchestration module for nbchat."""
from __future__ import annotations

import asyncio
import logging

from .aggregator import Aggregator
from .agent_pool import AgentPool
from .supervisor import Supervisor

logger = logging.getLogger(__name__)


class Orchestrator:
    """Main orchestrator for multi-agent task execution."""

    def __init__(self, client, available_tools: list[str] = None,
                 default_system_prompt: str = "You are a helpful assistant."):
        self.client = client
        self.supervisor = Supervisor(client, available_tools)
        self.agent_pool = AgentPool(client, default_system_prompt)
        self.aggregator = None

    async def execute_task(self, user_request: str) -> str:
        """Execute a complex task using multi-agent orchestration."""
        logger.info("Starting multi-agent orchestration for: %s", user_request)
        
        # Step 1: Decompose the task
        task_graph = self.supervisor.decompose_task(user_request)
        
        # Step 2: Execute tasks in parallel (respecting dependencies)
        await self._execute_tasks(task_graph)
        
        # Step 3: Aggregate and synthesize results
        self.aggregator = Aggregator(self.client, task_graph)
        final_output = self.aggregator.synthesize_final_output(user_request)
        
        logger.info("Multi-agent orchestration complete")
        return final_output

    async def _execute_tasks(self, task_graph) -> None:
        """Execute all tasks in the graph, respecting dependencies."""
        while not task_graph.is_complete():
            # Get ready tasks
            ready_tasks = task_graph.get_ready_tasks()
            
            if not ready_tasks:
                # No ready tasks, check if we're stuck
                pending = [n for n in task_graph._nodes.values()
                          if n.status in (TaskStatus.PENDING, TaskStatus.RUNNING)]
                if pending:
                    logger.warning("Stuck: no ready tasks but %d tasks pending", len(pending))
                    # Mark all remaining tasks as failed
                    for task in pending:
                        task_graph.mark_failed(task.task_id, "No ready tasks (stuck)")
                break
            
            # Execute ready tasks in parallel
            tasks = []
            for task in ready_tasks:
                task.status = TaskStatus.RUNNING
                tasks.append(self._execute_single_task(task))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for task, result in zip(ready_tasks, results):
                if isinstance(result, Exception):
                    task_graph.mark_failed(task.task_id, str(result))
                elif hasattr(result, 'success') and result.success:
                    task_graph.mark_completed(task.task_id, result.result)
                else:
                    task_graph.mark_failed(task.task_id, result.error)

    async def _execute_single_task(self, task) -> AgentResult:
        """Execute a single task."""
        return await self.agent_pool.execute_task(task)
```

**What this does:**
- Provides the main entry point for multi-agent orchestration.
- Coordinates the supervisor, agent pool, and aggregator.
- Executes tasks in parallel while respecting dependencies.

---

## 5. Testing

### 5.1 Unit Tests

**File:** `tests/test_task_graph.py`

```python
"""Tests for TaskGraph."""
import pytest
from nbchat.orchestration.task_graph import TaskGraph, TaskStatus


def test_add_task():
    """Test adding a task to the graph."""
    graph = TaskGraph()
    task_id = graph.add_task("Test task")
    assert task_id == "task_1"
    assert graph.get_task(task_id).description == "Test task"


def test_task_dependencies():
    """Test task dependencies."""
    graph = TaskGraph()
    task1 = graph.add_task("Task 1")
    task2 = graph.add_task("Task 2", dependencies=[task1])
    
    # Task 2 should not be ready until Task 1 is completed
    ready = graph.get_ready_tasks()
    assert task1 in ready
    assert task2 not in ready
    
    # Complete Task 1
    graph.mark_completed(task1)
    ready = graph.get_ready_tasks()
    assert task2 in ready


def test_task_failure_skips_dependents():
    """Test that task failure skips dependent tasks."""
    graph = TaskGraph()
    task1 = graph.add_task("Task 1")
    task2 = graph.add_task("Task 2", dependencies=[task1])
    
    # Fail Task 1
    graph.mark_failed(task1, "Error")
    
    # Task 2 should be skipped
    assert task2.status == TaskStatus.SKIPPED


def test_is_complete():
    """Test is_complete method."""
    graph = TaskGraph()
    task1 = graph.add_task("Task 1")
    
    # Not complete yet
    assert not graph.is_complete()
    
    # Complete the task
    graph.mark_completed(task1)
    assert graph.is_complete()


def test_get_summary():
    """Test get_summary method."""
    graph = TaskGraph()
    task1 = graph.add_task("Task 1")
    task2 = graph.add_task("Task 2")
    
    graph.mark_completed(task1)
    graph.mark_failed(task2, "Error")
    
    summary = graph.get_summary()
    assert summary["total"] == 2
    assert summary["completed"] == 1
    assert summary["failed"] == 1
```

**File:** `tests/test_supervisor.py`

```python
"""Tests for Supervisor."""
import pytest
from nbchat.orchestration.supervisor import Supervisor


class MockClient:
    """Mock LLM client for testing."""
    def __init__(self, response: str):
        self.response = response

    def send_message(self, prompt: str, system_prompt: str = None) -> str:
        return self.response


def test_decompose_task():
    """Test task decomposition."""
    client = MockClient('[{"description": "Task 1", "required_tools": ["tool1"]}]')
    supervisor = Supervisor(client)
    
    task_graph = supervisor.decompose_task("Test request")
    assert len(task_graph._nodes) == 1
    assert task_graph.get_task("subtask_1").description == "Task 1"
```

### 5.2 Integration Test

**File:** `tests/test_orchestration_e2e.py`

```python
"""End-to-end test for multi-agent orchestration."""
import asyncio
import pytest
from nbchat.orchestration import Orchestrator


class MockClient:
    """Mock LLM client for testing."""
    def __init__(self):
        self.calls = []

    def send_message(self, prompt: str, system_prompt: str = None) -> str:
        self.calls.append(prompt)
        # Simple heuristic: return a mock response
        if "decompose" in prompt.lower() or "decomposition" in prompt.lower():
            return '[{"description": "Task 1", "required_tools": [], "dependencies": []}, {"description": "Task 2", "required_tools": [], "dependencies": []}]'
        return "Task completed successfully."


@pytest.mark.asyncio
async def test_e2e_orchestration():
    """Test end-to-end orchestration with mock LLM."""
    client = MockClient()
    orchestrator = Orchestrator(client)
    
    result = await orchestrator.execute_task("Test complex task")
    assert "Task completed successfully" in result
```

### 5.3 Run Tests

```bash
cd nbchat
python -m pytest tests/test_task_graph.py tests/test_supervisor.py tests/test_orchestration_e2e.py -v
```

---

## 6. Usage

### 6.1 Basic Usage

```python
from nbchat.orchestration import Orchestrator
from nbchat.core.client import ChatClient
from nbchat.core.config import Config

# Load config
config = Config("repo_config.yaml")

# Create client
client = ChatClient(config)

# Create orchestrator
orchestrator = Orchestrator(
    client=client,
    available_tools=["file_editor", "command_runner", "web_searcher"],
)

# Execute a complex task
result = asyncio.run(orchestrator.execute_task("Refactor this codebase and run tests"))
print(result)
```

### 6.2 Advanced Usage

```python
# Execute multiple tasks in sequence
tasks = [
    "Refactor this codebase",
    "Run tests and fix failures",
    "Generate documentation",
]

for task in tasks:
    result = asyncio.run(orchestrator.execute_task(task))
    print(f"Task: {task}\nResult: {result}\n")
```

---

## 7. Common Pitfalls

1. **Circular dependencies:** Ensure that the task graph is a DAG (Directed Acyclic Graph). Circular dependencies will cause infinite loops.

2. **Resource exhaustion:** Each specialized agent consumes resources. Limit the number of concurrent agents.

3. **LLM API rate limits:** Multi-agent orchestration makes many LLM calls. Use the existing retry policy in `nbchat/core/retry.py` and consider batching.

4. **Error propagation:** If a critical task fails, dependent tasks may also fail. Implement proper error handling and fallback strategies.

5. **Context window pressure:** Each agent has its own context window. Monitor context usage and compress as needed.

---

## 8. Success Criteria

- [ ] All unit tests pass.
- [ ] Integration test shows the orchestrator runs end-to-end.
- [ ] The orchestrator correctly decomposes complex tasks into subtasks.
- [ ] The orchestrator executes tasks in parallel while respecting dependencies.
- [ ] The aggregator synthesizes results into a coherent final output.

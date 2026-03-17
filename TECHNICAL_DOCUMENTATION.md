# Reasoning Gym: Comprehensive Technical Documentation

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Data Structures](#data-structures)
5. [Dataset Registration System](#dataset-registration-system)
6. [Curriculum Learning](#curriculum-learning)
7. [Composite Datasets](#composite-datasets)
8. [Domain-Specific Modules](#domain-specific-modules)
9. [Evaluation Framework](#evaluation-framework)
10. [Training Integration](#training-integration)
11. [Pseudocode and Algorithms](#pseudocode-and-algorithms)
12. [Flowcharts and Sequence Diagrams](#flowcharts-and-sequence-diagrams)
13. [Usage Examples](#usage-examples)

---

## 1. Overview

### 1.1 Purpose

**Reasoning Gym** is a Python library that provides **procedural dataset generators** for training reasoning models using reinforcement learning (RL). The key innovation is the ability to generate **virtually infinite training data with adjustable complexity** through algorithmic problem generation.

### 1.2 Key Features

- **105+ Procedural Datasets** across multiple domains:
  - Algebra, Arithmetic, Computation, Cognition, Geometry, Graph Theory, Logic, Games, etc.
- **Algorithmic Verification**: Standard interface for procedurally verifying solutions
- **Multiple Solution Support**: Some tasks (e.g., Rubik's Cube, Countdown) have many correct solutions
- **Curriculum Learning**: Progressive difficulty scaling for each dataset
- **Composite Datasets**: Weighted combination of multiple datasets
- **Seeded Generation**: Reproducible and infinite data generation

### 1.3 Design Philosophy

```
┌─────────────────────────────────────────────────────────────────┐
│                    Reasoning Gym Philosophy                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  • Procedural Generation: Infinite data through algorithmic     │
│    construction rather than static curation                     │
│                                                                 │
│  • Algorithmic Verification: Truth determined by computation,  │
│    not human labeling                                           │
│                                                                 │
│  • Adjustable Difficulty: Configurable complexity parameters   │
│                                                                 │
│  • Standardized Interface: Consistent API across all           │
│    datasets                                                     │
│                                                                 │
│  • RL-Optimized: Rewards in [0,1] for gradient-based learning  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Reasoning Gym System                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Application Layer                          │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │  │
│  │  │   eval.py   │  │ train.py    │  │   create_dataset()  │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           │                                         │
│                           ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  Core API Layer                               │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │  │
│  │  │   get_score │  │  register_  │  │   create_curriculum │  │  │
│  │  │  _answer_fn │  │  _dataset() │  │                     │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           │                                         │
│                           ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   Registration Layer                          │  │
│  │                    (factory.py)                               │  │
│  │  ┌──────────────────────────────────────────────────────┐   │  │
│  │  │              Global Dataset Registry                  │   │  │
│  │  │              DATASETS: {name: (cls, config_cls)}     │   │  │
│  │  │              CURRICULA: {name: Curriculum}           │   │  │
│  │  └──────────────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           │                                         │
│                           ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   Domain Modules                              │  │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐     │  │
│  │  │ algebra │ │ arithmetic │ │ games │ │ geometry │ │ logic │   │  │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           │                                         │
│                           ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   Base Classes                                │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │  │
│  │  │ProceduralDataset │ │    BaseCurriculum    │ │ CompositeDataset │ │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Package Structure

```
reasoning-gym/
├── reasoning_gym/
│   ├── __init__.py              # Package entry point
│   ├── factory.py               # Dataset registration and creation
│   ├── dataset.py               # Base ProceduralDataset class
│   ├── composite.py             # CompositeDataset implementation
│   ├── version_manager.py       # Version tracking for datasets
│   ├── utils.py                 # Utility functions
│   ├── coaching/                # Curriculum learning module
│   │   ├── __init__.py
│   │   ├── base_curriculum.py   # BaseCurriculum class
│   │   ├── attributes.py        # Attribute definitions
│   │   ├── experiment.py        # Experiment tracking
│   │   └── score_board.py       # Score aggregation
│   └── [domain_modules]/        # Domain-specific datasets
│       ├── algebra/
│       ├── arithmetic/
│       ├── games/
│       ├── geometry/
│       ├── logic/
│       ├── graphs/
│       └── ... (12 domains total)
├── eval/                        # Evaluation scripts
├── training/                    # Training configurations
├── examples/                    # Example code
└── tests/                       # Unit tests
```

---

## 3. Core Components

### 3.1 ProceduralDataset (Base Class)

```
┌─────────────────────────────────────────────────────────────────┐
│                   ProceduralDataset Interface                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Required Parameters:                                           │
│  • config: Any           - Dataset configuration object        │
│  • seed: Optional[int]   - Random seed for reproducibility     │
│  • size: int             - Virtual dataset size (default: 500) │
│                                                                 │
│  Required Methods (Abstract):                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  def __getitem__(self, idx: int) -> dict[str, Any]     │   │
│  │      Generate task at index idx                         │   │
│  │      Returns: {                                          │   │
│  │          "question": str,                                │   │
│  │          "answer": str,                                 │   │
│  │          "metadata": dict                               │   │
│  │      }                                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Optional Override:                                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  def score_answer(self, answer, entry) -> float [0,1]  │   │
│  │      Verify solution correctness                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Implemented Features:                                          │
│  • Virtual size (infinite potential)                           │
│  • Iteration with index tracking                               │
│  • Automatic category extraction from module name             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Dataset Configuration

```
┌─────────────────────────────────────────────────────────────────┐
│                  Dataset Configuration Pattern                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  @dataclass                                            │    │
│  │  class DatasetConfig:                                  │    │
│  │      ├── min_terms: int = 2                           │    │
│  │      ├── max_terms: int = 4                           │    │
│  │      ├── min_value: int = 1                           │    │
│  │      ├── max_value: int = 100                         │    │
│  │      ├── operators: tuple = ("+", "-", "*")          │    │
│  │      ├── operators_weights: list[float] = [...]      │    │
│  │      └── seed: Optional[int] = None                  │    │
│  │                                                        │    │
│  │  def validate(self) -> None:                          │    │
│  │      # Validate configuration parameters              │    │
│  │      assert self.min_terms > 0                        │    │
│  │      assert self.max_terms >= self.min_terms          │    │
│  │      ...                                              │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
│  Configuration Validation:                                      │
│  • All datasets implement validate() method                    │
│  • Can throw AssertionError for invalid configs                │
│  • Called during dataset initialization                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Answer Scoring

```
┌─────────────────────────────────────────────────────────────────┐
│                    Answer Scoring Strategies                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Standard Scoring (Single Correct Answer):                      │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  reward = 1.0 if answer == oracle_answer else 0.0     │    │
│  │  # Optional partial credit:                           │    │
│  │  reward = len(oracle_answer) / len(answer)            │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
│  Multi-Solution Scoring (override required):                    │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  def score_answer(self, answer, entry) -> float:      │    │
│  │      valid_answers = self.get_all_valid_answers(entry)│    │
│  │      for valid in valid_answers:                      │    │
│  │          if valid in answer or answer in valid:       │    │
│  │              return compute_partial_credit(answer)    │    │
│  │      return 0.0                                       │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
│  Examples of Multi-Solution Datasets:                           │
│  • Rubik's Cube: Many valid sequences to solve                  │
│  • Countdown: Multiple arithmetic paths to same result          │
│  • Sudoku: Multiple valid solution grids                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Structures

### 4.1 Task Entry Structure

```python
# Every dataset entry is a dictionary with the following structure:

entry = {
    # Required fields
    "question": str,        # Human-readable problem statement
    "answer": str,          # Correct answer (may be partial for multi-solution)
    "metadata": {
        # Dataset source information
        "source_dataset": str,      # e.g., "simple_equations"
        "source_index": int,        # Index within dataset
        
        # Domain-specific metadata
        "equation": str,            # Original equation string
        "variable": str,            # Variable used (e.g., "x", "y")
        "difficulty": {
            "min_terms": int,
            "max_terms": int,
            "min_value": int,
            "max_value": int,
            "operators_weights": list[float]
        },
        
        # Version tracking (for composite datasets)
        "version_id": str,          # e.g., "0.123"
        "entry_id": str,            # e.g., "0.42"
    }
}

# Example:
{
    "question": "Find the value of x in the equation: 3 * x = 12",
    "answer": "4",
    "metadata": {
        "source_dataset": "simple_equations",
        "source_index": 42,
        "equation": "3 * x = 12",
        "variable": "x",
        "difficulty": {
            "min_terms": 2,
            "max_terms": 4,
            "min_value": 1,
            "max_value": 100,
            "operators_weights": [0.4, 0.4, 0.2]
        },
        "source_dataset": "simple_equations"
    }
}
```

### 4.2 Metadata Schema

```
┌─────────────────────────────────────────────────────────────────┐
│                      Metadata Fields Schema                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Common Fields (all datasets):                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  source_dataset: str        - Dataset name identifier    │  │
│  │  source_index: int          - Index in source dataset    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Domain-Specific Fields:                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Algebra: equation, variable, coefficients              │  │
│  │  Arithmetic: operations, numbers, complexity_level      │  │
│  │  Geometry: shape_type, dimensions, constraints          │  │
│  │  Games: board_size, move_count, win_condition           │  │
│  │  Logic: proposition_count, rule_complexity              │  │
│  │  Graphs: node_count, edge_density, graph_type           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Composite Fields:                                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  version_id: str             - Version identifier        │  │
│  │  entry_id: str               - Global entry identifier   │  │
│  │  source_dataset: str         - Which sub-dataset         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Dataset Registration System

### 5.1 Registration Mechanism

```
┌─────────────────────────────────────────────────────────────────┐
│                  Dataset Registration System                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  from reasoning_gym.factory import register_dataset    │    │
│  │  from reasoning_gym.dataset import ProceduralDataset  │    │
│  │  from dataclasses import dataclass                    │    │
│  │                                                        │    │
│  │  @dataclass                                           │    │
│  │  class MyConfig:                                      │    │
│  │      min_value: int = 1                               │    │
│  │      max_value: int = 100                             │    │
│  │                                                        │    │
│  │  class MyDataset(ProceduralDataset):                  │    │
│  │      # Implementation                                 │    │
│  │      pass                                             │    │
│  │                                                        │    │
│  │  DATASET_NAME = "my_dataset"                          │    │
│  │  register_dataset(                                    │    │
│  │      DATASET_NAME,                                    │    │
│  │      MyDataset,                                       │    │
│  │      MyConfig                                         │    │
│  │  )                                                    │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
│  Registration Requirements:                                     │
│  • Dataset class must inherit from ProceduralDataset           │
│  • Config class must be a dataclass                            │
│  • Each dataset must have unique name                          │
│  • Registration happens at module import time                  │
│                                                                 │
│  Internal Registry:                                             │
│  DATASETS: dict[str, tuple[Type[ProceduralDataset], Type]] = {}│
│  CURRICULA: dict[str, BaseCurriculum] = {}                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Factory Functions

```python
# reasoning_gym/factory.py

def register_dataset(
    name: str,
    dataset_cls: Type[ProceduralDataset],
    config_cls: Type[ConfigT],
    curriculum_cls: Optional[CurriculumT] = None,
) -> None:
    """Register a dataset class with the global registry."""
    if name in DATASETS:
        raise ValueError(f"Dataset '{name}' is already registered")
    
    if not issubclass(dataset_cls, ProceduralDataset):
        raise ValueError(f"Dataset class must inherit from ProceduralDataset")
    
    if not is_dataclass(config_cls):
        raise ValueError(f"Config class must be a dataclass")
    
    DATASETS[name] = (dataset_cls, config_cls)
    if curriculum_cls:
        CURRICULA[name] = curriculum_cls


def create_dataset(name: str, **kwargs) -> ProceduralDataset:
    """Create a dataset instance by name with given configuration."""
    if name not in DATASETS:
        raise ValueError(f"Dataset '{name}' not registered")
    
    dataset_cls, config_cls = DATASETS[name]
    config = config_cls(**kwargs)
    
    if hasattr(config, "validate"):
        config.validate()
    
    return dataset_cls(config=config)


def get_score_answer_fn(name: str):
    """Get the score_answer function for a dataset."""
    if name not in DATASETS:
        raise ValueError(f"Dataset '{name}' not registered")
    
    dataset_cls, config_cls = DATASETS[name]
    return dataset_cls(config=config_cls()).score_answer
```

---

## 6. Curriculum Learning

### 6.1 Curriculum System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Curriculum Learning System                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Purpose: Progressive difficulty scaling for RL training        │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  BaseCurriculum                                        │    │
│  │  ├─ Define difficulty attributes                       │    │
│  │  ├─ Track current levels for each attribute           │    │
│  │  ├─ Generate configurations at any level              │    │
│  │  └─ Increment/decrement difficulty levels             │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
│  Attribute Types:                                               │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  ScalarAttributeDefinition:                           │    │
│  │      - Single value per level                         │    │
│  │      - Example: min_value = [1, 10, 100, 1000]       │    │
│  │                                                        │    │
│  │  RangeAttributeDefinition:                            │    │
│  │      - Value range per level                          │    │
│  │      - Example: num_items = [(10,20), (20,50),...]   │    │
│  │      - Supports different range modes                 │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
│  Range Attribute Modes:                                         │
│  • UPPER_BOUND: Use only highest value in range                │
│  • INCLUSIVE: Include all values up to current level           │
│  • LAST_K: Use only last K difficulty levels                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Curriculum Class Structure

```python
# BaseCurriculum structure

class BaseCurriculum:
    def __init__(self, name: str, config_cls: ConfigT):
        self.name = name
        self._config_cls = config_cls
        self._attributes: dict[str, AttributeDefinition] = {}
        self._current_levels: dict[str, int] = {}
    
    def _define_attributes(self, *attrs: AttributeDefinition) -> None:
        """Define difficulty attributes with levels."""
        for attr in attrs:
            self.attributes[attr.name] = attr
    
    def get_attr_level(self, attr_name: str) -> int:
        """Get current level index for attribute."""
        attr = self.get_attribute(attr_name)
        return self._current_levels.get(attr_name, attr.default_level)
    
    def get_attr_value(self, attr_name: str) -> Any:
        """Get current value based on level and attribute type."""
        attr = self.get_attribute(attr_name)
        level = self.get_attr_level(attr_name)
        return attr.get_level_value(level)
    
    def increment_attr_level(self, attr_name: str) -> bool:
        """Increment difficulty level."""
        current_level = self.get_attr_level(attr_name)
        if current_level < len(attr.levels) - 1:
            self.set_attr_level(attr_name, current_level + 1)
            return True
        return False
    
    def set_global_level(self, level: int) -> None:
        """Set all attributes to specified level."""
        for attr_name, attr in self._attributes.items():
            attr_level = min(level, len(attr.levels) - 1)
            self.set_attr_level(attr_name, attr_level)
    
    def generate_configuration(self, defaults=None) -> ConfigT:
        """Generate configuration at current levels."""
        config_args = defaults.copy() if defaults else {}
        for attr in self._attributes.values():
            if isinstance(attr, RangeAttributeDefinition):
                v = context.get_range_attr_value(self, attr)
                config_args[attr.lower_field_name] = min(v)
                config_args[attr.upper_field_name] = max(v)
            elif isinstance(attr, ScalarAttributeDefinition):
                val = context.get_attr_value(self, attr)
                config_args[attr.field_name] = val
        return self._config_cls(**config_args)

# Example: SimpleEquationsCurriculum

class SimpleEquationsCurriculum(BaseCurriculum):
    def __init__(self):
        super().__init__("simple_equations", SimpleEquationsConfig)
        
        # Define difficulty attributes
        self._define_attributes(
            ScalarAttributeDefinition(
                name="min_terms",
                field_name="min_terms",
                levels=[2, 3, 4, 5],
                description="Minimum number of terms"
            ),
            RangeAttributeDefinition(
                name="max_value",
                lower_field_name="min_value",
                upper_field_name="max_value",
                levels=[
                    [1, 100],
                    [10, 1000],
                    [100, 10000],
                    [1000, 100000]
                ],
                description="Value range for constants"
            )
        )
```

---

## 7. Composite Datasets

### 7.1 Composite Dataset Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Composite Dataset                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Purpose: Combine multiple datasets with weighted sampling      │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  CompositeDataset                                      │    │
│  │  ├─ Internal state:                                    │    │
│  │  │   • datasets: dict[name -> ProceduralDataset]      │    │
│  │  │   • weights: list[float]                           │    │
│  │  │   • dataset_names: list[str]                       │    │
│  │  └─ Methods:                                          │    │
│  │      • __getitem__(idx) - Weighted sampling           │    │
│  │      • update_dataset_config() - Modify sub-dataset   │    │
│  │      • add_dataset() - Add new sub-dataset            │    │
│  │      • remove_dataset() - Remove sub-dataset          │    │
│  │      • score_answer() - Forward to appropriate dataset│    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
│  Weighted Sampling Algorithm:                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  1. For index idx, create deterministic RNG            │    │
│  │     rng = Random(seed + idx)                           │    │
│  │                                                        │    │
│  │  2. Sample dataset index according to weights          │    │
│  │     dataset_idx = rng.choices(range(n_datasets),       │    │
│  │                              weights=weights, k=1)[0]  │    │
│  │                                                        │    │
│  │  3. Get item from selected dataset                     │    │
│  │     item = datasets[dataset_names[dataset_idx]][idx]   │    │
│  │                                                        │    │
│  │  4. Add metadata for tracking                          │    │
│  │     item["metadata"]["source_dataset"] = dataset_name  │    │
│  │     item["metadata"]["entry_id"] = f"{version}.{idx}"  │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 DatasetSpec

```python
@dataclass
class DatasetSpec:
    """Specification for a single dataset within composite."""
    name: str           # Dataset name from registry
    weight: float       # Relative weight in sampling
    config: dict        # Configuration parameters
    
    def validate(self):
        assert self.name, "Dataset name cannot be empty"
        assert self.weight > 0, "Weight must be positive"
        assert isinstance(self.config, dict), "Config must be dict"

# Example composite configuration:
specs = [
    DatasetSpec(
        name="leg_counting",
        weight=2,  # 2/3 of samples
        config={}
    ),
    DatasetSpec(
        name="figlet_font",
        weight=1,  # 1/3 of samples
        config={"min_word_len": 4, "max_word_len": 6}
    ),
]
```

---

## 8. Domain-Specific Modules

### 8.1 Domain Categories

```
┌─────────────────────────────────────────────────────────────────┐
│                     Domain Categories                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  algebra/              Mathematical equations and expressions   │
│                        • Simple equations                       │
│                        • Polynomial equations                   │
│                        • Complex arithmetic                     │
│                        • Polynomial multiplication              │
│                        • Integration problems                   │
│                                                                 │
│  arithmetic/           Basic numerical computations             │
│                        • Basic arithmetic                       │
│                        • Chain sum                              │
│                        • Decimal arithmetic                     │
│                        • Bitwise arithmetic                     │
│                        • Base conversion                        │
│                        • Products/multiplication tables         │
│                                                                 │
│  games/                Game-based reasoning tasks               │
│                        • Rubik's Cube                           │
│                        • Countdown                              │
│                        • Sokoban                                │
│                        • Rush Hour                               │
│                        • Tower of Hanoi                         │
│                        • Knight Swap                            │
│                        • Futoshiki                              │
│                        • Sudoku                                 │
│                        • Game of Life                           │
│                                                                 │
│  geometry/             Geometric reasoning                      │
│                        • Simple geometry                        │
│                        • Advanced geometry                      │
│                        • Rectangle counting                     │
│                        • Spiral matrix                          │
│                                                                 │
│  graphs/               Graph theory problems                    │
│                        • Graph coloring                         │
│                        • Shortest path                          │
│                        • N-Queens                               │
│                        • Largest island                         │
│                                                                 │
│  logic/                Logical reasoning tasks                  │
│                        • Propositional logic                    │
│                        • Syllogism                              │
│                        • Knights and Knaves                     │
│                        • Self-reference                         │
│                        • Circuit logic                          │
│                        • Quantum lock                           │
│                                                                 │
│  [Additional domains: code, cognition, probability, induction,  │
│   algorithmic, arc, data, coaching, etc.]                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Example: Simple Equations Generator

```
┌─────────────────────────────────────────────────────────────────┐
│              Simple Equations Generator - Flow                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  __getitem__(idx: int)                                  │  │
│  │                                                          │  │
│  │  ┌─────────┐                                             │  │
│  │  │ Step 1: │                                             │  │
│  │  │ Initialize│ rng = Random(self.seed + idx)            │  │
│  │  └────┬────┘                                             │  │
│  │       │                                                  │  │
│  │  ┌────▼─────┐                                            │  │
│  │  │ Step 2:  │                                            │  │
│  │  │ Generate │ variable = random lowercase letter        │  │
│  │  │ term list│ (e.g., 'x')                               │  │
│  │  │ num_terms │ rng.randint(min_terms, max_terms)        │  │
│  │  └────┬─────┘                                            │  │
│  │       │                                                  │  │
│  │  ┌────▼─────┐                                            │  │
│  │  │ Step 3:  │                                            │  │
│  │  │ Replace  │ Pick random term, replace with variable   │  │
│  │  │ one term │ with coefficient * variable               │  │
│  │  └────┬─────┘                                            │  │
│  │       │                                                  │  │
│  │  ┌────▼─────┐                                            │  │
│  │  │ Step 4:  │                                            │  │
│  │  │ Apply ops│ Apply operators between terms            │  │
│  │  │ randomly │ +, -, * with weighted probabilities       │  │
│  │  └────┬─────┘                                            │  │
│  │       │                                                  │  │
│  │  ┌────▼─────┐                                            │  │
│  │  │ Step 5:  │                                            │  │
│  │  │ Generate │ Compute solution value                    │  │
│  │  │ solution │ random in [min_value, max_value]          │  │
│  │  └────┬─────┘                                            │  │
│  │       │                                                  │  │
│  │  ┌────▼─────┐                                            │  │
│  │  │ Step 6:  │                                            │  │
│  │  │ Format   │ Create equation string                    │  │
│  │  │ equation │ "left_side = right_side"                  │  │
│  │  └────┬─────┘                                            │  │
│  │       │                                                  │  │
│  │  ┌────▼─────┐                                            │  │
│  │  │ Step 7:  │                                            │  │
│  │  │ Return   │ {question, answer, metadata}              │  │
│  │  └─────────┘                                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. Evaluation Framework

### 9.1 Evaluation Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  Evaluation Pipeline                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Configuration Loading                                   │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  YAML/JSON Config                                  │  │  │
│  │  │  ├─ Model specification                            │  │  │
│  │  │  ├─ API provider & key                            │  │  │
│  │  │  ├─ Default dataset size & seed                   │  │  │
│  │  │  └─ Dataset list with parameters                  │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                     │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Dataset Generation                                      │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  For each dataset in config:                      │  │
│  │  │    1. Load dataset class from registry            │  │
│  │  │    2. Apply dataset-specific config               │  │
│  │  │    3. Generate 'size' tasks                       │  │
│  │  │    4. Store tasks for evaluation                  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                     │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Model Inference (Async)                                 │  │
│  │  ┌────────────────────────────────────────────────────┐  │
│  │  │  Concurrent API calls (max_concurrent limit)      │  │
│  │  │  ├─ Send prompt to API                            │  │
│  │  │  ├─ Receive generation                            │  │
│  │  │  └─ Store response                                │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                     │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Answer Scoring                                          │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  For each task:                                   │  │
│  │  │    1. Get score_answer_fn from metadata           │  │
│  │  │    2. Compare model response with oracle          │  │
│  │  │    3. Compute reward score [0,1]                  │  │
│  │  │    4. Store results                              │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                     │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Results Aggregation                                     │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  ├─ Per-dataset accuracy                          │  │
│  │  │  ├─ Overall statistics                            │  │
│  │  │  └─ Save to JSON files                             │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 9.2 Resume Capability

```
┌─────────────────────────────────────────────────────────────────┐
│                  Checkpoint & Resume System                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  After each dataset completes:                                  │
│  • Save checkpoint to: results/{model}_{timestamp}/             │
│  • Store:                                                      │
│    ├─ summary.json      - Aggregate statistics                  │
│    ├─ results.json      - Full results (if requested)           │
│    └─ {category}/       - Per-dataset results                   │
│                        └─ {dataset_name}.json                   │
│                                                                 │
│  On resume:                                                     │
│  • Load existing checkpoint                                    │
│  • Skip completed datasets                                     │
│  • Continue with remaining                                     │
│  • Produce identical final results                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 10. Training Integration

### 10.1 RL Training Integration

```
┌─────────────────────────────────────────────────────────────────┐
│                  RL Training Integration                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Training Loop (e.g., GRPO)                           │    │
│  │                                                        │    │
│  │  for step in num_steps:                               │    │
│  │      ┌────────────────────────────────────────────┐   │    │
│  │      │ 1. Sample training episode                 │   │    │
│  │      │    dataset = create_dataset("composite")   │   │    │
│  │      │    for entry in dataset[:episode_len]:     │   │    │
│  │      │        entry as training prompt            │   │    │
│  │      │                                          │   │    │
│  │      │ 2. Generate actor responses                 │   │    │
│  │      │    responses = actor(model, prompts)       │   │    │
│  │      │                                          │   │    │
│  │      │ 3. Compute rewards                          │   │    │
│  │      │    for entry, response in zip(entries,    │   │    │
│  │      │         responses):                        │   │    │
│  │      │        reward_fn = get_score_answer_fn(    │   │    │
│  │      │            entry["metadata"]["source_"]   │   │    │
│  │      │        reward = reward_fn(response,       │   │    │
│  │      │                          entry)           │   │    │
│  │      │                                          │   │    │
│  │      │ 4. Compute advantages & update weights     │   │    │
│  │      └────────────────────────────────────────────┘    │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
│  Key Features:                                                  │
│  • Dynamic dataset generation at runtime                       │
│  • Algorithmic verification as reward signal                   │
│  • Adjustable curriculum during training                       │
│  • Compatible with verl, FSDP, vLLM                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 10.2 HuggingFace Dataset Export

```
┌─────────────────────────────────────────────────────────────────┐
│                  HF Dataset Generation                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Script: scripts/hf_dataset/save_hf_dataset.py                  │
│                                                                 │
│  Process:                                                       │
│  1. Load dataset configuration from YAML                        │
│  2. Generate all dataset entries                               │
│  3. Convert to HuggingFace Dataset format                       │
│  4. Push to HuggingFace Hub (optional)                          │
│                                                                 │
│  Output columns:                                                │
│  ├─ question: str                                              │
│  ├─ answer: str                                                │
│  └─ metadata: dict (pandas JSON column)                        │
│                                                                 │
│  Usage:                                                         │
│  python save_hf_dataset.py                                    │
│    --config config.yaml                                        │
│    --output hf_dataset                                        │
│    --push_to_hub [optional]                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 11. Pseudocode and Algorithms

### 11.1 Dataset Generation Algorithm

```
FUNCTION create_dataset(name, config, seed, size):
    INPUT:
        name: string - dataset name from registry
        config: dict - configuration parameters
        seed: int - random seed for reproducibility
        size: int - number of items to generate

    OUTPUT:
        ProceduralDataset instance

    # 1. Look up dataset class from registry
    dataset_cls, config_cls = DATASETS[name]
    
    # 2. Create configuration object
    config_obj = config_cls(**config)
    
    # 3. Validate configuration
    IF hasattr(config_obj, "validate"):
        config_obj.validate()
    
    # 4. Create dataset instance
    RETURN dataset_cls(config=config_obj, seed=seed, size=size)


FUNCTION __getitem__(self, idx):
    # INPUT: self - ProceduralDataset, idx - item index
    # OUTPUT: dict with question, answer, metadata
    
    # 1. Create deterministic RNG for this index
    rng = Random(self.seed + idx)
    
    # 2. Generate task-specific content
    # (Implementation varies by dataset type)
    question, answer = self._generate_task(rng, idx)
    
    # 3. Extract domain-specific metadata
    difficulty = self._compute_difficulty(idx)
    source_dataset = self.category
    
    # 4. Return structured entry
    RETURN {
        "question": question,
        "answer": answer,
        "metadata": {
            "source_dataset": source_dataset,
            "source_index": idx,
            "difficulty": difficulty,
            # ... additional metadata
        }
    }
```

### 11.2 Weighted Sampling Algorithm

```
FUNCTION __getitem__(self, idx):
    # CompositeDataset implementation
    # Returns item from appropriately weighted sub-dataset
    
    # 1. Create deterministic RNG for reproducibility
    rng = Random(self.seed + idx)
    
    # 2. Sample dataset index based on weights
    n_datasets = len(self.dataset_names)
    dataset_idx = rng.choices(
        range(n_datasets),
        weights=self.weights,
        k=1
    )[0]
    
    # 3. Get target dataset name
    dataset_name = self.dataset_names[dataset_idx]
    dataset = self.datasets[dataset_name]
    
    # 4. Retrieve item from sub-dataset
    item = dataset[idx]
    
    # 5. Add composite metadata
    IF self.version_manager:
        item["metadata"]["version_id"] = self.dataset_versions[dataset_name]
        item["metadata"]["entry_id"] = f"{self.dataset_versions[dataset_name]}.{idx}"
    
    RETURN item
```

### 11.3 Curriculum Progression Algorithm

```
FUNCTION increment_curriculum(dataset, global_level=1):
    # Progressive difficulty scaling
    curriculum = dataset.config.dataset_class.get_curriculum()
    
    # Set global level or use existing state
    curriculum.set_global_level(global_level)
    
    # Generate configuration at current levels
    config = curriculum.generate_configuration(
        defaults=dataset.config.__dict__
    )
    
    # Create new dataset with updated config
    new_dataset = dataset.config.dataset_class(
        config=config,
        seed=dataset.seed,
        size=dataset.size
    )
    
    RETURN new_dataset


FUNCTION get_progression_config(curriculum, level):
    # Get configuration for specific curriculum level
    # level: integer curriculum level
    
    # 1. Validate level
    max_level = curriculum.get_max_level()
    level = min(max(level, 0), max_level)
    
    # 2. Create context for level transition
    context = DefaultCurriculumContext(mode=RangeAttributeMode.INCLUSIVE)
    
    # 3. Generate configuration at current level
    config = curriculum.generate_configuration(context=context)
    
    RETURN config
```

### 11.4 Answer Scoring Algorithm

```
FUNCTION score_answer(dataset, model_answer, entry):
    # Verify model answer against oracle
    # Returns reward in [0, 1]
    
    # 1. Get or create score function for dataset type
    source = entry["metadata"]["source_dataset"]
    score_fn = DATASETS[source][0].get_score_answer_fn()
    
    # 2. Compute reward based on answer match
    reward = 0.0
    
    ORACLE_ANSWER = entry["answer"]
    
    # Standard exact match
    IF model_answer == ORACLE_ANSWER:
        reward = 1.0
    # Partial credit for substring match
    ELIF ORACLE_ANSWER in model_answer:
        reward = len(ORACLE_ANSWER) / len(model_answer)
    # Multi-solution handling (dataset-specific)
    ELIF dataset.has_multiple_solutions():
        reward = dataset.evaluate_multi_solution(
            model_answer, entry
        )
    
    RETURN max(0.0, min(1.0, reward))  # Clamp to [0, 1]


FUNCTION evaluate_multi_solution(dataset, model_answer, entry):
    # For datasets with multiple correct answers
    valid_solutions = dataset.generate_all_valid_answers(entry)
    
    # Check if answer matches any valid solution
    best_match = 0.0
    FOR solution IN valid_solutions:
        # Compute match quality
        match = compute_answer_match(model_answer, solution)
        best_match = max(best_match, match)
    
    RETURN best_match
```

---

## 12. Flowcharts and Sequence Diagrams

### 12.1 Dataset Creation Sequence Diagram

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   User       │     │   factory.py │     │ Registry     │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       │ create_dataset("x")│                    │
       │────────────────────▶│                    │
       │                    │                    │
       │                    │ Lookup in DATASETS│
       │                    │────────────────────▶│
       │                    │                    │
       │                    │                    │ Found
       │                    │                    │
       │                    │                    │
       │                    │ Create config      │
       │                    │────────────────────▶│
       │                    │                    │
       │                    │                    │ Validate
       │                    │                    │
       │                    │                    │
       │                    │ Instantiate class  │
       │                    │────────────────────▶│
       │                    │                    │
       │                    │                    │
       │                    │<───────────────────│
       │                    │                    │
       │ Dataset Instance   │                    │
       │◀───────────────────│                    │
       │                    │                    │
```

### 12.2 Evaluation Pipeline Sequence Diagram

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Config       │     │   Evaluator  │     │   API Server │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       │ Load config        │                    │
       │────────────────────▶│                    │
       │                    │                    │
       │                    │ Generate datasets  │
       │                    │────────────────────▶│
       │                    │                    │
       │                    │                    │
       │                    │ For each task:     │
       │                    │                    │
       │                    │                    │
       │                    │ Send prompt        │
       │                    │────────────────────▶│
       │                    │                    │
       │                    │                    │ Process
       │                    │                    │
       │                    │                    │
       │                    │                    │
       │                    │<───────────────────│ Response
       │                    │                    │
       │                    │                    │
       │                    │ Score answer       │
       │                    │<───────────────────│
       │                    │
       │                    │ Aggregate results
       │                    │
       │                    │
       │ Results JSON       │
       │◀───────────────────│
       │
```

### 12.3 RL Training Loop Sequence Diagram

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Model      │     │  Reasoning   │     │  Verifier    │
└──────┬───────┘     │    Gym       │     └──────┬───────┘
       │             └──────┬───────┘            │
       │                    │                    │
       │ Generate responses │                    │
       │────────────────────▶│                    │
       │                    │                    │
       │                    │ Sample tasks       │
       │                    │────────────────────▶│
       │                    │                    │
       │                    │                    │
       │                    │                    │
       │                    │ Generate questions │
       │                    │────────────────────▶│
       │                    │                    │
       │                    │                    │
       │                    │                    │
       │                    │<───────────────────│ Task
       │                    │                    │
       │                    │                    │
       │                    │                    │
       │                    │<───────────────────│ Score
       │                    │ (answer, task)     │
       │                    │                    │
       │                    │                    │
       │ Advantages &       │                    │
       │ Updates            │                    │
       │◀───────────────────│                    │
       │                    │                    │
```

---

## 13. Usage Examples

### 13.1 Basic Usage

```python
# Create a simple dataset
import reasoning_gym

# Generate 10 leg counting tasks
data = reasoning_gym.create_dataset('leg_counting', size=10, seed=42)

# Iterate through tasks
for i, entry in enumerate(data):
    print(f"Task {i}:")
    print(f"  Question: {entry['question']}")
    print(f"  Answer: {entry['answer']}")
    print(f"  Metadata: {entry['metadata']}")
    
    # Verify answer using algorithmic scoring
    score = data.score_answer(entry['answer'], entry)
    assert score == 1.0

# Output example:
# Task 0:
#   Question: How many legs are there in total if you have 1 sea slug, 1 deer?
#   Answer: 4
#   Metadata: {'animals': {'sea slug': 1, 'deer': 1}, 'total_legs': 4}
```

### 13.2 Composite Datasets

```python
from reasoning_gym.composite import DatasetSpec

# Create weighted composite dataset
specs = [
    DatasetSpec(name='leg_counting', weight=2, config={}),  # 2/3 weight
    DatasetSpec(name='figlet_font', weight=1, config={
        "min_word_len": 4,
        "max_word_len": 6
    }),  # 1/3 weight
]

dataset = reasoning_gym.create_dataset('composite', size=10, seed=42, datasets=specs)

# Each item will have source_dataset metadata indicating origin
for entry in dataset:
    print(entry['metadata']['source_dataset'])  # 'leg_counting' or 'figlet_font'
```

### 13.3 Curriculum Learning

```python
# Create dataset with curriculum
dataset = reasoning_gym.create_dataset('simple_equations', size=500, seed=42)

# Get the curriculum
curriculum = reasoning_gym.create_curriculum('simple_equations')

# Start at level 0 (easiest)
curriculum.set_global_level(0)

# Progress through levels
for level in range(4):
    config = curriculum.generate_configuration()
    new_dataset = reasoning_gym.create_dataset(
        'simple_equations',
        size=100,
        seed=42,
        **config.__dict__
    )
    
    print(f"Level {level}:")
    print(f"  Config: {config.__dict__}")
    
    # Or use incremental approach
    if level > 0:
        curriculum.increment_global_level()

# Increment specific attribute
curriculum.set_attr_level('min_terms', 2)
curriculum.increment_attr_level('min_terms')  # Now min_terms = 3
```

### 13.4 Model Evaluation

```python
from reasoning_gym import get_score_answer_fn

# Generate evaluation dataset
dataset = reasoning_gym.create_dataset('simple_equations', size=100, seed=42)

# Generate model responses (simulated)
model_responses = [
    "4", "12", "6", "10", "15"  # Example responses
]

# Evaluate responses
scores = []
for entry, response in zip(dataset, model_responses):
    # Get scoring function from metadata
    score_fn = get_score_answer_fn(
        entry['metadata']['source_dataset']
    )
    
    # Compute reward
    score = score_fn(response, entry)
    scores.append(score)
    
    print(f"Response: {response}, Score: {score}")

# Average accuracy
avg_score = sum(scores) / len(scores)
print(f"Average accuracy: {avg_score:.2%}")
```

### 13.5 Training with verl

```python
# Example verl training configuration
# configs/inter_generalisation/algorithmic_qwen_3b.yaml

training:
  actor_rollout_ref:
    actor:
      model: qwen/Qwen2.5-3B-Instruct
      load_in_4bit: false
      use_flash_attention_2: true
      dtype: "float16"
      device: "cuda:0"
    
    rollout:
      engine:
        engine_type: vllm
        vllm:
          tensor_model_parallel_size: 2
          dtype: "float16"
          max_model_len: 8192
          gpu_memory_utilization: 0.9
          enforce_eager: false
          max_num_batched_tokens: 65536

  trainer:
    algorithm: grpo
    grpo:
      batch_size: 256
      mini_batch_size: 32
      gradient_accumulation_steps: 8
      max_epochs: 3
      learning_rate: 3e-7
      clip_range: 0.2
      gamma: 0.99
      lora_rank: 64
      lora_alpha: 128
      ema_beta: 0.992
```

---

## 14. Technical Specifications

### 14.1 Supported Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                      Required Dependencies                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Core:                                                          │
│  • Python >= 3.10                                              │
│  • dataclasses                                                 │
│  • sympy >= 1.13.1 (symbolic math)                             │
│                                                                 │
│  Domain-Specific:                                               │
│  • cellpylib == 2.4.0 (cellular automata)                      │
│  • magiccube == 0.3.0 (Rubik's cube)                           │
│  • pycosat == 0.6.6 (SAT solving)                              │
│  • arckit == 0.1.0 (ARC tasks)                                 │
│  • zss >= 1.2.0 (string diff)                                  │
│  • bfi == 1.0.4 (binary file I/O)                              │
│                                                                 │
│  Optional (for features):                                      │
│  • pyfiglet == 1.0.2 (text fonts)                              │
│  • pytz >= 2024.1 (timezone handling)                          │
│  • tabulate == 0.9.0 (table formatting)                        │
│                                                                 │
│  Development:                                                   │
│  • pytest >= 7.0.0                                             │
│  • pytest-cov >= 4.0.0                                         │
│  • httpx >= 0.27.0 (HTTP testing)                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 14.2 Performance Characteristics

```
┌─────────────────────────────────────────────────────────────────┐
│                   Performance Metrics                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Generation Speed:                                              │
│  • ~1000 tasks/second (CPU-only)                               │
│  • ~5000 tasks/second (with batching)                          │
│                                                                 │
│  Memory Usage:                                                  │
│  • < 100MB for single dataset                                  │
│  • O(n) for composite with n datasets                          │
│  • Streaming supported (doesn't load all into memory)          │
│                                                                 │
│  Verification Speed:                                            │
│  • O(1) for exact match                                         │
│  • O(k) for k possible solutions                                │
│  • Symbolic verification: ~1ms per task                        │
│                                                                 │
│  Infinite Generation:                                           │
│  • ReseedingDataset provides unbounded iteration               │
│  • Deterministic within seed boundaries                        │
│  • Chunk-based for memory efficiency                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 15. Complete System Flow

### 15.1 End-to-End Data Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Complete Data Pipeline                               │
└─────────────────────────────────────────────────────────────────────────────┘

Step 1: Configuration
  ├─ User defines dataset config (YAML/Python)
  ├─ Specifies weights for composite datasets
  └─ Sets training/evaluation parameters

Step 2: Dataset Registration
  ├─ Modules import dataset classes
  ├─ register_dataset() called automatically
  └─ Global DATASETS registry populated

Step 3: Generation
  ├─ create_dataset() looks up class from registry
  ├─ Validates configuration
  ├─ Instantiates ProceduralDataset subclass
  └─ Seeds RNG for reproducibility

Step 4: Task Generation
  ├─ __getitem__(idx) creates deterministic RNG
  ├─ Generates problem based on config
  ├─ Computes oracle answer
  ├─ Extracts metadata
  └─ Returns structured entry

Step 5: Scoring Setup
  ├─ get_score_answer_fn() retrieves scoring function
  ├─ Returns lambda that calls dataset.score_answer
  └─ Bound to specific dataset instance

Step 6: Training/Evaluation
  ├─ RL agent generates responses
  ├─ Responses passed to scoring function
  ├─ Reward computed in [0,1]
  └─ Used for gradient updates

Step 7: Curriculum Progression
  ├─ Track performance across episodes
  ├─ Increment curriculum levels
  ├─ Generate harder problems
  └─ Continue progressive training
```

---

## 16. Best Practices

### 16.1 Creating New Datasets

```python
"""
Creating a new Reasoning Gym dataset:

1. Create domain module directory
   reasoning_gym/your_domain/

2. Implement configuration class
   @dataclass
   class YourConfig:
       min_difficulty: int = 1
       max_difficulty: int = 10
       
       def validate(self):
           assert self.min_difficulty >= 1

3. Implement dataset class
   class YourDataset(ProceduralDataset):
       def __getitem__(self, idx):
           # Generate problem
           # Compute answer
           # Return {question, answer, metadata}

4. Implement scoring (if needed)
   def score_answer(self, answer, entry):
       # Handle multiple solutions if needed

5. Define curriculum (optional)
   class YourCurriculum(BaseCurriculum):
       def __init__(self):
           self._define_attributes(...)

6. Register the dataset
   register_dataset("your_dataset", YourDataset, YourConfig)

7. Write comprehensive tests
   tests/test_your_dataset.py
"""
```

### 16.2 Common Patterns

```python
# Pattern 1: Simple exact-answer dataset
class SimpleDataset(ProceduralDataset):
    def __getitem__(self, idx):
        rng = Random(self.seed + idx)
        answer = self._compute_answer(rng)
        return {"question": self._generate_question(answer),
                "answer": str(answer),
                "metadata": {...}}
    
    def score_answer(self, answer, entry):
        return 1.0 if answer == entry["answer"] else 0.0

# Pattern 2: Multiple correct answers
class MultiSolutionDataset(ProceduralDataset):
    def __getitem__(self, idx):
        ...
        valid_solutions = self._generate_all_solutions(rng)
        selected = rng.choice(valid_solutions)
        ...
    
    def score_answer(self, answer, entry):
        valid = self._generate_all_solutions_from_metadata(entry)
        for sol in valid:
            if self._check_partial(answer, sol):
                return 0.5  # Partial credit
        return 0.0

# Pattern 3: Procedural verification
class VerifiedDataset(ProceduralDataset):
    def __getitem__(self, idx):
        ...
        state = self._initial_state(rng)
        solution = self._generate_solution(rng)
        final = self._apply_solution(state, solution)
        ...
    
    def score_answer(self, answer, entry):
        state = self._initial_state_from_metadata(entry)
        result = self._apply_solution(state, answer)
        return 1.0 if result == self._winning_state() else 0.0
```

---

## 17. Troubleshooting

### 17.1 Common Issues

```
Issue: "Dataset 'X' not registered"
Solution: Ensure domain module is imported before calling create_dataset()
  import reasoning_gym.algebra  # Import specific domain
  or
  from reasoning_gym import algebra  # Import specific module

Issue: "Config class must be a dataclass"
Solution: Add @dataclass decorator to config class

Issue: "No curriculum registered"
Solution: Dataset needs BaseCurriculum subclass registered

Issue: Non-deterministic results
Solution: Always set seed parameter for reproducibility

Issue: Invalid answer scores
Solution: Check that score_answer returns float in [0, 1]
```

---

## 18. References

### 18.1 Key Files

```
reasoning_gym/
├── factory.py              # Dataset registration
├── dataset.py              # Base classes
├── composite.py            # Composite datasets
├── coaching/               # Curriculum learning
│   └── base_curriculum.py  # Curriculum implementation
└── [domain]/               # Domain-specific datasets
    └── __init__.py         # Registration points
```

### 18.2 Resources

- Paper: [REASONING GYM: Reasoning Environments for Reinforcement Learning with Verifiable Rewards](https://arxiv.org/abs/2505.24760)
- GitHub: [https://github.com/open-thought/reasoning-gym](https://github.com/open-thought/reasoning-gym)
- Evaluation Repo: [https://github.com/open-thought/reasoning-gym-eval](https://github.com/open-thought/reasoning-gym-eval)
- Discord: [GPU-Mode Server](https://discord.gg/gpumode)

---

*This documentation was generated through comprehensive analysis of the reasoning-gym repository.*
"""
Core module for LLM Architecture Duplication Research.
Contains the main layer duplication logic and experiment execution.
"""

from .layer_duplicator import LayerDuplicator
from .experiment_runner import ExperimentRunner
from .metric_collector import MetricCollector
from .resource_manager import ResourceManager

__all__ = [
    'LayerDuplicator',
    'ExperimentRunner',
    'MetricCollector',
    'ResourceManager'
]

__version__ = '0.1.0'
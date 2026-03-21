"""Applicationâ€wide configuration.

All runtime configuration is now loaded from :file:`repo_config.yaml` located in the
repository root. The file is parsed once at import time and the resulting values
populate a set of constants that other modules import.

The module keeps a small fallback dictionary for unit tests that may run in an
environment where the YAML file is absent.  The defaults match the historic
hardâ€coded values from the original code base.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Tuple

# ---------------------------------------------------------------------------
#  Load configuration from YAML
# ---------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

# Path to repo_config.yaml â€” three levels up from this file
_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "repo_config.yaml"

try:
    import yaml
except Exception:  # pragma: no cover â€” yaml is a normal dependency
    _LOGGER.warning("PyYAML not available â€” using empty config")
    yaml = None


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:  # pragma: no cover
        _LOGGER.warning("Failed to load %s: %s", path, exc)
        return {}

# Default values that mimic the historic hardâ€coded constants.
_DEFAULTS: Dict[str, Any] = {
    "SERVER_URL": "http://localhost:8000",
    "MODEL_NAME": "unsloth/gpt-oss-20b-GGUF:F16",
    "DEFAULT_SYSTEM_PROMPT": "You are a helpful assistant.",
    "user_name": "ghghang2",
    "repo_name": "v1.4",
    "context_len": 16384,
    "tail_len": 2,
    "max_tool_output_chars": 6000,
    "compress_threshold_chars": 8000,
    "email_login": "ghghang2@gmail.com",
    "email_to": "ghghang2@gmail.com",
    "max_history_turns": 10,
    "window_turns": 8,
    "max_window_rows": 30,
    "max_exchanges": 50,
    "keep_recent_exchanges": 30,
    "port": 8000,
    "n_parallel": 1,
    "ctx_size": 16384,
    "n_gpu_layers": 999,
    "service_info_path": "service_info.json",
    "llama_log_path": "llama_server.log",
    "IGNORED_ITEMS": [
        ".*",
        "sample_data",
        "llama-server",
        "__pycache__",
        "*.log",
        "*.yml",
        "*.json",
        "*.out",
    ],
    "SUMMARY_PROMPT": "Write a detailed summary of the conversation above.",
    "max_tool_turns": 100,
    "stall_turns": 3,
    # L2 Episodic Store constants
    "L2_WRITE_THRESHOLD": 2.0,
    "L2_RETRIEVAL_LIMIT": 5,
    "L2_MIN_IMPORTANCE_FOR_RETRIEVAL": 3.0,
    # Core memory constants
    "CORE_MEMORY_ACTIVE_ENTITIES_LIMIT": 20,
    "CORE_MEMORY_ERROR_HISTORY_LIMIT": 5,
    # Summarizer constants
    "SUMMARIZER_TOOL_CHARS": 2000,
    # Correction keywords
    "_CORRECTION_KEYWORDS": (
        "actually", "wait,", "no,", "wrong", "instead", "correct",
        "not that", "stop,", "that's not", "don't do", "undo",
    ),
    # Structured summary prompt
    "_STRUCTURED_SUMMARY_PROMPT": (
        "Analyse this conversation segment and output EXACTLY three labelled lines.\n"
        "GOAL: <one sentence â€” what the user was trying to accomplish in this segment>\n"
        "ENTITIES: <pipe-separated entity state changes, e.g. "
        "'file:report.py created | api:/users â†’ 404 | task:login done'. "
        "Use 'none' if there are no meaningful entity changes.>\n"
        "RATIONALE: <one sentence â€” the key action taken and whether it achieved "
        "the expected outcome>\n"
        "Be factual and concrete. Output exactly three lines with the exact labels "
        "GOAL:, ENTITIES:, RATIONALE: â€” no preamble, no extra lines."
    ),
}

_cfg: Dict[str, Any] = _load_yaml(_CONFIG_PATH)
_cfg = {**_DEFAULTS, **_cfg}

# ---------------------------------------------------------------------------
#  Public constants â€” exported for import by other modules.
# ---------------------------------------------------------------------------
SERVER_URL: str = str(_cfg["SERVER_URL"])
MODEL_NAME: str = str(_cfg["MODEL_NAME"])
DEFAULT_SYSTEM_PROMPT: str = str(_cfg["DEFAULT_SYSTEM_PROMPT"])

USER_NAME: str = str(_cfg["user_name"])
REPO_NAME: str = str(_cfg["repo_name"])
CONTEXT_TOKEN_THRESHOLD: int = int(_cfg["context_len"])
TAIL_MESSAGES: int = int(_cfg["tail_len"])
MAX_TOOL_OUTPUT_CHARS: int = int(_cfg["max_tool_output_chars"])
MAX_HISTORY_TURNS: int = int(_cfg["max_history_turns"])

# Context management constants
WINDOW_TURNS: int = int(_cfg["window_turns"])
MAX_WINDOW_ROWS: int = int(_cfg["max_window_rows"])
MAX_EXCHANGES: int = int(_cfg["max_exchanges"])
KEEP_RECENT_EXCHANGES: int = int(_cfg["keep_recent_exchanges"])

# L2 Episodic Store constants
L2_WRITE_THRESHOLD: float = float(_cfg["L2_WRITE_THRESHOLD"])
L2_RETRIEVAL_LIMIT: int = int(_cfg["L2_RETRIEVAL_LIMIT"])
L2_MIN_IMPORTANCE_FOR_RETRIEVAL: float = float(_cfg["L2_MIN_IMPORTANCE_FOR_RETRIEVAL"])

# Core memory constants
CORE_MEMORY_ACTIVE_ENTITIES_LIMIT: int = int(_cfg["CORE_MEMORY_ACTIVE_ENTITIES_LIMIT"])
CORE_MEMORY_ERROR_HISTORY_LIMIT: int = int(_cfg["CORE_MEMORY_ERROR_HISTORY_LIMIT"])

# Summarizer constants
SUMMARIZER_TOOL_CHARS: int = int(_cfg["SUMMARIZER_TOOL_CHARS"])
_SUMMARIZER_TOOL_CHARS: int = SUMMARIZER_TOOL_CHARS

# Correction keywords
_CORRECTION_KEYWORDS: Tuple[str, ...] = tuple(_cfg.get("_CORRECTION_KEYWORDS", _DEFAULTS["_CORRECTION_KEYWORDS"]))

# Structured summary prompt
_STRUCTURED_SUMMARY_PROMPT: str = str(_cfg.get("_STRUCTURED_SUMMARY_PROMPT", _DEFAULTS["_STRUCTURED_SUMMARY_PROMPT"]))

# Conversation loop constants
MAX_TOOL_TURNS: int = int(_cfg["max_tool_turns"])
STALL_TURNS: int = int(_cfg["stall_turns"])

PORT: int = int(_cfg["port"])
N_PARALLEL: int = int(_cfg["n_parallel"])
CTX_SIZE: int = int(_cfg["ctx_size"])
N_GPU_LAYERS: int = int(_cfg["n_gpu_layers"])
SERVICE_INFO_PATH: str = str(_cfg["service_info_path"])
LLAMA_LOG_PATH: str = str(_cfg["llama_log_path"])

IGNORED_ITEMS: list[str] = list(_cfg["IGNORED_ITEMS"])

SUMMARY_PROMPT: str = str(_cfg["SUMMARY_PROMPT"])

__all__ = [
    "SERVER_URL",
    "MODEL_NAME",
    "DEFAULT_SYSTEM_PROMPT",
    "USER_NAME",
    "REPO_NAME",
    "CONTEXT_TOKEN_THRESHOLD",
    "TAIL_MESSAGES",
    "MAX_TOOL_OUTPUT_CHARS",
    "MAX_HISTORY_TURNS",
    "WINDOW_TURNS",
    "MAX_WINDOW_ROWS",
    "MAX_EXCHANGES",
    "KEEP_RECENT_EXCHANGES",
    "L2_WRITE_THRESHOLD",
    "L2_RETRIEVAL_LIMIT",
    "L2_MIN_IMPORTANCE_FOR_RETRIEVAL",
    "CORE_MEMORY_ACTIVE_ENTITIES_LIMIT",
    "CORE_MEMORY_ERROR_HISTORY_LIMIT",
    "SUMMARIZER_TOOL_CHARS",
    "_SUMMARIZER_TOOL_CHARS",
    "_CORRECTION_KEYWORDS",
    "_STRUCTURED_SUMMARY_PROMPT",
    "MAX_TOOL_TURNS",
    "STALL_TURNS",
    "PORT",
    "N_PARALLEL",
    "CTX_SIZE",
    "N_GPU_LAYERS",
    "SERVICE_INFO_PATH",
    "LLAMA_LOG_PATH",
    "IGNORED_ITEMS",
    "SUMMARY_PROMPT",
]

# ---------------------------------------------------------------------------
#  End of module
# ---------------------------------------------------------------------------
# L2 retrieval and context management
L2_WRITE_THRESHOLD: float = float(_cfg["l2_write_threshold"])
L2_RETRIEVAL_LIMIT: int = int(_cfg["l2_retrieval_limit"])
L2_MIN_IMPORTANCE_FOR_RETRIEVAL: float = float(_cfg["l2_min_importance_for_retrieval"])
CORE_MEMORY_ACTIVE_ENTITIES_LIMIT: int = int(_cfg["core_memory_active_entities_limit"])
CORE_MEMORY_ERROR_HISTORY_LIMIT: int = int(_cfg["core_memory_error_history_limit"])
SUMMARIZER_TOOL_CHARS: int = int(_cfg["summarizer_tool_chars"])

# Compression parameters
LOSSLESS_WINDOW: int = int(_cfg["lossless_window"])

# Retry parameters
DEFAULT_MAX_RETRIES: int = int(_cfg["max_retries"])
DEFAULT_INITIAL_DELAY: float = float(_cfg["initial_delay"])
DEFAULT_MAX_DELAY: float = float(_cfg["max_delay"])
DEFAULT_BACKOFF_MULTIPLIER: float = float(_cfg["backoff_multiplier"])

# Monitoring thresholds
_LOG_TAIL_BYTES: int = int(_cfg["log_tail_bytes"])
_REREAD_RATE_THRESHOLD: float = float(_cfg["reread_rate_threshold"])
_ERROR_COMPRESSION_THRESHOLD: float = float(_cfg["error_compression_threshold"])
_LLM_FAILURE_THRESHOLD: float = float(_cfg["llm_failure_threshold"])
_NO_OUTPUT_THRESHOLD: float = float(_cfg["no_output_threshold"])
_POOR_RATIO_THRESHOLD: float = float(_cfg["poor_ratio_threshold"])
_LOW_SIM_THRESHOLD: float = float(_cfg["low_sim_threshold"])
_HIGH_INVALIDATION_THRESHOLD: float = float(_cfg["high_invalidation_threshold"])

# Email parameters
SMTP_PORT: int = int(_cfg["smtp_port"])

# UI parameters
MAX_VISIBLE_WIDGETS: int = int(_cfg["max_visible_widgets"])

# Timeout parameters (in seconds)
BROWSER_TIMEOUT: int = int(_cfg["browser_timeout"])
TESTS_TIMEOUT: int = int(_cfg["tests_timeout"])
OTHER_TOOLS_TIMEOUT: int = int(_cfg["other_tools_timeout"])

# Browser default parameters (in milliseconds)
DEFAULT_NAVIGATION_TIMEOUT: int = int(_cfg["default_navigation_timeout"])
DEFAULT_ACTION_TIMEOUT: int = int(_cfg["default_action_timeout"])
DEFAULT_MAX_CONTENT_LENGTH: int = int(_cfg["default_max_content_length"])

__all__ = [
    # Existing exports
    "SERVER_URL",
    "MODEL_NAME",
    "DEFAULT_SYSTEM_PROMPT",
    "USER_NAME",
    "REPO_NAME",
    "CONTEXT_TOKEN_THRESHOLD",
    "TAIL_MESSAGES",
    "MAX_TOOL_OUTPUT_CHARS",
    "MAX_HISTORY_TURNS",
    "WINDOW_TURNS",
    "MAX_WINDOW_ROWS",
    "MAX_EXCHANGES",
    "KEEP_RECENT_EXCHANGES",
    "MAX_TOOL_TURNS",
    "STALL_TURNS",
    "PORT",
    "N_PARALLEL",
    "CTX_SIZE",
    "N_GPU_LAYERS",
    "SERVICE_INFO_PATH",
    "LLAMA_LOG_PATH",
    "IGNORED_ITEMS",
    "SUMMARY_PROMPT",
    # L2 retrieval and context management
    "L2_WRITE_THRESHOLD",
    "L2_RETRIEVAL_LIMIT",
    "L2_MIN_IMPORTANCE_FOR_RETRIEVAL",
    "CORE_MEMORY_ACTIVE_ENTITIES_LIMIT",
    "CORE_MEMORY_ERROR_HISTORY_LIMIT",
    "SUMMARIZER_TOOL_CHARS",
    # Compression parameters
    "LOSSLESS_WINDOW",
    # Retry parameters
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_INITIAL_DELAY",
    "DEFAULT_MAX_DELAY",
    "DEFAULT_BACKOFF_MULTIPLIER",
    # Monitoring thresholds
    "_LOG_TAIL_BYTES",
    "_REREAD_RATE_THRESHOLD",
    "_ERROR_COMPRESSION_THRESHOLD",
    "_LLM_FAILURE_THRESHOLD",
    "_NO_OUTPUT_THRESHOLD",
    "_POOR_RATIO_THRESHOLD",
    "_LOW_SIM_THRESHOLD",
    "_HIGH_INVALIDATION_THRESHOLD",
    # Email parameters
    "SMTP_PORT",
    # UI parameters
    "MAX_VISIBLE_WIDGETS",
    # Timeout parameters
    "BROWSER_TIMEOUT",
    "TESTS_TIMEOUT",
    "OTHER_TOOLS_TIMEOUT",
    # Browser default parameters
    "DEFAULT_NAVIGATION_TIMEOUT",
    "DEFAULT_ACTION_TIMEOUT",
    "DEFAULT_MAX_CONTENT_LENGTH",
]
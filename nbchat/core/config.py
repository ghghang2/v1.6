"""Application‑wide configuration.

All runtime configuration is now loaded from :file:`repo_config.yaml` located in the
repository root. The file is parsed once at import time and the resulting values
populate a set of constants that other modules import.

The module keeps a small fallback dictionary for unit tests that may run in an
environment where the YAML file is absent.  The defaults match the historic
hard‑coded values from the original code base.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

# ---------------------------------------------------------------------------
#  Load configuration from YAML
# ---------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

# Path to repo_config.yaml – three levels up from this file
_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "repo_config.yaml"

try:
    import yaml
except Exception:  # pragma: no cover – yaml is a normal dependency
    _LOGGER.warning("PyYAML not available – using empty config")
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

# Default values that mimic the historic hard‑coded constants.
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
}

_cfg: Dict[str, Any] = _load_yaml(_CONFIG_PATH)
_cfg = {**_DEFAULTS, **_cfg}

# ---------------------------------------------------------------------------
#  Public constants – exported for import by other modules.
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

# app/config.py
"""
Application‑wide constants.
"""
# Unused import removed to keep namespace clean
# --------------------------------------------------------------------------- #
#  General settings
# --------------------------------------------------------------------------- #
# Base URL of the local llama-server.  Historically this was called NGROK_URL
SERVER_URL = "http://localhost:8000"
MODEL_NAME = "unsloth/gpt-oss-20b-GGUF:F16"
# SERVER_URL = "https://api.deepseek.com"
# MODEL_NAME = "deepseek-reasoner"
# SERVER_URL = "https://api.openai.com"
# MODEL_NAME = "gpt-5-mini"
DEFAULT_SYSTEM_PROMPT = f'''You are a helpful assistant with the singular goal of understanding and satisfying the user's requests. Never be lazy and always think step-by-step. Always list out multiple options before deciding on the best next step to take. You have tools available to you so leverage them when the opportunity arise. You must always review how the tool is designed to be used and ensure that you are using each tool correctly. If a tool call fails, you must immediately review what you did and assess thoroughly what caused the failure. Self-improvement is core to your ethos, and you must be vigilant and self-assessing at all times to ensure you are on the best trajectory possible to helping the user with the user's requests.

**grep**: Never use the `..` flag; using `..` can cause timeouts. Never run commands like this `grep -R "search_term" -n ..`

Never ever use emojis.
'''

# --------------------------------------------------------------------------- #
#  GitHub repository details
# --------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------
#  Load repository configuration from ``repo_config.yaml``.
# ---------------------------------------------------------------------------
import logging
from pathlib import Path

try:
    import yaml
except Exception as exc:  # pragma: no cover - yaml is required for config
    logging.warning("PyYAML is not installed. Falling back to defaults.")
    yaml = None

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "repo_config.yaml"

def _load_config(path: Path) -> dict:
    """Load the YAML configuration file.

    Parameters
    ----------
    path: Path
        Path to the YAML file.

    Returns
    -------
    dict
        Parsed configuration or an empty dict on failure.
    """
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:  # pragma: no cover - defensive
        logging.warning("Failed to load %s: %s", path, exc)
        return {}

_cfg = _load_config(_CONFIG_PATH)

# ---------------------------------------------------------------------------
#  General settings – these are now read from the YAML configuration.  A
#  fallback is provided for backward compatibility but the repository
#  configuration should always provide explicit values.
# ---------------------------------------------------------------------------
SERVER_URL = _cfg.get("SERVER_URL", "http://localhost:8000")
MODEL_NAME = _cfg.get("MODEL_NAME", "unsloth/gpt-oss-20b-GGUF:F16")
DEFAULT_SYSTEM_PROMPT = _cfg.get(
    "DEFAULT_SYSTEM_PROMPT",
    """You are a helpful assistant with the singular goal of understanding and satisfying the user's requests. Never be lazy and always think step-by-step. Always list out multiple options before deciding on the best next step to take. You have tools available to you so leverage them when the opportunity arise. You must always review how the tool is designed to be used and ensure that you are using each tool correctly. If a tool call fails, you must immediately review what you did and assess thoroughly what caused the failure. Self-improvement is core to your ethos, and you must be vigilant and self-assessing at all times to ensure you are on the best trajectory possible to helping the user with the user's requests.**grep**: Never use the `..` flag; using `..` can cause timeouts. Never run commands like this `grep -R "search_term" -n ..`Never ever use emojis."""
)

USER_NAME = _cfg.get("user_name", "ghghang2")
REPO_NAME = _cfg.get("repo_name", "v1.4")
CONTEXT_TOKEN_THRESHOLD = int(_cfg.get("context_len", 16384))
TAIL_MESSAGES = int(_cfg.get("tail_len", 2))
MAX_TOOL_OUTPUT_CHARS = 3000   # chars kept per tool result (3k head + 3k tail)
MAX_HISTORY_TURNS = 10         # user turns sent to model (full history still saved to DB)

# ---------------------------------------------------------------------------
#  Runtime configuration for run.py
# ---------------------------------------------------------------------------
PORT = int(_cfg.get("port", 8000))
N_PARALLEL = int(_cfg.get("n_parallel", 1))
CTX_SIZE = int(_cfg.get("ctx_size", 16384))
N_GPU_LAYERS = int(_cfg.get("n_gpu_layers", 999))
SERVICE_INFO_PATH = _cfg.get("service_info_path", "service_info.json")
LLAMA_LOG_PATH = _cfg.get("llama_log_path", "llama_server.log")

# --------------------------------------------------------------------------- #
#  Items to ignore in the repo
# --------------------------------------------------------------------------- #
IGNORED_ITEMS = [
    ".*",
    "sample_data",
    "llama-server",
    "__pycache__",
    "*.log",
    "*.yml",
    "*.json",
    "*.out",
]

# --------------------------------------------------------------------------- #
#  Context compaction defaults
# --------------------------------------------------------------------------- #

SUMMARY_PROMPT = """\
Write a detailed summary of the conversation above. \
Use plain text, no markdown.\
Include relevant code blocks. \
Cover: what the user asked for, what was done, which files were changed, and current status. \
Be specific — include actual file paths, function names, key implementation details, code and outcomes. \
Do not include any preamble or closing remarks."""
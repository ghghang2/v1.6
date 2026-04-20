#!/usr/bin/env python3
"""
run.py – Start llama-server and provide simple status/stop helpers.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

from nbchat.core import config

# --------------------------------------------------------------------------- #
#  Constants
# --------------------------------------------------------------------------- #
SERVICE_INFO = Path(config.SERVICE_INFO_PATH)
LLAMA_LOG    = Path(config.LLAMA_LOG_PATH)
# RELEASE_REPO = f"{config.USER_NAME}/llamacpp_g4"
RELEASE_REPO = f"{config.USER_NAME}/llamacpp_t4"
MODEL        = config.MODEL_NAME
PORT         = config.PORT
N_PARALLEL   = config.N_PARALLEL
CTX_SIZE     = config.CTX_SIZE
N_GPU_LAYERS = config.N_GPU_LAYERS
WA_PORT      = os.environ.get("WA_PORT", "8764")
WA_ALLOW     = os.environ.get("WA_ALLOW", "")
REPO_ROOT    = Path(__file__).resolve().parent
CHANNELS_DIR = REPO_ROOT / "nbchat" / "channels"

# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #

def _run_blocking(cmd: str, *, extra_env: dict | None = None) -> None:
    """Standard blocking run for setup tasks."""
    env = {**os.environ, **(extra_env or {})}
    subprocess.run(cmd, shell=True, env=env, check=True)


def _run_detached(cmd: str | list, log_path: Path, label: str, extra_env: dict | None = None) -> int:
    """
    Launches a command fully detached from the parent process.
    Returns the PID of the started process.
    """
    env = {**os.environ, **(extra_env or {})}
    log_file = log_path.open("w", encoding="utf-8", buffering=1)
    
    # start_new_session=True makes it the leader of a new process group
    # close_fds=True ensures the notebook doesn't hang on open pipes
    with open(os.devnull, "r") as devnull:
        p = subprocess.Popen(
            cmd,
            shell=isinstance(cmd, str),
            stdin=devnull,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
            env=env
        )
    
    log_file.close()
    print(f"[run] {label} started (PID: {p.pid})")
    return p.pid


def _is_port_free(port: int) -> bool:
    result = subprocess.run(["ss", "-tuln"], capture_output=True, text=True)
    return str(port) not in result.stdout


def _wait_for(url: str, *, timeout: int = 360, interval: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def _save_service_info(pids: dict[str, int]) -> None:
    SERVICE_INFO.write_text(json.dumps({
        "pids": pids,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, indent=2))


def _load_service_info() -> dict:
    if not SERVICE_INFO.exists():
        raise FileNotFoundError("No service_info.json found – services likely not running.")
    return json.loads(SERVICE_INFO.read_text())


def _kill_pid(name: str, pid: int) -> None:
    if psutil is None:
        print(f"psutil missing – cannot gracefully kill {name} (PID {pid})")
        return
    try:
        proc = psutil.Process(pid)
        for child in proc.children(recursive=True):
            child.terminate()
        proc.terminate()
        print(f"✓ {name} (PID {pid}) stopped")
    except psutil.NoSuchProcess:
        print(f"! {name} (PID {pid}) was already dead")
    except Exception as exc:
        print(f"! Error stopping {name}: {exc}")

# --------------------------------------------------------------------------- #
#  Commands
# --------------------------------------------------------------------------- #

def main() -> None:
    if not os.getenv("GITHUB_TOKEN"):
        sys.exit("[ERROR] GITHUB_TOKEN must be set")

    if not _is_port_free(PORT):
        sys.exit(f"[ERROR] Port {PORT} is already in use")

    # 1. Binary Setup
    _run_blocking(
        f"gh release download --repo {RELEASE_REPO} --pattern llama-server --skip-existing",
        extra_env={"GITHUB_TOKEN": os.environ["GITHUB_TOKEN"]},
    )
    _run_blocking("chmod +x ./llama-server")

    pids = {}

    # 2. Start llama-server

    llama_cmd = [ ## G4
        "./llama-server",
        "-hf", MODEL,
        "--port", str(PORT),
        "--parallel", "1",
        "--ctx-size", str(CTX_SIZE),
        "--n-gpu-layers", "999",
        "--flash-attn", "1",
        "--batch-size", "2048",
        "--ubatch-size", "512",
        # "--cache-type-k", "q8_0",
        # "--cache-type-v", "q8_0",
        "--temp", "0.6",
        "--top-p", "0.95",
        "--top-k", "20",
        "--min-p", "0.0",
        "--repeat-penalty", "1.0",
        "--reasoning", "on",
        "--mmap",
        "--mlock",
        "--metrics",
    ]
    # llama_cmd = [ ## T4
    #     "./llama-server",
    #     "-hf", MODEL,
    #     "--port", str(PORT),
    #     "--parallel", str(N_PARALLEL),
    #     "--ctx-size", str(CTX_SIZE),
    #     "--n-gpu-layers", str(N_GPU_LAYERS),
    #     "--flash-attn", "1",
    #     "--temp", "0.6", # 27B thinking
    #     "--top-p", "0.95",
    #     "--top-k", "20",
    #     "--chat-template-kwargs", '{"enable_thinking": true}',
    #     "--batch-size", "512",
    #     "--ubatch-size", "512",
    #     "--no-mmap",
    #     "--mlock",
    #     "--metrics",
    #     # # Speculative decoding — draft on GPU!
    #     # "-hfrd", "unsloth/Qwen3.5-0.8B-GGUF:IQ4_XS",
    #     # "-ngld", "999",             # ← KEY FIX: put the 0.8B on GPU, it's ~300MB
    #     # "--ctx-size-draft", "8192", # ← smaller draft ctx saves VRAM
    #     # "--draft", "16",
    #     # "--draft-p-min", "0.5",     # lower threshold for thinking-token uncertainty
    # ]
    pids["llama"] = _run_detached(llama_cmd, LLAMA_LOG, "llama-server")

    # # 3. Start WhatsApp Python Server
    # wa_py_cmd = f"python -m nbchat.channels.whatsapp_server"
    # pids["whatsapp_python"] = _run_detached(
    #     wa_py_cmd, 
    #     REPO_ROOT / "whatsapp_server.log", 
    #     "WhatsApp Python Server",
    #     extra_env={"WA_PORT": WA_PORT}
    # )
    # time.sleep(2) # Let FastAPI bind

    # # 4. Start WhatsApp Bridge (Node)
    # bridge_path = CHANNELS_DIR / "whatsapp_bridge.js"
    # if not bridge_path.exists():
    #     sys.exit(f"[ERROR] Bridge script not found: {bridge_path}")
    
    # wa_node_cmd = f"node {bridge_path}"
    # pids["whatsapp_bridge"] = _run_detached(
    #     wa_node_cmd, 
    #     REPO_ROOT / "whatsapp_bridge.log", 
    #     "WhatsApp Node Bridge",
    #     extra_env={"WA_PORT": WA_PORT, "WA_ALLOW": WA_ALLOW}
    # )

    # 5. Environment Setup
    print("Installing remaining dependencies...")
    _run_blocking("pip install -r requirements.txt -qqq")
    _run_blocking("sudo apt-get update -qq && sudo apt-get install -y libxcomposite1 libgtk-3-0 libatk1.0-0")
    _run_blocking("playwright install --with-deps chromium")

    # 6. Final health check
    print("Waiting for llama-server health check...")
    if not _wait_for(f"http://localhost:{PORT}/health"):
        stop() # Cleanup what we started
        sys.exit("[ERROR] llama-server failed to start within timeout")

    _save_service_info(pids)
    print("\n" + "="*60)
    print("ALL SERVICES RUNNING SUCCESSFULLY!")
    print(f"WhatsApp QR: tail -f whatsapp_bridge.log")
    print("="*60)
    
    os._exit(0)


def status() -> None:
    try:
        info = _load_service_info()
    except FileNotFoundError as exc:
        print(exc)
        return

    print("=" * 60)
    print(f"Started at : {info['started_at']}")
    for name, pid in info["pids"].items():
        alive = psutil.pid_exists(pid) if psutil else "Unknown (psutil missing)"
        status_str = "RUNNING" if alive is True else "STOPPED"
        print(f"{name:16} (PID {pid}): {status_str}")
    print("=" * 60)


def stop() -> None:
    try:
        info = _load_service_info()
    except FileNotFoundError:
        print("No active services found in service_info.json")
        return

    print("Shutting down all services...")
    for name, pid in info["pids"].items():
        _kill_pid(name, pid)
    
    SERVICE_INFO.unlink(missing_ok=True)
    print("Cleanup complete.")


if __name__ == "__main__":
    commands = {"--status": status, "--stop": stop}
    if len(sys.argv) == 1:
        main()
    elif sys.argv[1] in commands:
        commands[sys.argv[1]]()
    else:
        print(f"Unknown command: {sys.argv[1]}")
        print("Usage: python run.py [--status | --stop]")
        sys.exit(1)
        
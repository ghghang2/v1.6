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
RELEASE_REPO = f"{config.USER_NAME}/llamacpp_t4_v2"
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
    llama_cmd = [
        "./llama-server",
        "-hf", MODEL,
        "--port", str(PORT),
        "--parallel", str(N_PARALLEL),
        "--ctx-size", str(CTX_SIZE),
        "--n-gpu-layers", str(N_GPU_LAYERS),
        "--flash-attn", "1",
        # "--temp", "1.0", # 9B reasoning
        "--temp", "0.6", # 27B thinking
        "--top-p", "0.95",
        "--top-k", "20",
        "--chat-template-kwargs", '{"enable_thinking": true}',
        "--batch-size", "512",
        "--ubatch-size", "512",
        "--no-mmap",
        "--mlock",
        "--metrics",
    ]
    pids["llama"] = _run_detached(llama_cmd, LLAMA_LOG, "llama-server")

    # 3. Start WhatsApp Python Server
    wa_py_cmd = f"python -m nbchat.channels.whatsapp_server"
    pids["whatsapp_python"] = _run_detached(
        wa_py_cmd, 
        REPO_ROOT / "whatsapp_server.log", 
        "WhatsApp Python Server",
        extra_env={"WA_PORT": WA_PORT}
    )
    time.sleep(2) # Let FastAPI bind

    # 4. Start WhatsApp Bridge (Node)
    bridge_path = CHANNELS_DIR / "whatsapp_bridge.js"
    if not bridge_path.exists():
        sys.exit(f"[ERROR] Bridge script not found: {bridge_path}")
    
    wa_node_cmd = f"node {bridge_path}"
    pids["whatsapp_bridge"] = _run_detached(
        wa_node_cmd, 
        REPO_ROOT / "whatsapp_bridge.log", 
        "WhatsApp Node Bridge",
        extra_env={"WA_PORT": WA_PORT, "WA_ALLOW": WA_ALLOW}
    )

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
# #!/usr/bin/env python3
# """
# run.py – Start llama-server and provide simple status/stop helpers.

# Usage
# -----
#     python run.py          # start everything
#     python run.py --status # inspect current state
#     python run.py --stop   # terminate all services
# """

# from __future__ import annotations

# import json
# import os
# import subprocess
# import sys
# import time
# import urllib.request
# from pathlib import Path

# try:
#     import psutil
# except ImportError:  # pragma: no cover - fallback when psutil is missing
#     psutil = None

# # --------------------------------------------------------------------------- #
# #  Constants – load from repo_config.yaml via nbchat.core.config
# # --------------------------------------------------------------------------- #
# from nbchat.core import config

# # Paths and repository identifiers are now read from the configuration file.
# SERVICE_INFO  = Path(config.SERVICE_INFO_PATH)
# LLAMA_LOG     = Path(config.LLAMA_LOG_PATH)
# RELEASE_REPO          = f"{config.USER_NAME}/llamacpp_t4_v2"
# # Q4_K_M (~12 GB) fits entirely in T4 VRAM — no CPU offload, maximum TPS.
# # Switch to Q8_0 (~21 GB) only if output quality is insufficient (will require partial CPU offload).
# MODEL         = config.MODEL_NAME
# PORT          = config.PORT
# N_PARALLEL    = config.N_PARALLEL  # matches 1-2 simultaneous users; fewer slots = faster per-request TPS
# CTX_SIZE      = config.CTX_SIZE  # tokens per slot; total KV mem ≈ CTX_SIZE * N_PARALLEL * layers. 32K fits within T4 headroom at Q4_K_M + N_PARALLEL=2
# N_GPU_LAYERS  = config.N_GPU_LAYERS  # offload all layers to GPU (llama.cpp clamps to actual layer count)
# WA_PORT      = os.environ.get("WA_PORT",      "8765")
# WA_ALLOW     = os.environ.get("WA_ALLOW",     "")
# REPO_ROOT    = Path(__file__).resolve().parent
# CHANNELS_DIR = REPO_ROOT / "nbchat" / "channels"
# _procs: list[subprocess.Popen] = []

# # --------------------------------------------------------------------------- #
# #  Helpers
# # --------------------------------------------------------------------------- #
# def _run(cmd: str, *, extra_env: dict | None = None) -> None:
#     """Run a shell command, optionally merging extra environment variables."""
#     env = {**os.environ, **(extra_env or {})}
#     subprocess.run(cmd, shell=True, env=env, check=True)


# def _is_port_free(port: int) -> bool:
#     result = subprocess.run(["ss", "-tuln"], capture_output=True, text=True)
#     return str(port) not in result.stdout


# def _wait_for(url: str, *, timeout: int = 360, interval: float = 1.0) -> bool:
#     deadline = time.monotonic() + timeout
#     while time.monotonic() < deadline:
#         try:
#             with urllib.request.urlopen(url, timeout=5) as r:
#                 if r.status == 200:
#                     return True
#         except Exception:
#             pass
#         time.sleep(interval)
#     return False


# def _save_service_info(pid: int) -> None:
#     SERVICE_INFO.write_text(json.dumps({
#         "llama_server_pid": pid,
#         "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
#     }, indent=2))


# def _load_service_info() -> dict:
#     if not SERVICE_INFO.exists():
#         raise FileNotFoundError("No service_info.json found – are the services running?")
#     return json.loads(SERVICE_INFO.read_text())


# def _kill_pid(name: str, pid: int) -> None:
#     """Gracefully terminate a process and its children."""
#     if psutil is None:
#         print(f"psutil not available – cannot gracefully terminate {name} (PID {pid})")
#         return
#     try:
#         proc = psutil.Process(pid)
#         for child in proc.children(recursive=True):
#             child.terminate()
#         proc.terminate()
#         print(f"{name} (PID {pid}) stopped")
#     except psutil.NoSuchProcess:
#         print(f"{name} (PID {pid}) was not running")
#     except Exception as exc:
#         print(f"Error stopping {name} (PID {pid}): {exc}")

# def _launch(cmd: str, *, extra_env: dict | None = None, label: str = "") -> subprocess.Popen:
#     """Launch a background process and register it for cleanup."""
#     env = {**os.environ, **(extra_env or {})}
#     print(f"[run] starting {label or cmd[:60]}")
#     p = subprocess.Popen(cmd, shell=True, env=env)
#     _procs.append(p)
#     return p

# def _whatsapp_python_server() -> subprocess.Popen:
#     """Start the Python FastAPI WhatsApp HTTP server."""
#     cmd = (
#         f"python -m nbchat.channels.whatsapp_server"
#         f" > whatsapp_server.log 2>&1"
#     )
#     p = _launch(
#         cmd,
#         extra_env={"WA_PORT": WA_PORT},
#         label=f"WhatsApp Python server (port {WA_PORT})",
#     )
#     # Brief pause to let FastAPI bind.
#     time.sleep(2)
#     return p
 
 
# def _whatsapp_bridge() -> subprocess.Popen:
#     """Start the Node.js Baileys bridge.
 
#     On first run this prints a QR code to whatsapp_bridge.log.
#     Tail that file and scan the QR with your phone:
#         tail -f whatsapp_bridge.log
#     """
#     bridge = CHANNELS_DIR / "whatsapp_bridge.js"
#     if not bridge.exists():
#         raise FileNotFoundError(f"Bridge script not found: {bridge}")
 
#     cmd = f"node {bridge} > whatsapp_bridge.log 2>&1"
#     p = _launch(
#         cmd,
#         extra_env={"WA_PORT": WA_PORT, "WA_ALLOW": WA_ALLOW},
#         label="WhatsApp Node bridge",
#     )
#     print(
#         "[run] WhatsApp bridge started.\n"
#         "[run] If this is a new device, scan the QR code:\n"
#         "[run]   tail -f whatsapp_bridge.log"
#     )
#     return p

# # --------------------------------------------------------------------------- #
# #  Commands
# # --------------------------------------------------------------------------- #
# def main() -> None:
#     if not os.getenv("GITHUB_TOKEN"):
#         sys.exit("[ERROR] GITHUB_TOKEN must be set")

#     if not _is_port_free(PORT):
#         sys.exit(f"[ERROR] Port {PORT} is already in use")

#     # Download pre-built llama-server binary
#     _run(
#         f"gh release download --repo {RELEASE_REPO} --pattern llama-server --skip-existing",
#         extra_env={"GITHUB_TOKEN": os.environ["GITHUB_TOKEN"]},
#     )
#     _run("chmod +x ./llama-server")

#     # Start llama-server fully detached — stdin from /dev/null, close_fds=True,
#     # and parent closes its file handle immediately after Popen returns.
#     # This ensures the notebook shell has no open fd tying it to the child process.
#     log_file = LLAMA_LOG.open("w", encoding="utf-8", buffering=1)
#     with open(os.devnull, "r") as devnull:
#         llama_proc = subprocess.Popen(
#             [
#                 "./llama-server",
#                 "-hf",            MODEL,
#                 "--port",         str(PORT),
#                 "--parallel",     str(N_PARALLEL),
#                 "--ctx-size",     str(CTX_SIZE),
#                 "--n-gpu-layers", str(N_GPU_LAYERS),
#                 "--flash-attn", "0", # T4 regresses w fa 1
#                 "--temp", "1.0", # 9B reasoning
#                 # "--temp", "0.6", # 27B thinking
#                 "--top-p", "0.95",
#                 "--top-k", "20",
#                 "--min-p", "0.0",
#                 "--chat-template-kwargs", '{"enable_thinking": false}', # false for 9B, true for 27B
#                 # "--cache-type-k", "q4_0", 
#                 # "--cache-type-v", "q4_0",
#                 "--batch-size", "512",
#                 "--ubatch-size", "512",
#                 # "-fit", "on",
#                 # "-fitc", "8192",
#                 "--no-mmap",
#                 "--mlock",
#                 "--metrics",
#             ],
#             stdin=devnull,
#             stdout=log_file,
#             stderr=subprocess.STDOUT,
#             start_new_session=True,
#             close_fds=True,
#         )
#     log_file.close()  # parent closes its copy; child retains its own fd

#     print(f"llama-server started (PID: {llama_proc.pid}) – waiting for health…")

#     whatsapp_server_proc = _whatsapp_python_server()
#     print(f"whatsapp server started (PID: {whatsapp_server_proc.pid})")
#     whatsapp_bridge_proc =_whatsapp_bridge()
#     print(f"whatsapp bridge started (PID: {whatsapp_bridge_proc.pid})")

#     # Install Python dependencies
#     print("Installing Python dependencies…")
#     _run("pip install -r requirements.txt -qqq")

#     # Install Playwright + system deps
#     print("Installing Playwright dependencies…")
#     _run("sudo apt-get update -qq")
#     _run("sudo apt-get install -y libxcomposite1 libgtk-3-0 libatk1.0-0")
#     _run("playwright install --with-deps chromium")

#     if not _wait_for(f"http://localhost:{PORT}/health"):
#         llama_proc.terminate()
#         sys.exit("[ERROR] llama-server failed to start within timeout")

#     _save_service_info(llama_proc.pid)
#     print("\nALL SERVICES RUNNING SUCCESSFULLY!")
#     print("=" * 60)
#     os._exit(0)  # Hard-exit so the notebook cell stops immediately


# def status() -> None:
#     try:
#         info = _load_service_info()
#     except FileNotFoundError as exc:
#         print(exc)
#         return

#     pid = info["llama_server_pid"]
#     alive = psutil.pid_exists(pid)
#     print("=" * 60)
#     print(f"Started at : {info['started_at']}")
#     print(f"llama-server PID {pid}: {'running' if alive else 'NOT running'}")
#     print("=" * 60)


# def stop() -> None:
#     try:
#         info = _load_service_info()
#     except FileNotFoundError:
#         print("No service_info.json – nothing to stop")
#         return

#     print("Stopping services…")
#     _kill_pid("llama-server", info["llama_server_pid"])
#     time.sleep(1)

#     SERVICE_INFO.unlink(missing_ok=True)
#     print("Cleaned up service info")


# # --------------------------------------------------------------------------- #
# #  Entry point
# # --------------------------------------------------------------------------- #
# if __name__ == "__main__":
#     commands = {"--status": status, "--stop": stop}
#     if len(sys.argv) == 1:
#         main()
#     elif sys.argv[1] in commands:
#         commands[sys.argv[1]]()
#     else:
#         print(f"Unknown command: {sys.argv[1]}")
#         print("Usage: python run.py [--status | --stop]")
#         sys.exit(1)
#!/usr/bin/env bash
# bench/tput_sweep.sh — throughput sweep for Qwen3.8-27B UD-Q4_K_XL on RTX 5090.
#
# Workload mirrors the agent: 32k prompt / 1500 gen, c1.
#
# Self-contained by design. This session runs THROUGH the prod llama-server
# (port 8889), and a second copy of the 17.2 GiB model does not fit beside it
# in 32 GiB VRAM. So this script:
#   1. snapshots the live server command line (to restart it identically),
#   2. stops the prod server via run.py (this session dies mid-turn; expected),
#   3. runs the whole sweep,
#   4. restarts llama-server from the snapshot,
#   5. relaunches the nbchat TUI so the client is usable again.
#
# Note: `python run.py` (start) is NOT used — it hard-exits without
# GITHUB_TOKEN and would also run pip/playwright setup. Stop via
# `python run.py --stop` is fine (it only reads service_info.json).
#
# Usage:  nohup bash bench/tput_sweep.sh > /tmp/tput_sweep.out 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/.."

# Refuse to run twice (lock file; pgrep -f would match its own wrapper).
LOCK=/tmp/tput_sweep.lock
if [ -e "$LOCK" ]; then
  echo "tput_sweep already running (lock: $LOCK) — exiting."
  exit 1
fi
touch "$LOCK"
trap 'rm -f "$LOCK"' EXIT INT TERM

MODEL=(-hf unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL)
WL=(-p 32768 -n 1500)                       # agent prompts run 16k-33k in, ~1.5k out
COMMON=(-ngl 999 -fa on -lm mmap -t 16 -r 3 --prio 1 --delay 5 -o csv)
OUT=bench/results/tput_sweep.csv
mkdir -p bench/results

# 1) Snapshot the live server command line for a faithful restart later.
LIVE_CMD=$(tr '\0' ' ' < /proc/$(ss -ltnp 2>/dev/null | grep 8889 | grep -oP 'pid=\K[0-9]+' | head -1)/cmdline)
echo "[$(date)] captured: $LIVE_CMD"

echo "[$(date)] stopping prod server..."
python run.py --stop 2>/dev/null || pkill -f "llama-server"
sleep 5

# 2) baseline = current production llama-server settings (f16 KV, 4096/2048)
./llama-bench "${MODEL[@]}" "${WL[@]}" -b 4096 -ub 2048 "${COMMON[@]}" >> "$OUT"

# 3) KV cache quant: f16 -> q8_0 -> q4_0 (halves/quarters KV bytes; decode is
#    bandwidth-bound, so smaller KV reads faster per step; also fits bigger ctx)
./llama-bench "${MODEL[@]}" "${WL[@]}" -b 4096 -ub 2048 -ctk q8_0 -ctv q8_0 "${COMMON[@]}" >> "$OUT"
./llama-bench "${MODEL[@]}" "${WL[@]}" -b 4096 -ub 2048 -ctk q4_0 -ctv q4_0 "${COMMON[@]}" >> "$OUT"

# 4) prefill chunk size (current 4096/2048 vs the 8192/4096 tried on the L40S)
./llama-bench "${MODEL[@]}" "${WL[@]}" -b 8192 -ub 4096 "${COMMON[@]}" >> "$OUT"
./llama-bench "${MODEL[@]}" "${WL[@]}" -b 16384 -ub 8192 "${COMMON[@]}" >> "$OUT"

# 5) load mode: mlock keeps weights pinned in RAM (no page faults).
#    Skipped silently if ulimit -l blocks it (this box: 8 GiB).
./llama-bench "${MODEL[@]}" "${WL[@]}" -b 4096 -ub 2048 -lm mlock "${COMMON[@]}" >> "$OUT" \
  || echo "[skip] mlock run failed (RLIMIT_MEMLOCK?)" >> "$OUT"

# 6) flash attention sanity check (FA should win at 32k; confirms no regression)
./llama-bench "${MODEL[@]}" "${WL[@]}" -b 4096 -ub 2048 -fa off "${COMMON[@]}" >> "$OUT"

# 7) CPU threads (256-core box; only a few are used for host-side ops)
./llama-bench "${MODEL[@]}" "${WL[@]}" -b 4096 -ub 2048 -t 8  "${COMMON[@]}" >> "$OUT"
./llama-bench "${MODEL[@]}" "${WL[@]}" -b 4096 -ub 2048 -t 32 "${COMMON[@]}" >> "$OUT"

# 8) context-length scaling: how does decode t/s degrade as KV grows?
./llama-bench "${MODEL[@]}" -p 8192  -n 1500 -b 4096 -ub 2048 "${COMMON[@]}" >> "$OUT"
./llama-bench "${MODEL[@]}" -p 16384 -n 1500 -b 4096 -ub 2048 "${COMMON[@]}" >> "$OUT"
./llama-bench "${MODEL[@]}" -p 65536 -n 1500 -b 4096 -ub 2048 "${COMMON[@]}" >> "$OUT"

# 9) restart the prod server from the snapshot (same binary, same args).
echo "[$(date)] restarting prod server..."
if ! (exec 3<>/dev/tcp/127.0.0.1/8889) 2>/dev/null; then
  # shellcheck disable=SC2086
  setsid nohup $LIVE_CMD >> ./llama_server.log 2>&1 &
  disown 2>/dev/null || true
fi

# This sweep killed the TUI's server mid-session; relaunch the TUI so the
# client is usable again once llama-server is back up.
pkill -f "nbchat.tui" 2>/dev/null || true
sleep 2
setsid nohup python -m nbchat.tui >/var/log/nbchat_tui.log 2>&1 &
disown 2>/dev/null || true

echo
echo "Done. Results: $OUT"

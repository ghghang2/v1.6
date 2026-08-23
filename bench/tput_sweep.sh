#!/usr/bin/env bash
# bench/tput_sweep.sh — throughput sweep for Qwen3.8-27B UD-Q4_K_XL on RTX 5090.
#
# Workload mirrors the agent: 32k prompt / 1500 gen, c1.
#
# Self-contained by design: the agent session runs THROUGH llama-server
# (PID 16672, port 8889), and a second copy of the 17.2 GiB model does not
# fit beside the prod server in 32 GiB VRAM — so this script:
#   1. stops the prod server (the agent session dies mid-turn; expected),
#   2. runs the whole sweep,
#   3. restarts llama-server,
#   4. relaunches the nbchat TUI so the client is usable again.
#
# Usage:  nohup bash bench/tput_sweep.sh > /tmp/tput_sweep.out 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/.."

# Refuse to run twice.
if pgrep -f "tput_sweep.sh" | grep -v "^$$\$" >/dev/null 2>&1; then
  echo "tput_sweep.sh already running — exiting."; exit 1
fi

MODEL=(-hf unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL)
WL=(-p 32768 -n 1500)                       # agent prompts run 16k-33k in, ~1.5k out
COMMON=(-ngl 999 -fa on -lm mmap -t 16 -r 3 --prio 1 --delay 5 -o csv)
OUT=bench/results/tput_sweep.csv
mkdir -p bench/results

echo "[$(date)] stopping prod server..."
python run.py stop 2>/dev/null || true
sleep 5

# 0) baseline = current production llama-server settings (f16 KV, 4096/2048)
./llama-bench "${MODEL[@]}" "${WL[@]}" -b 4096 -ub 2048 "${COMMON[@]}" >> "$OUT"

# 1) KV cache quant: f16 -> q8_0 -> q4_0 (halves/quarters KV bytes; decode is
#    bandwidth-bound, so smaller KV reads faster per step; also fits bigger ctx)
./llama-bench "${MODEL[@]}" "${WL[@]}" -b 4096 -ub 2048 -ctk q8_0 -ctv q8_0 "${COMMON[@]}" >> "$OUT"
./llama-bench "${MODEL[@]}" "${WL[@]}" -b 4096 -ub 2048 -ctk q4_0 -ctv q4_0 "${COMMON[@]}" >> "$OUT"

# 2) prefill chunk size (current 4096/2048 vs the 8192/4096 tried on the L40S)
./llama-bench "${MODEL[@]}" "${WL[@]}" -b 8192 -ub 4096 "${COMMON[@]}" >> "$OUT"
./llama-bench "${MODEL[@]}" "${WL[@]}" -b 16384 -ub 8192 "${COMMON[@]}" >> "$OUT"

# 3) load mode: mlock keeps weights pinned in RAM (no page faults).
#    Skipped silently if ulimit -l blocks it (this box: 8 GiB).
./llama-bench "${MODEL[@]}" "${WL[@]}" -b 4096 -ub 2048 -lm mlock "${COMMON[@]}" >> "$OUT" \
  || echo "[skip] mlock run failed (RLIMIT_MEMLOCK?)" >> "$OUT"

# 4) flash attention sanity check (FA should win at 32k; confirms no regression)
./llama-bench "${MODEL[@]}" "${WL[@]}" -b 4096 -ub 2048 -fa off "${COMMON[@]}" >> "$OUT"

# 5) CPU threads (256-core box; only a few are used for host-side ops)
./llama-bench "${MODEL[@]}" "${WL[@]}" -b 4096 -ub 2048 -t 8  "${COMMON[@]}" >> "$OUT"
./llama-bench "${MODEL[@]}" "${WL[@]}" -b 4096 -ub 2048 -t 32 "${COMMON[@]}" >> "$OUT"

# 6) context-length scaling: how does decode t/s degrade as KV grows?
./llama-bench "${MODEL[@]}" -p 8192  -n 1500 -b 4096 -ub 2048 "${COMMON[@]}" >> "$OUT"
./llama-bench "${MODEL[@]}" -p 16384 -n 1500 -b 4096 -ub 2048 "${COMMON[@]}" >> "$OUT"
./llama-bench "${MODEL[@]}" -p 65536 -n 1500 -b 4096 -ub 2048 "${COMMON[@]}" >> "$OUT"

echo "[$(date)] restarting prod server..."
# Only restart if the port is actually down (idempotent if a server came back meanwhile).
if ! (exec 3<>/dev/tcp/127.0.0.1/8889) 2>/dev/null; then
  python run.py start
fi

# This sweep killed the TUI's server mid-session; relaunch the TUI so the
# client is usable again once llama-server is back up.
pkill -f "nbchat.tui" 2>/dev/null || true
sleep 2
setsid nohup python -m nbchat.tui >/var/log/nbchat_tui.log 2>&1 &
disown 2>/dev/null || true

echo
echo "Done. Results: $OUT"

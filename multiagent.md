# Multi‑Agent Architecture – Light‑Weight Draft

> **Goal** – Add a lightweight “supervisor” to the current llama‑server + Streamlit stack so that multiple chat agents can run concurrently, each with its own context, and the supervisor can inject corrective messages when needed.

> **Scope** – No external services (Redis, Docker, Kubernetes).  **Dependencies** – Only the Python standard library + the existing `llama-server` binary.

---

## 1. Technical Specifications

| Item | Details |
|------|---------|
| **CPU** | 12‑core Xeon (or any modern CPU) – 8 GB RAM minimum for the LLM + supervisor |
| **GPU** | NVIDIA Tesla‑T4 (or any CUDA‑capable GPU) – 8 GB VRAM, compute capability ≥ 7.5 |
| **OS** | Ubuntu 22.04 LTS (or any Linux with `ss`, `systemd` support) |
| **Python** | 3.12 (stdlib only) |
| **LLM binary** | `llama-server` (pre‑built, 20 B GGUF, GPU‑accelerated) |
| **Ports** | 8000 – llama‑server API <br> 8002 – Streamlit UI <br> 4040 – ngrok |
| **Storage** | Local filesystem (SQLite optional) for chat history |
| **Optional** | `ngrok` (public tunnel) – not required for local tests |

---

## 2. Refined Step‑by‑Step Plan

| Step | Action | Why |
|------|--------|-----|
| **1. AgentProcess** | *Start a single shared `llama-server` instance for all agents (GPU‑shared).* <br> *Maintain a per‑agent `inbox` queue for user messages & interjections.* <br> *Expose a lightweight HTTP endpoint (`/chat/{id}`) that forwards to the shared server and streams the response back to the agent’s `inbox`.* | Reduces GPU overhead while still isolating context. |
| **2. Supervisor** | *Runs in its own process.* <br> *Listens to `agent_events` queue.* <br> *Loads a pluggable policy module (`policy.py`).* <br> *On event, if policy flags an issue, writes an “interject” message into the target agent’s `inbox`.* | Keeps supervision logic separate and testable. |
| **3. Persistence Layer** | *SQLite `chat_history` table* (chat_id, role, content, ts). <br> *Agent loads its history on start; writes each turn.* | Enables audit and recovery. |
| **4. Graceful Shutdown** | *`run.py` writes `agent_pids.json`.* <br> *`--stop` reads the file and SIGTERM‑s each PID.* <br> *Agents and supervisor trap SIGTERM to terminate child processes.* | Clean restarts. |
| **5. Testing** | *Unit tests for AgentProcess and Supervisor.* <br> *Integration test that simulates a user sending a message that triggers interjection.* | Confidence in end‑to‑end flow. |
| **6. Documentation** | *`multiagent.md` (this file).* <br> *Include quick‑start, architecture diagram, and future directions.* | Keeps the implementation transparent. |

---

## 3. High‑Level Architecture Diagram

```
+-------------------+          +-------------------+          +-------------------+
|  Streamlit UI     | <---->   |  Supervisor (P)  | <---->   |  AgentProcess (P) |
|  (port 8002)      |          |  (multiprocess)  |          |  (per chat)       |
+-------------------+          +-------------------+          +-------------------+
          |                          |                          |
          |  HTTP POST /chat/{id}    |                          |
          |  ----------------------> |                          |
          |                          |  Agent sends event      |
          |                          |  to supervisor          |
          |                          |  ----------------------> |
          |                          |  (interjection)         |
          |                          |  <---------------------- |
          |                          |                          |
          |                          |  forwards to llama-      |
          |                          |  server (port 8000)      |
          |                          |                          |
          |                          |                          |
          |                          |  writes to SQLite DB     |
          +--------------------------+--------------------------+
```

---

## 4. Quick‑Start Commands

```bash
# 1. Install Python 3.12 (if not already)
sudo apt install python3.12

# 2. Install requirements (only stdlib is needed)
#    (llama-server binary already in repo)

# 3. Run the whole stack
python run.py

# 4. Open browser at http://localhost:8002

# 5. To stop all agents
python run.py --stop
```

---

## 5. Future Enhancements

1. **GPU‑sharing policy** – limit number of concurrent contexts per GPU. 
2. **External policy engine** – swap the simple heuristic for a separate LLM that evaluates context drift. 
3. **WebSocket UI** – replace polling with SSE for lower latency. 
4. **Docker / Kubernetes** – containerize the agents for cloud deployment. 
5. **Monitoring** – expose Prometheus metrics per agent (latency, queue depth). 

---

> **Next steps** – Implement `agent.py`, `supervisor.py`, and update `run.py` to launch the supervisor and a couple of agents. Write a simple `policy.py` that flags any message containing “ERROR” and injects a corrective prompt. After that, run `pytest` to verify the integration.

```

``` 

--- 

*End of file.*
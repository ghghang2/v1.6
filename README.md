# nbchat

nbchat is a lightweight LLM inference harness: an agentic chat loop (tool
calling, streaming, L1/L2 memory, context windowing and output compression)
that talks to a local [llama.cpp](https://github.com/ggml-org/llama.cpp)
server over the OpenAI-compatible API.

It ships two front-ends:

| Front-end | Start with | Needs |
|-----------|-----------|-------|
| **Terminal UI (TUI)** — minimal, no Jupyter | `python -m nbchat.tui` | a plain terminal |
| Jupyter notebook UI | open a `.ipynb` and `from nbchat.ui.chatui import ChatUI` | Jupyter + `ipywidgets` |

## 1. Start the LLM server

```bash
python run.py           # downloads/starts llama-server + installs deps
python run.py --status  # show service status
python run.py --stop    # stop the services
```

The server URL, model and context size come from `repo_config.yaml`.

## 2. Chat from the terminal (TUI)

```bash
python -m nbchat.tui            # or: python nbchat_tui.py
```

Options:

```
--new          force a brand-new session
--session ID   resume a specific session id (see /sessions)
--no-color     disable ANSI colours
--check        only check the llama-server is reachable, then exit
```

Inside the TUI:

```
/            show help
/new         start a new session
/sessions    list terminal sessions
/load <id>   load one of the sessions from /sessions
/history     print the current session's messages
/model       show the active model and server
/clear       clear the screen
/quit        exit (Ctrl+C / Ctrl+D also work)
```

Type a normal message and press Enter to chat — the reply (and the model's
reasoning) stream in live. End a line with a trailing backslash (`\`) to wrap
it across multiple lines; press `Ctrl+C` while a reply is streaming to stop it.
Sessions persist in `nbchat/chat_history.db` and the last one is resumed on the
next start.

The TUI reuses the **same** agent stack as the notebook UI and the WhatsApp
channel (`ContextMixin` + `ConversationMixin` in `nbchat/ui/`) — only the
output layer is swapped from `ipywidgets` to `stdout`. No Jupyter, no
`ipywidgets`, no browser required.

## Layout

```
nbchat/
  core/     config, OpenAI client, SQLite db, compressor, monitoring, retry
  tools/    auto-discovered tool functions (run_command, git, browser, …)
  ui/       context_manager (memory/window), conversation (agentic loop),
            chatui (Jupyter), whatsapp/headless agents, styles
  tui/      terminal UI (TerminalAgent + REPL) — see below
  channels/ WhatsApp bridge (FastAPI + Node)
run.py      start/stop the local llama-server
```

## Tests

```bash
python -m pytest -q
```

The TUI tests (`tests/test_tui.py`) do not require a running server.

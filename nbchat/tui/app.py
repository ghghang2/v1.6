"""Terminal REPL for nbchat.

Run with a single command:

    python -m nbchat.tui          # or: python nbchat_tui.py

Options:
    --new         Force a brand-new session (skip resuming the last one).
    --session S   Resume a specific session id (see /sessions).
    --no-color    Disable ANSI colours.
    --check       Only check the llama-server is reachable, then exit.

The REPL reuses the full agent stack (memory, context windowing, tools,
streaming).  It talks to the local llama-server configured in
``repo_config.yaml`` (``SERVER_URL``).  If the server is not running it will
still start, but LLM calls will fail until you run ``python run.py``.
"""
from __future__ import annotations

import argparse
import sys
import threading
import urllib.request

from nbchat.core import config
from nbchat.tui.agent import TerminalAgent
from prompt_toolkit import print_formatted_text          # noqa: F401
from prompt_toolkit.formatted_text import ANSI            # noqa: F401
from prompt_toolkit.shortcuts import PromptSession

_BANNER = """
  ┌──────────────────────────────────────────────┐
  │  n b c h a t  ·  terminal  chat               │
  └──────────────────────────────────────────────┘
"""

_HELP = """Commands
  /help              Show this help.
  /new               Start a new session.
  /sessions          List terminal sessions (id prefix 'tui:').
  /load <id>         Load one of the sessions from /sessions.
  /history           Print the current session's message history.
  /model             Show the active model and server.
  /clear             Clear the screen.
  /quit              Exit (Ctrl+C / Ctrl+D also work).
  /sup <question>    Ask the supervisor about system state (requires --supervisor).

Tips
  • Type a normal message and press Enter to chat; the reply streams in live.
  • End a line with a backslash ( \\ ) to continue on the next line.
  • Type a new message while a reply is streaming to interrupt it and
    redirect the agent immediately (no need to wait for the stream to finish).
  • Press Ctrl+C while a reply is streaming to interrupt it too.
  • Start with --email to also receive Gmail replies in this chat.
"""


# ── Server health ──────────────────────────────────────────────────────────

def server_ok() -> bool:
    try:
        with urllib.request.urlopen(f"{config.SERVER_URL}/health", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


# ── Banner / startup ───────────────────────────────────────────────────────

def print_banner(agent: TerminalAgent, server_up: bool) -> None:
    p = agent.palette
    print(p.cyan(_BANNER.strip()))
    print(f"  {p.gray('model   ')} {agent.model_name}")
    print(f"  {p.gray('server  ')} {config.SERVER_URL} "
          f"{p.green('[up]') if server_up else p.red('[down]')}")
    print(f"  {p.gray('session ')} {agent.session_id}")
    print(f"  {p.gray('help    ')} type /help for commands")
    if not server_up:
        print(p.yellow("  ! llama-server is not reachable — LLM calls will fail "
                       "until you run: python run.py"))
    print()


# ── Slash commands ─────────────────────────────────────────────────────────

def handle_command(agent: TerminalAgent, line: str, supervisor=None) -> bool:
    """Handle a slash command.  Returns True if the caller should exit."""
    parts = line.split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("/quit", "/exit"):
        return True
    if cmd == "/help":
        print(_HELP)
    elif cmd == "/new":
        sid = agent.new_session()
        agent.remember_session(sid)
        print(f"Started new session: {sid}")
    elif cmd == "/sessions":
        sessions = agent.list_sessions()
        if not sessions:
            print("No terminal sessions yet.")
        else:
            for s in sessions:
                marker = " (current)" if s == agent.session_id else ""
                print(f"  {s}{marker}")
    elif cmd == "/load":
        if not arg:
            print("usage: /load <session-id>")
        else:
            agent._switch_session(arg)
            agent.remember_session(arg)
            print(f"Loaded session {arg} ({len(agent.history)} rows).")
    elif cmd == "/history":
        rows = agent.history
        if not rows:
            print("History is empty.")
        else:
            for role, content, _tid, tname, _targs, _ef in rows:
                if role == "analysis":
                    continue
                label = {"user": "You", "assistant": "Agent",
                         "tool": f"tool:{tname}"}.get(role, role)
                text = (content or "").strip()
                if len(text) > 200:
                    text = text[:197] + "..."
                print(f"  {label}: {text}")
    elif cmd in ("/model", "/about"):
        print(f"model   {agent.model_name}")
        print(f"server  {config.SERVER_URL}")
        print(f"session {agent.session_id}")
    elif cmd == "/clear":
        sys.stdout.write("\033[2J\033[H")
    elif cmd == "/sup":
        if supervisor is None:
            print(agent.palette.yellow(
                "  ! Supervisor is not running (start with --supervisor)."))
        elif not arg:
            print("usage: /sup <question>")
        else:
            print(agent.palette.magenta(f"  [supervisor] asking: {arg}\n"))
            answer = supervisor.ask(arg)
            for line_ in answer.splitlines() or [""]:
                print("  " + line_)
            print()
    else:
        print(f"Unknown command: {cmd}  (try /help)")
    return False


# ── Input reading (with backslash continuation) ────────────────────────────
#
# Uses prompt_toolkit so the typed line is rendered in its own row and is
# never overwritten by concurrent streaming output from the turn thread.
# Falls back to built-in input() when stdin is not a TTY (tests, CI, pipes)
# so that monkeypatching builtins.input still works.

_session = PromptSession()


def read_line(prompt: str, session: PromptSession | None = None) -> str:
    """Read a line from the user, supporting backslash continuation.

    Uses prompt_toolkit when stdin is a TTY so that streamed output from the
    background turn thread never corrupts the text the user is typing.
    Falls back to ``input()`` otherwise (tests, CI, piped stdin).
    """
    sess = session or _session
    interactive = sys.stdin.isatty()

    def _read(p: str) -> str:
        if interactive:
            return sess.prompt(p)
        return input(p)

    line = _read(prompt)
    if line.rstrip().endswith("\\"):
        buf = line.rstrip()[:-1]
        while True:
            cont = _read("  …")
            if cont.rstrip().endswith("\\"):
                buf += "\n" + cont.rstrip()[:-1]
            else:
                buf += "\n" + cont
                break
        return buf
    return line


def wait_for_turn(agent: TerminalAgent, thread: threading.Thread) -> None:
    """Block until the in-flight turn thread finishes.

    Runs on the main thread *only* when there is no active input prompt (the
    user has not typed anything to redirect), so it never competes with the
    input thread for the terminal.  If the user presses Ctrl+C while we wait,
    we ask the turn to stop and wait for it to wind down so the agent is left
    in a clean state (history consistent, no orphaned LLM call).
    """
    while thread.is_alive():
        try:
            thread.join(timeout=0.25)
        except KeyboardInterrupt:
            agent.interrupt()
            thread.join(timeout=5.0)
            if thread.is_alive():
                # The turn could not be stopped in time; abandon the wait and
                # let the daemon thread finish on its own.
                break

# ── Main loop ──────────────────────────────────────────────────────────────

def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nbchat-tui",
        description="Minimal terminal chat UI for nbchat.",
    )
    parser.add_argument("--new", action="store_true",
                        help="force a new session")
    parser.add_argument("--session", metavar="ID",
                        help="resume a specific session id")
    parser.add_argument("--no-color", action="store_true",
                        help="disable ANSI colours")
    parser.add_argument("--check", action="store_true",
                        help="check the llama-server is reachable, then exit")
    parser.add_argument("--email", action="store_true",
                        help="poll the Gmail inbox and inject replies into "
                             "the chat (extends the input box to email)")
    parser.add_argument("--no-auto-reply", action="store_true",
                        help="with --email: do NOT email the agent's reply "
                             "back to the sender")
    parser.add_argument("--supervisor", action="store_true",
                        help="start the always-on supervisor watchdog "
                             "(uses the second parallel slot)")
    args = parser.parse_args(argv)

    up = server_ok()
    if args.check:
        print("llama-server reachable." if up
              else f"llama-server NOT reachable at {config.SERVER_URL}")
        return 0 if up else 1

    agent = TerminalAgent(color=not args.no_color)

    if args.session:
        agent._switch_session(args.session)
    elif not args.new:
        last = TerminalAgent.last_session()
        if last:
            agent._switch_session(last)
    agent.remember_session(agent.session_id)

    print_banner(agent, up)

    # Supervisor: always-on watchdog on the second parallel slot.
    supervisor = None
    if args.supervisor or config.SUPERVISOR_ENABLED:
        from nbchat.core.supervisor import create_supervisor
        supervisor = create_supervisor(agent)
        supervisor.start()
        p = agent.palette
        print(p.magenta("  supervisor ")
              + f"ACTIVE (review every {supervisor._interval}s, "
                f"cooldown {supervisor._cooldown}s)")

    # Email bridge: pipe the Gmail inbox into the chat stream.
    bridge = None
    if args.email:
        import os
        if not os.getenv("GHG_APP_PASSWORD"):
            print(agent.palette.yellow(
                "  ! --email requested but GHG_APP_PASSWORD is not set; "
                "email bridge disabled."))
        else:
            from nbchat.tui.email_bridge import EmailBridge
            bridge = EmailBridge(
                agent,
                auto_reply=not args.no_auto_reply,
                supervisor=supervisor,
            )
            bridge.start()
            p = agent.palette
            print(p.magenta("  email   ") + "inbox bridge ACTIVE "
                  f"(poll every {bridge._poll_interval}s, "
                  f"auto-reply: {bridge._auto_reply})")

    prompt = agent.palette.cyan("\u276f ")
    # The turn thread runs the agentic loop in the background.  The main
    # thread *always* keeps reading input so the user can interject and
    # redirect the stream at any time.  We only join the turn thread on exit
    # (clean shutdown) — never while a prompt is live, which would block the
    # user from typing.
    turn_thread = None
    while True:
        try:
            line = read_line(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl+C / EOF at the prompt: stop any in-flight turn, exit.
            if turn_thread is not None and turn_thread.is_alive():
                agent.interrupt()
                wait_for_turn(agent, turn_thread)
            print("\nBye.")
            break

        if not line:
            continue

        # Mid-stream interjection: a turn is still running and the user typed
        # a new message.  Stop the current turn and start a fresh one with the
        # new message.  ``send_async`` serialises on the agent's send lock, so
        # the new turn waits for the (now interrupted) turn to wind down, then
        # runs the user's redirect — no message is lost.
        if turn_thread is not None and turn_thread.is_alive():
            agent.interrupt()
            print("\n" + agent.palette.yellow(
                "[redirecting \u2014 stopping current response]"))
            turn_thread = agent.send_async(line)
            agent.remember_session(agent.session_id)
            # Do NOT block: keep reading so the user can interject again.
            continue

        # No turn in flight: idle prompt loop.
        if line.startswith("/"):
            if handle_command(agent, line, supervisor=supervisor):
                print("Bye.")
                break
            continue

        turn_thread = agent.send_async(line)
        agent.remember_session(agent.session_id)
        # Do NOT block here: the loop returns to read_line immediately so the
        # user can interject mid-stream.  The turn thread streams in the
        # background.
    if bridge is not None:
        bridge.stop()
    if supervisor is not None:
        supervisor.stop()
    return 0

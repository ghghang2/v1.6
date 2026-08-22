"""Tests for the nbchat terminal UI (nbchat.tui).

These tests do NOT require a running llama-server: they exercise the
construction path, session bookkeeping, the colour palette and the
streaming output hooks (which write to stdout / capture state).
"""
from __future__ import annotations

import pytest

from nbchat.tui import TerminalAgent, Palette, run  # noqa: F401  (run importable)
from nbchat.tui.agent import short_arg, _arg_hint
from nbchat.tui.colors import Palette as _Palette  # same object
from nbchat.tui.app import handle_command, read_line


# ── Palette ────────────────────────────────────────────────────────────────

def test_palette_disabled_has_no_escapes():
    p = Palette(color=False)
    assert p.color is False
    assert p.cyan("hi") == "hi"
    assert p.bold("") == ""
    assert "\033" not in p.red("x")


def test_palette_wrap_shape_when_enabled(monkeypatch):
    # Force the TTY check to pass so the palette enables regardless of env.
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.delenv("NO_COLOR", raising=False)
    p = Palette(color=True)
    assert p.color is True
    out = p.cyan("hi")
    assert out.startswith("\033[36m") and out.endswith("\033[0m")
    assert "hi" in out


# ── Arg helpers ────────────────────────────────────────────────────────────

def test_short_arg_truncates():
    assert short_arg("hello") == "hello"
    long = "x" * 200
    out = short_arg(long)
    assert len(out) == 60 and out.endswith("...")


def test_arg_hint_pretty():
    assert _arg_hint('{"city": "Paris"}') == "city=Paris"
    assert _arg_hint("not json") == "not json"
    assert _arg_hint('{"a": 1, "b": 2}') == "a=1, b=2"


# ── Agent construction & session bookkeeping ───────────────────────────────

def test_agent_constructs_with_tui_session():
    agent = TerminalAgent(color=False)
    assert agent.session_id.startswith("tui:")
    assert agent.history == []
    assert agent.task_log == []
    assert agent._last_response == ""


def test_new_session_resets_state():
    agent = TerminalAgent(color=False)
    first = agent.session_id
    agent.history = [("user", "hi", "", "", "", 0)]
    sid = agent.new_session()
    assert sid != first
    assert agent.session_id == sid
    assert agent.history == []


def test_list_sessions_only_tui():
    agent = TerminalAgent(color=False)
    sessions = agent.list_sessions()
    assert isinstance(sessions, list)
    assert all(s.startswith("tui:") for s in sessions)


def test_remember_and_last_session_roundtrip():
    agent = TerminalAgent(color=False)
    agent.remember_session(agent.session_id)
    assert TerminalAgent.last_session() == agent.session_id


def test_switch_session_reloads():
    agent = TerminalAgent(color=False)
    agent.remember_session(agent.session_id)
    # Switching to the same id is a no-op.
    same = agent.session_id
    agent._switch_session(same)
    assert agent.session_id == same


# ── Streaming output hooks (no network) ────────────────────────────────────

def test_streaming_hooks_write_and_capture(capsys):
    agent = TerminalAgent(color=False)
    agent._on_stream_reasoning("I will think")
    agent._on_stream_reasoning("I will think step by step")
    agent._on_stream_token("Hello")
    agent._on_stream_token("Hello world")
    agent._on_stream_complete("Hello world", None)

    out = capsys.readouterr().out
    assert "[thinking]" in out
    assert "step by step" in out
    assert "Hello world" in out
    assert agent._last_response == "Hello world"
    # Streaming state resets after completion.
    assert agent._content_started is False
    assert agent._reasoning_printed == ""


def test_streaming_content_only_no_reasoning(capsys):
    agent = TerminalAgent(color=False)
    agent._on_stream_token("just an answer")
    agent._on_stream_complete("just an answer", None)
    out = capsys.readouterr().out
    assert "just an answer" in out
    assert "[thinking]" not in out


def test_agent_message_fallback(capsys):
    agent = TerminalAgent(color=False)
    agent._on_agent_message("Maximum tool turns (200) reached.")
    out = capsys.readouterr().out
    assert "Maximum tool turns" in out
    # _last_response should capture the notice when nothing else was set.
    assert agent._last_response == "Maximum tool turns (200) reached."


def test_tool_display(capsys):
    agent = TerminalAgent(color=False)
    agent._on_tool_display('{"result": "File created: a.py"}',
                           "create_file", '{"path": "a.py", "content": "x"}')
    out = capsys.readouterr().out
    assert "create_file" in out
    assert "path=a.py" in out
    assert "File created: a.py" in out


# ── REPL command handling (pure, no network) ──────────────────────────────

def test_handle_command_quit(capsys):
    agent = TerminalAgent(color=False)
    assert handle_command(agent, "/quit") is True
    assert handle_command(agent, "/exit") is True


def test_handle_command_new_and_unknown(capsys):
    agent = TerminalAgent(color=False)
    before = agent.session_id
    assert handle_command(agent, "/new") is False
    assert agent.session_id != before
    assert handle_command(agent, "/bogus") is False
    out = capsys.readouterr().out
    assert "Unknown command" in out


def test_handle_command_model_shows_config(capsys):
    agent = TerminalAgent(color=False)
    assert handle_command(agent, "/model") is False
    out = capsys.readouterr().out
    assert agent.model_name in out


def test_read_line_plain(capsys, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _="": "hello")
    assert read_line("❯ ") == "hello"


def test_read_line_continuation(capsys, monkeypatch):
    values = iter(["line1\\", "line2\\", "line3"])
    monkeypatch.setattr("builtins.input", lambda _="": next(values))
    assert read_line("❯ ") == "line1\nline2\nline3"

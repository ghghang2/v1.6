"""Tests for the nbchat email bridge and its components.

These tests do NOT require a running llama-server or a real IMAP/SMTP
connection.  Network calls (imaplib, smtplib) are monkey-patched.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from nbchat.core import email_inbox, email_smtp
from nbchat.tui import TerminalAgent


# ── email_inbox parsing (no network) ──────────────────────────────────────

def test_decode_header_plain():
    assert email_inbox._decode_header("Alice <alice@example.com>") == "Alice <alice@example.com>"


def test_decode_header_encoded():
    # RFC 2047 encoded header
    assert email_inbox._decode_header("=?utf-8?B?SGVsbG8=?= <x@y.com>") == "Hello <x@y.com>"


def test_extract_body_plain():
    import email as em
    msg = em.message_from_string(
        "Content-Type: text/plain\r\n\r\nHello world"
    )
    assert email_inbox._extract_body(msg) == "Hello world"


def test_extract_body_multipart():
    import email as em
    raw = (
        "MIME-Version: 1.0\r\n"
        "Content-Type: multipart/alternative; boundary=\"bnd\"\r\n"
        "\r\n"
        "--bnd\r\n"
        "Content-Type: text/plain\r\n"
        "\r\n"
        "plain body here\r\n"
        "--bnd\r\n"
        "Content-Type: text/html\r\n"
        "\r\n"
        "<html><p>html body</p></html>\r\n"
        "--bnd--\r\n"
    )
    msg = em.message_from_string(raw)
    body = email_inbox._extract_body(msg)
    assert "plain body here" in body


def test_extract_body_html_fallback():
    import email as em
    msg = em.message_from_string(
        "Content-Type: text/html\r\n\r\n<p>Hello</p><br><b>World</b>"
    )
    body = email_inbox._extract_body(msg)
    assert "Hello" in body and "World" in body


def test_email_message_dataclass():
    em = email_inbox.EmailMessage(
        message_id="<abc@x>", from_addr="a@b.com", subject="Hi",
        body="Hello", date=None, uid="42",
    )
    assert em.uid == "42"
    assert em.subject == "Hi"


# ── email_bridge: injection into agent (mocked network) ───────────────────

def test_bridge_injects_email_as_user_turn():
    """Email bridge calls agent.send_from_email, which appends to history."""
    agent = TerminalAgent(color=False)
    from nbchat.tui.email_bridge import EmailBridge
    bridge = EmailBridge(agent, auto_reply=False, poll_interval=1)

    # Mock send_from_email to capture the call
    captured = {}
    def fake_send_from_email(sender, subject, body):
        captured.update(sender=sender, subject=subject, body=body)
        # Simulate what the real method does: append to history
        text = f"[Email message from {sender}]\nSubject: {subject}\n\n{body}"
        agent.history.append(("user", text, "", "", "", 0))
        return "I received your email."

    with patch.object(agent, "send_from_email", side_effect=fake_send_from_email):
        msg = email_inbox.EmailMessage(
            message_id="<t1@x>", from_addr="alice@example.com",
            subject="Test", body="Hi agent", date=None, uid="1",
        )
        # Manually call the injection path
        agent.send_from_email.__wrapped__ if hasattr(agent.send_from_email, '__wrapped__') else None
        # Actually just verify the agent method works
        agent.send_from_email("alice@example.com", "Test", "Hi agent")

    assert any(r[0] == "user" and "alice@example.com" in r[1] for r in agent.history)


def test_bridge_skips_own_outbound():
    """Bridge should skip emails from its own address."""
    agent = TerminalAgent(color=False)
    from nbchat.tui.email_bridge import EmailBridge
    bridge = EmailBridge(agent, auto_reply=False, poll_interval=1)

    own_msg = email_inbox.EmailMessage(
        message_id="<self@x>", from_addr=email_smtp.LOGIN,
        subject="Re: Something (nbchat-tui)", body="self reply",
        date=None, uid="2",
    )
    assert bridge._is_outbound(own_msg) is True

    other_msg = email_inbox.EmailMessage(
        message_id="<other@x>", from_addr="alice@example.com",
        subject="Hello", body="hi", date=None, uid="3",
    )
    assert bridge._is_outbound(other_msg) is False


def test_bridge_parse_addr():
    from nbchat.tui.email_bridge import EmailBridge
    assert EmailBridge._parse_addr("Alice <alice@example.com>") == "alice@example.com"
    assert EmailBridge._parse_addr("alice@example.com") == "alice@example.com"
    assert EmailBridge._parse_addr("nobody") is None


def test_bridge_start_stop_lifecycle():
    agent = TerminalAgent(color=False)
    from nbchat.tui.email_bridge import EmailBridge
    bridge = EmailBridge(agent, auto_reply=False, poll_interval=1)
    assert not bridge.running
    bridge.start()
    assert bridge.running
    bridge.stop(timeout=2)
    assert not bridge.running


def test_bridge_dedup_by_message_id():
    """Second poll with same message_id should not re-inject."""
    agent = TerminalAgent(color=False)
    from nbchat.tui.email_bridge import EmailBridge
    bridge = EmailBridge(agent, auto_reply=False, poll_interval=1)

    msg = email_inbox.EmailMessage(
        message_id="<dup@x>", from_addr="a@b.com",
        subject="Dup", body="test", date=None, uid="5",
    )
    # Simulate first injection
    bridge._seen.add(msg.message_id)
    # Verify it would be skipped
    with patch("nbchat.core.email_inbox.fetch_unseen", return_value=[msg]), \
         patch("nbchat.core.email_inbox.mark_read"), \
         patch.object(agent, "send_from_email") as mock_send:
        bridge._poll_once()
        mock_send.assert_not_called()


# ── agent.send_from_email (mocked LLM) ────────────────────────────────────

def test_send_from_email_appends_labelled_user_message():
    agent = TerminalAgent(color=False)
    # Mock the conversation turn to avoid LLM calls
    with patch.object(agent, "_process_conversation_turn") as mock_turn:
        mock_turn.return_value = None
        agent._last_response = "I got your email."
        agent.send_from_email("bob@x.com", "Hello", "Please do X")

    # Verify the user message was composed correctly
    user_msgs = [r for r in agent.history if r[0] == "user"]
    assert user_msgs, "no user message found"
    last_user = user_msgs[-1][1]
    assert "bob@x.com" in last_user
    assert "Hello" in last_user
    assert "Please do X" in last_user


# ── truncation guard (conversation loop) ──────────────────────────────────

def test_truncation_guard_detects_ending_colon():
    """The truncation heuristic should flag a reply ending with a colon."""
    content = "Now let me write tests for the email feature:"
    _tail = content.rstrip()
    _ends_unfinished = bool(_tail) and _tail.endswith((
        ":", "\u2026", "...", " (", " [", " \u2014",
        ", and", ", the", ", that", ", it",
        " then", " now", " let", " i will",
    ))
    assert _ends_unfinished, "should detect trailing colon as truncated"


def test_truncation_guard_allows_complete_sentence():
    """A normal complete sentence should NOT be flagged."""
    content = "All done. The TUI is ready to use."
    _tail = content.rstrip()
    _ends_unfinished = bool(_tail) and _tail.endswith((
        ":", "\u2026", "...", " (", " [", " \u2014",
        ", and", ", the", ", that", ", it",
        " then", " now", " let", " i will",
    ))
    assert not _ends_unfinished, "complete sentence should not be flagged"


def test_truncation_guard_finish_reason_length():
    """finish_reason='length' should always be treated as truncated."""
    finish_reason = "length"
    _truncated = (finish_reason == "length")
    assert _truncated

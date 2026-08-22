"""Email bridge for the nbchat terminal UI.

Extends the TUI chat input box to the email layer: a daemon thread polls the
Gmail inbox (IMAP) and, for each new message, injects it into the agent's chat
stream as a user interjection — exactly as if the user typed it into the
terminal.  Optionally it sends the agent's reply back to the sender by email.

Design
------
* ``agent.send_from_email(...)`` is called under the agent's ``_send_lock``
  (acquired inside ``_run_turn``), so an email turn and a terminal turn can
  never run the LLM loop concurrently — the inbox is an extension of the same
  input box, not a parallel conversation.
* Emails are marked read **only after** they have been injected, so a crash
  before that point does not silently discard a message.
* All IMAP/SMTP calls are isolated in ``nbchat.core.email_inbox`` /
  ``email_smtp``; errors are logged and the loop continues (one bad poll
  must not kill the bridge).

Run with:  ``python -m nbchat.tui --email``
"""
from __future__ import annotations

import logging
import threading

from nbchat.core import config
from nbchat.core import email_inbox, email_smtp

_log = logging.getLogger("nbchat.tui.email")

# Mark our own replies so we never re-process (and reply to) ourselves.
OUTBOUND_MARKER = "nbchat-tui"


class EmailBridge:
    """Background thread that pipes the Gmail inbox into the chat."""

    def __init__(self, agent, *, auto_reply: bool | None = None,
                 poll_interval: int | None = None,
                 my_addr: str = email_smtp.LOGIN) -> None:
        self._agent = agent
        self._auto_reply = (
            config.EMAIL_AUTO_REPLY if auto_reply is None else auto_reply
        )
        self._poll_interval = (
            config.EMAIL_POLL_INTERVAL if poll_interval is None else poll_interval
        )
        self._my_addr = my_addr
        self._stop = threading.Event()
        self._seen: set[str] = set()   # in-memory Message-ID dedupe (belt & suspenders)
        self._thread: threading.Thread | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="nbchat-email-bridge", daemon=True
        )
        self._thread.start()
        _log.info("email bridge started (poll every %ss, auto_reply=%s)",
                  self._poll_interval, self._auto_reply)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None
        _log.info("email bridge stopped")

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ── Poll loop ──────────────────────────────────────────────────────────

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._poll_once()
            except Exception as exc:  # one bad poll must not kill the bridge
                _log.warning("email poll failed: %s: %s",
                             type(exc).__name__, exc)
            # Event.wait lets us stop promptly and is interruptible.
            self._stop.wait(self._poll_interval)

    def _poll_once(self) -> None:
        """Fetch unseen mail and inject each new message into the chat."""
        for msg in email_inbox.fetch_unseen(limit=20):
            if self._stop.is_set():
                break
            # Skip our own replies and anything already handled this process.
            if self._is_outbound(msg):
                email_inbox.mark_read(msg.uid)
                continue
            if msg.message_id in self._seen:
                email_inbox.mark_read(msg.uid)
                continue

            # Inject into the chat stream (blocks until the turn completes).
            reply = self._agent.send_from_email(
                msg.from_addr, msg.subject, msg.body
            )

            # Record as handled, then mark read (only after successful inject).
            self._seen.add(msg.message_id)
            try:
                email_inbox.mark_read(msg.uid)
            except Exception as exc:
                _log.warning("failed to mark read %s: %s", msg.uid, exc)

            # Optionally reply to the sender by email.
            if self._auto_reply and reply:
                try:
                    email_smtp.send(
                        to=self._parse_addr(msg.from_addr) or msg.from_addr,
                        subject=f"Re: {msg.subject} ({OUTBOUND_MARKER})",
                        body=reply,
                    )
                    _log.info("auto-replied to %s", msg.from_addr)
                except Exception as exc:
                    _log.warning("auto-reply failed: %s: %s",
                                 type(exc).__name__, exc)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _is_outbound(self, msg) -> bool:
        """True if this is one of our own auto-replies (avoid self-loops).

        We do NOT skip by From address: the user often replies from the
        same Gmail account the TUI uses, and those replies are exactly
        what we want to inject into the chat.  We only skip messages
        whose subject carries the ``(nbchat-tui)`` marker that we add
        to every auto-reply.
        """
        return f"({OUTBOUND_MARKER})" in msg.subject

    @staticmethod
    def _parse_addr(from_header: str) -> str | None:
        """Extract a bare email address from an RFC 5322 From header."""
        import email.utils
        _name, addr = email.utils.parseaddr(from_header)
        return addr if addr and "@" in addr else None


def start_for(agent, **kw) -> EmailBridge:
    """Convenience: construct + start a bridge for *agent*."""
    bridge = EmailBridge(agent, **kw)
    bridge.start()
    return bridge

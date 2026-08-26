"""Email bridge for the nbchat terminal UI.

Extends the TUI chat input box to the email layer: a daemon thread polls the
Gmail inbox (IMAP) and, for each **matching** message, injects it into the
agent's chat stream as a user interjection — exactly as if the user typed it
into the terminal.  Optionally it sends the agent's reply back by email.

Filtering
---------
Only emails that satisfy BOTH conditions are injected:

1. Sent **from the user's own address** (``ghghang2@gmail.com``).
2. Subject contains the string ``nbchat`` (case-insensitive).

All other inbox traffic (colleagues, newsletters, auto-replies, etc.) is
silently marked read and ignored.  This prevents the bridge from responding
to random unread mail on startup.

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
                 my_addr: str = email_smtp.LOGIN,
                 supervisor=None) -> None:
        self._agent = agent
        self._auto_reply = (
            config.EMAIL_AUTO_REPLY if auto_reply is None else auto_reply
        )
        self._poll_interval = (
            config.EMAIL_POLL_INTERVAL if poll_interval is None else poll_interval
        )
        self._my_addr = my_addr
        self._supervisor = supervisor
        self._stop = threading.Event()
        self._seen: set[str] = set()   # in-memory Message-ID dedupe (belt & suspenders)
        self._thread: threading.Thread | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────

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

    # ── Poll loop ──────────────────────────────────────────────────────

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
        """Fetch unseen mail and inject matching messages into the chat.

        Only emails from our own address with 'nbchat' in the subject are
        processed; all others are marked read and silently skipped.
        """
        for msg in email_inbox.fetch_unseen(limit=20):
            if self._stop.is_set():
                break
            # Only process deliberate user commands: from our own address
            # with 'nbchat' in the subject.  Everything else is skipped.
            if not self._should_process(msg):
                email_inbox.mark_read(msg.uid)
                continue
            # Dedup check (belt & suspenders for in-flight messages).
            if msg.message_id in self._seen:
                email_inbox.mark_read(msg.uid)
                continue

            # Route supervisor questions: subject contains "supervisor".
            if self._supervisor is not None and "supervisor" in msg.subject.lower():
                self._handle_supervisor_email(msg)
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

    # ── Helpers ──────────────────────────────────────────────────────

    def _handle_supervisor_email(self, msg) -> None:
        """Answer a supervisor question by email.

        The email body is treated as the question.  The supervisor gathers
        the live state snapshot and returns an answer, which is emailed back
        to the sender (if auto-reply is on) and logged to the terminal.
        """
        question = msg.body.strip() or msg.subject
        _log.info("supervisor email question from %s: %s",
                  msg.from_addr, question[:80])

        answer = self._supervisor.ask(question)

        # Log to terminal so the user sees it in the TUI.
        p = getattr(self._agent, "palette", None)
        if p is not None:
            import sys
            sys.stdout.write(p.magenta(f"  [supervisor] {question[:60]}\n"))
            for line in answer.splitlines() or [""]:
                sys.stdout.write("  " + line + "\n")
            sys.stdout.write("\n")
            sys.stdout.flush()

        # Record + mark read.
        self._seen.add(msg.message_id)
        try:
            email_inbox.mark_read(msg.uid)
        except Exception as exc:
            _log.warning("failed to mark read %s: %s", msg.uid, exc)

        # Optionally reply by email.
        if self._auto_reply:
            try:
                email_smtp.send(
                    to=self._parse_addr(msg.from_addr) or msg.from_addr,
                    subject=f"Re: {msg.subject} ({OUTBOUND_MARKER})",
                    body=answer,
                )
                _log.info("supervisor auto-replied to %s", msg.from_addr)
            except Exception as exc:
                _log.warning("supervisor auto-reply failed: %s: %s",
                             type(exc).__name__, exc)

    def _is_outbound(self, msg) -> bool:
        """True if this is one of our own auto-replies (avoid self-loops).

        Auto-replies carry the ``(nbchat-tui)`` marker in the subject so
        they are never re-processed.
        """
        return f"({OUTBOUND_MARKER})" in msg.subject

    def _should_process(self, msg) -> bool:
        """True if this email should be injected into the chat.

        Only emails that satisfy **all** conditions are processed:

        1. NOT one of our own auto-replies (subject has no ``(nbchat-tui)``).
        2. Sent from our own address (``ghghang2@gmail.com``).
        3. Subject contains the string ``nbchat`` (case-insensitive).

        This ensures the bridge acts as a deliberate command channel —
        the user sends themselves an email with 'nbchat' in the subject,
        and it gets injected as a user turn.  All other inbox traffic
        (colleagues, newsletters, etc.) is silently ignored.
        """
        # Skip our own auto-replies (prevent self-loops).
        if self._is_outbound(msg):
            return False
        # Must be from our own address.
        from_addr = self._parse_addr(msg.from_addr)
        if not from_addr or from_addr.lower() != self._my_addr.lower():
            return False
        # Must have 'nbchat' in the subject.
        # 'nbchat' routes to the assistant; 'supervisor' routes to the
        # supervisor (when one is attached).  Either keyword is a deliberate
        # command from the user's own address.
        subj = msg.subject.lower()
        if "nbchat" not in subj and "supervisor" not in subj:
            return False
        return True

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

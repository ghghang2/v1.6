"""Reusable SMTP email-sending for nbchat.

Used by both the ``send_email`` tool and the TUI email bridge.
Credentials: ``ghghang2@gmail.com`` + ``GHG_APP_PASSWORD`` env var.
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
LOGIN = "ghghang2@gmail.com"


def _password() -> str:
    pw = os.getenv("GHG_APP_PASSWORD")
    if not pw:
        raise RuntimeError("GHG_APP_PASSWORD env variable not set")
    return pw.strip()


def send(to: str, subject: str, body: str) -> str:
    """Send a plain-text email via Gmail SMTP.

    Parameters
    ----------
    to: Recipient address.
    subject: Subject line.
    body: Plain-text body.

    Returns
    -------
    str
        A human-readable confirmation on success.

    Raises
    ------
    Exception
        On any SMTP / authentication failure.
    """
    msg = EmailMessage()
    msg["From"] = LOGIN
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(LOGIN, _password())
        server.send_message(msg)

    return f"Email sent to {to}: {subject}"

#!/usr/bin/env python3
"""Send a progress email via SMTP. All SMTP_* settings come from the repo's
.env (gitignored) — see .env.example for the list.

Usage: python3 scripts/notify.py "Subject line" <<'EOF'
Body text (plain).
EOF
"""
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path


def _load_env() -> None:
    """Load the repo's .env (gitignored) so no secret lives in source."""
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


_load_env()

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
MAIL_FROM = os.environ.get("MAIL_FROM", SMTP_USER or "")
MAIL_TO = os.environ.get("MAIL_TO")

_missing = [name for name, val in (
    ("SMTP_HOST", SMTP_HOST),
    ("SMTP_USER", SMTP_USER),
    ("SMTP_PASSWORD", SMTP_PASSWORD),
    ("MAIL_TO", MAIL_TO),
) if not val]
if _missing:
    raise SystemExit("Missing SMTP_* vars — add them to the repo .env (gitignored): " + ", ".join(_missing))


def send(subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = MAIL_FROM
    msg["To"] = MAIL_TO
    msg.set_content(body)

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=30) as s:
        s.login(SMTP_USER, SMTP_PASSWORD)
        s.send_message(msg)
    print(f"sent: {subject}", flush=True)


if __name__ == "__main__":
    subject = sys.argv[1] if len(sys.argv) > 1 else "(no subject)"
    body = sys.stdin.read()
    send(subject, body)

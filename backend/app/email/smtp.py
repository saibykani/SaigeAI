"""Send an approved outreach email from the user's own Gmail (SMTP + Google App Password).

Used only after the user approves a specific message; caps and pauses are checked by the caller
before anything is sent. Nothing is sent without an explicit click.
"""

import asyncio
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.email.gmail import GmailError

HOST = "smtp.gmail.com"
SMTP_FACTORY = smtplib.SMTP_SSL  # patched in tests


def _send_sync(address: str, app_password: str, from_name: str, to: str, subject: str, body: str) -> str:
    msg = EmailMessage()
    msg["From"] = formataddr((from_name, address)) if from_name else address
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=address.split("@")[-1])
    msg.set_content(body)
    try:
        with SMTP_FACTORY(HOST, 465, timeout=20) as s:
            s.login(address, app_password)
            s.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        raise GmailError("Gmail rejected the App Password. Reconnect Gmail in Integrations.") from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise GmailError(f"Gmail couldn't send the email: {exc}") from exc
    return msg["Message-ID"]


async def send(address: str, app_password: str, from_name: str, to: str, subject: str, body: str) -> str:
    return await asyncio.to_thread(_send_sync, address, app_password, from_name, to, subject, body)

"""Send an approved email from the user's own Gmail over SMTP with a Google App Password.

Prefer `app.email.outbound.send`, which tries the Gmail API first. Used only after the user approves a specific
message; caps and pauses are checked by the caller before anything is sent.
"""

import asyncio
import smtplib
import time
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.email.gmail import GmailError

HOST = "smtp.gmail.com"
EHLO_NAME = "saige-ai.vercel.app"  # serverless hosts can report hostnames Gmail rejects
SMTP_FACTORY = smtplib.SMTP_SSL  # patched in tests
STARTTLS_FACTORY = smtplib.SMTP  # fallback, patched in tests
RETRY_WAIT = 2.0


def build_message(address: str, from_name: str, to: str, subject: str, body: str,
                  attachments: list[tuple[str, bytes, str]] | None = None, html: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((from_name, address)) if from_name else address
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=address.split("@")[-1])
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
    for filename, data, mime in attachments or []:
        maintype, _, subtype = mime.partition("/")
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return msg


def _deliver(address: str, app_password: str, msg: EmailMessage) -> None:
    try:
        with SMTP_FACTORY(HOST, 465, timeout=20, local_hostname=EHLO_NAME) as s:
            s.login(address, app_password)
            s.send_message(msg)
    except (smtplib.SMTPServerDisconnected, ConnectionError, TimeoutError):
        # Gmail sometimes drops implicit-TLS connections from cloud IPs; retry over STARTTLS on 587.
        with STARTTLS_FACTORY(HOST, 587, timeout=20, local_hostname=EHLO_NAME) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(address, app_password)
            s.send_message(msg)


def _send_msg_sync(address: str, app_password: str, msg: EmailMessage) -> str:
    try:
        try:
            _deliver(address, app_password, msg)
        except (smtplib.SMTPServerDisconnected, ConnectionError, TimeoutError):
            time.sleep(RETRY_WAIT)  # a dropped connection is usually transient: one more try
            _deliver(address, app_password, msg)
    except smtplib.SMTPAuthenticationError as exc:
        raise GmailError("Gmail rejected the App Password. Reconnect Gmail in Integrations.") from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise GmailError(f"Gmail couldn't send the email: {exc}. Connect Gmail with Google in Settings → Integrations "
                         "to send through the Gmail API instead.") from exc
    return msg["Message-ID"]


async def send_message(address: str, app_password: str, msg: EmailMessage) -> str:
    return await asyncio.to_thread(_send_msg_sync, address, app_password, msg)


async def send(address: str, app_password: str, from_name: str, to: str, subject: str, body: str,
               attachments: list[tuple[str, bytes, str]] | None = None, html: str | None = None) -> str:
    return await send_message(address, app_password, build_message(address, from_name, to, subject, body, attachments, html))

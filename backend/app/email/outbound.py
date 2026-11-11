"""Send mail from the user's own Gmail: the Gmail API (OAuth, gmail.send) first, SMTP + App Password as fallback.

Gmail often drops SMTP connections that come from cloud hosts ("Connection unexpectedly closed"); the Gmail API
is plain HTTPS and isn't affected. Callers check approvals, pauses and caps before calling `send`.
"""

import base64
import logging

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import collections as c
from app.email import gmail, smtp
from app.email.gmail import GmailError
from app.services import crypto

log = logging.getLogger(__name__)
SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


def can_api(integ: dict) -> bool:
    return bool(integ.get("refresh_token_enc")) and SEND_SCOPE in (integ.get("scopes") or [])


async def find_sender(db: AsyncIOMotorDatabase, uid: str) -> dict | None:
    """The user's Gmail connection if it can send (App Password, or OAuth with the send permission)."""
    integ = await db[c.INTEGRATIONS].find_one({"user_id": uid, "provider": "gmail"})
    if integ and (integ.get("app_password_enc") or can_api(integ)):
        return integ
    return None


async def send(integ: dict, from_name: str, to: str, subject: str, body: str,
               attachments: list[tuple[str, bytes, str]] | None = None, html: str | None = None) -> str:
    """Returns the Message-ID. Raises GmailError with a readable message when every route fails."""
    msg = smtp.build_message(integ["email"], from_name, to, subject, body, attachments, html)
    api_error = None
    if can_api(integ):
        try:
            token = await gmail.access_token(crypto.decrypt(integ["refresh_token_enc"]))
            await gmail.send_raw(token, base64.urlsafe_b64encode(msg.as_bytes()).decode())
            return msg["Message-ID"]
        except GmailError as exc:
            api_error = exc
            log.warning("Gmail API send failed, trying SMTP: %s", exc)
    if integ.get("app_password_enc"):
        return await smtp.send_message(integ["email"], crypto.decrypt(integ["app_password_enc"]), msg)
    raise api_error or GmailError("Connect Gmail in Settings → Integrations to send from Saige.")

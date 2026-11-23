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


def saige_sender() -> dict | None:
    """Saige's own mailbox (SAIGE_MAIL_USER + SAIGE_MAIL_APP_PASSWORD), used for emails Saige sends *to* the user."""
    from app.config import get_settings
    s = get_settings()
    if s.saige_mail_user and s.saige_mail_app_password:
        return {"email": s.saige_mail_user.strip(), "app_password_enc": crypto.encrypt(s.saige_mail_app_password.replace(" ", "")),
                "system": True, "from_name": s.saige_mail_from_name}
    return None


def resend_sender() -> dict | None:
    """Saige's verified-domain sender via Resend (RESEND_API_KEY + RESEND_FROM). Best inbox placement for every user."""
    from app.config import get_settings
    s = get_settings()
    if s.resend_api_key and s.resend_from:
        return {"email": s.resend_from.strip(), "resend": True, "system": True, "from_name": s.saige_mail_from_name}
    return None


async def find_digest_sender(db: AsyncIOMotorDatabase, uid: str) -> dict | None:
    """Sender for Saige-to-user mail (job digests), best inbox placement first:
    1. Saige's own domain via Resend, if configured;
    2. the user's own connected Gmail (mail to yourself never lands in spam);
    3. Saige's Gmail mailbox (SAIGE_MAIL_*), for users without a connected Gmail.
    Mail to recruiters/employers must keep using find_sender (it is the user writing)."""
    return resend_sender() or await find_sender(db, uid) or saige_sender()


async def _send_resend(integ: dict, from_name: str, to: str, subject: str, body: str, html: str | None) -> str:
    import httpx

    from app.config import get_settings
    s = get_settings()
    settings_url = s.frontend_url.rstrip("/") + "/settings"
    payload = {"from": f"{from_name} <{integ['email']}>", "to": [to], "subject": subject, "text": body,
               "headers": {"List-Unsubscribe": f"<{settings_url}>"}}
    if html:
        payload["html"] = html
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.post("https://api.resend.com/emails", json=payload, headers={"Authorization": f"Bearer {s.resend_api_key}"})
    if res.status_code >= 300:
        raise GmailError(f"Email service error ({res.status_code}): {res.text[:200]}")
    return str(res.json().get("id") or "")


async def send(integ: dict, from_name: str, to: str, subject: str, body: str,
               attachments: list[tuple[str, bytes, str]] | None = None, html: str | None = None) -> str:
    """Returns the Message-ID. Raises GmailError with a readable message when every route fails."""
    if integ.get("resend"):
        return await _send_resend(integ, from_name, to, subject, body, html)
    msg = smtp.build_message(integ["email"], from_name, to, subject, body, attachments, html)
    if integ.get("system"):
        # Saige's own digests: a one-click unsubscribe (RFC 8058) tells Gmail this is wanted bulk mail, not spam.
        from app.config import get_settings
        settings_url = get_settings().frontend_url.rstrip("/") + "/settings"
        msg["List-Unsubscribe"] = f"<mailto:{integ['email']}?subject=unsubscribe>, <{settings_url}>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
        msg["Reply-To"] = integ["email"]
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

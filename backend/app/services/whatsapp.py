"""WhatsApp notifications to the user's own phone via CallMeBot (free personal WhatsApp API).

Setup is done once by the user: they message CallMeBot's number from WhatsApp to get a personal API
key, then save phone + key in Integrations. Only the user's own number can be messaged this way.
Every in-app notification is mirrored when enabled. Failures are logged and never block the app.
"""

import logging
import re

import httpx

from app.config import get_settings
from app.database import collections as c
from app.services import crypto
from app.utils import utcnow

logger = logging.getLogger("saige.whatsapp")
API = "https://api.callmebot.com/whatsapp.php"


def http_client() -> httpx.AsyncClient:
    """Factory (patched in tests)."""
    return httpx.AsyncClient(timeout=8)


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"[^\d+]", "", phone)
    return digits if digits.startswith("+") else f"+{digits}"


def format_message(title: str, body: str = "", details: list[dict] | None = None, link: str | None = None) -> str:
    lines = [f"*Saige AI* · {title}"]
    if body:
        lines.append(body)
    for d in (details or [])[:5]:
        lines.append(f"• {d.get('platform', '')} {d.get('field', '')}: {d.get('after', '')}".strip())
    if link:
        base = get_settings().frontend_url.rstrip("/")
        lines.append(f"{base}{link}" if link.startswith("/") else link)
    return "\n".join(lines)[:1500]


async def send(phone: str, apikey: str, text: str) -> None:
    async with http_client() as client:
        r = await client.get(API, params={"phone": phone, "text": text, "apikey": apikey})
    if r.status_code != 200 or "ERROR" in r.text.upper()[:200]:
        raise RuntimeError(f"CallMeBot answered {r.status_code}: {r.text[:120]}")


async def mirror(db, user_id: str, title: str, body: str, details: list[dict] | None, link: str | None) -> None:
    """Send a notification to WhatsApp if the user enabled it. Never raises."""
    try:
        integ = await db[c.INTEGRATIONS].find_one({"user_id": user_id, "provider": "whatsapp", "enabled": True})
        if not integ:
            return
        await send(integ["phone"], crypto.decrypt(integ["apikey_enc"]), format_message(title, body, details, link))
        await db[c.INTEGRATIONS].update_one({"_id": integ["_id"]}, {"$set": {"last_sent_at": utcnow(), "error": None}})
    except Exception as exc:  # noqa: BLE001 - WhatsApp is best effort; the in-app notification already exists
        logger.warning("WhatsApp notification failed", extra={"user_id": user_id, "error": str(exc)[:200]})
        try:
            await db[c.INTEGRATIONS].update_one({"user_id": user_id, "provider": "whatsapp"},
                                                {"$set": {"error": str(exc)[:200]}})
        except Exception:  # noqa: BLE001, S110 - recording the error is also best effort
            pass

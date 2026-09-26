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
    return httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10))  # CallMeBot is often slow to answer


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"[^\d+]", "", phone)
    return digits if digits.startswith("+") else f"+{digits}"


ICONS = [  # first matching keyword in the title picks the icon
    ("interview", "📅"), ("offer", "🎉"), ("auto-applier", "🤖"), ("applied", "✅"), ("application", "📨"),
    ("email sent", "✉️"), ("sent to", "✉️"), ("reply", "📥"), ("recruiter", "📥"), ("updated", "🔄"), ("refresh", "🔄"),
    ("match", "🎯"), ("job", "💼"), ("follow", "⏰"), ("gmail", "📬"), ("connected", "🔗"),
]


def _icon(title: str) -> str:
    t = title.lower()
    return next((icon for key, icon in ICONS if key in t), "🔔")


def format_message(title: str, body: str = "", details: list[dict] | None = None, link: str | None = None) -> str:
    """Clean WhatsApp layout: a bold header line, the message, one bullet per detail, then an open link.

    *Saige AI* · 🔄 LinkedIn updated · Headline
    Your change is recorded.

    • *LinkedIn · Headline*
      Senior QA Engineer → Senior SDET | Selenium · Java
    ↗ https://saige-ai.vercel.app/profiles
    """
    lines = [f"*Saige AI* · {_icon(title)} {title.strip()}"]
    if body:
        lines.append(body.strip())
    rows = (details or [])[:5]
    if rows:
        lines.append("")
    for d in rows:
        head = " · ".join(x for x in (str(d.get("platform") or "").strip(), str(d.get("field") or "").strip()) if x)
        before, after = str(d.get("before") or "").strip(), str(d.get("after") or "").strip()
        lines.append(f"• *{head}*" if head else "•")
        if before and after:
            lines.append(f"   {before[:120]} → {after[:160]}")
        elif after:
            lines.append(f"   {after[:200]}")
    if len(details or []) > 5:
        lines.append(f"   …and {len(details) - 5} more")
    if link:
        base = get_settings().frontend_url.rstrip("/")
        lines.append(f"↗ {base}{link}" if link.startswith("/") else f"↗ {link}")
    return "\n".join(lines)[:1500]


class WhatsAppError(RuntimeError):
    pass


FAIL_HINTS = ("apikey is invalid", "invalid apikey", "not activated", "phone number is not", "error:", "not authorized",
              "you need to get the apikey", "wrong phone")


def answer_text(html: str) -> str:
    """CallMeBot answers with a small HTML page; keep just its visible sentence."""
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()[:200]


async def send(phone: str, apikey: str, text: str) -> str:
    """Send one message; returns CallMeBot's answer. Raises WhatsAppError only for a real rejection."""
    async with http_client() as client:
        r = await client.get(API, params={"phone": phone, "text": text, "apikey": apikey})
    said = answer_text(r.text)
    if r.status_code >= 400 or any(h in said.lower() for h in FAIL_HINTS):
        raise WhatsAppError(said or f"HTTP {r.status_code}")
    return said


# Alert groups the user can switch off individually (Settings → Alerts & templates).
GROUPS: dict[str, tuple[str, ...]] = {
    "applications": ("application", "auto_apply", "applications_approved"),
    "emails": ("recruiter_email", "gmail_sync", "reply_drafted"),
    "outreach": ("outreach", "followup"),
    "jobs": ("job_discovery", "job_feed"),
    "profile": ("profile", "naukri", "linkedin"),
    "interviews": ("interview",),
}


def group_for(kind: str | None) -> str:
    k = (kind or "").lower()
    return next((g for g, prefixes in GROUPS.items() if any(k.startswith(p) for p in prefixes)), "other")


async def mirror(db, user_id: str, title: str, body: str, details: list[dict] | None, link: str | None,
                 kind: str | None = None) -> None:
    """Send a notification to WhatsApp if the user enabled it (and hasn't muted its group). Never raises."""
    try:
        integ = await db[c.INTEGRATIONS].find_one({"user_id": user_id, "provider": "whatsapp", "enabled": True})
        if not integ or group_for(kind) in (integ.get("muted") or []):
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

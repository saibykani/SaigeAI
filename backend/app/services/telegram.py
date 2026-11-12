"""Telegram alerts through the official Bot API (free). The user links their chat by pressing Start on the bot with a
one-time code; every notify() is then mirrored to that chat. Needs TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_USERNAME."""

import html
import logging
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.deps import db_dep, get_current_user
from app.config import get_settings
from app.database import collections as c
from app.services.audit import log_action
from app.utils import utcnow

logger = logging.getLogger("saige.telegram")
router = APIRouter(prefix="/integrations/telegram", tags=["integrations"])
API = "https://api.telegram.org/bot{}/{}"


def http_client() -> httpx.AsyncClient:
    """Factory (patched in tests)."""
    return httpx.AsyncClient(timeout=10)


def configured() -> bool:
    s = get_settings()
    return bool(s.telegram_bot_token and s.telegram_bot_username)


async def call(method: str, payload: dict) -> dict:
    async with http_client() as client:
        r = await client.post(API.format(get_settings().telegram_bot_token, method), json=payload)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("description") or f"Telegram error {r.status_code}")
    return data


def format_message(title: str, body: str, link: str | None) -> str:
    base = get_settings().frontend_url.rstrip("/")
    text = f"<b>{html.escape(title)}</b>"
    if body:
        text += f"\n{html.escape(body[:600])}"
    if link:
        text += f"\n\n<a href='{html.escape(base + link if link.startswith('/') else link)}'>Open in Saige →</a>"
    return text


async def mirror(db: AsyncIOMotorDatabase, user_id: str, title: str, body: str, link: str | None) -> None:
    """Best effort: never raises (the in-app notification already exists)."""
    if not configured():
        return
    try:
        integ = await db[c.INTEGRATIONS].find_one({"user_id": user_id, "provider": "telegram", "enabled": True})
        if not integ or not integ.get("chat_id"):
            return
        await call("sendMessage", {"chat_id": integ["chat_id"], "text": format_message(title, body, link), "parse_mode": "HTML",
                                   "disable_web_page_preview": True})
        await db[c.INTEGRATIONS].update_one({"_id": integ["_id"]}, {"$set": {"last_sent_at": utcnow(), "error": None}})
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram notification failed", extra={"user_id": user_id, "error": str(exc)[:200]})


def _status(integ: dict | None) -> dict:
    s = get_settings()
    return {"available": configured(), "connected": bool(integ and integ.get("chat_id") and integ.get("enabled")),
            "name": (integ or {}).get("chat_name"), "bot": s.telegram_bot_username,
            "link": f"https://t.me/{s.telegram_bot_username}?start={integ['code']}" if integ and integ.get("code") and configured() else None}


@router.get("")
async def telegram_status(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return _status(await db[c.INTEGRATIONS].find_one({"user_id": user["_id"], "provider": "telegram"}))


@router.post("/start")
async def telegram_start(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """A one-time code; the user opens t.me/<bot>?start=<code> and presses Start."""
    if not configured():
        raise HTTPException(status.HTTP_409_CONFLICT, "Telegram alerts aren't set up on this server yet (TELEGRAM_BOT_TOKEN).")
    code = secrets.token_urlsafe(12).replace("-", "").replace("_", "")[:16]
    await db[c.INTEGRATIONS].update_one({"user_id": user["_id"], "provider": "telegram"},
                                        {"$set": {"code": code, "user_id": user["_id"], "provider": "telegram", "updated_at": utcnow()}}, upsert=True)
    return await telegram_status(user, db)


@router.post("/confirm")
async def telegram_confirm(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """After pressing Start: find the /start <code> message and remember that chat."""
    integ = await db[c.INTEGRATIONS].find_one({"user_id": user["_id"], "provider": "telegram"})
    if not integ or not integ.get("code"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Press Connect Telegram first.")
    updates = (await call("getUpdates", {"allowed_updates": ["message"], "limit": 100})).get("result", [])
    hit = next((u["message"] for u in reversed(updates) if (u.get("message") or {}).get("text", "").strip() == f"/start {integ['code']}"), None)
    if not hit:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Didn't see your Start yet. Open the link, press Start in Telegram, then try again.")
    chat = hit["chat"]
    name = " ".join(x for x in (chat.get("first_name"), chat.get("last_name")) if x) or chat.get("username") or "Telegram"
    await db[c.INTEGRATIONS].update_one({"_id": integ["_id"]}, {"$set": {"chat_id": chat["id"], "chat_name": name, "enabled": True,
                                                                        "connected_at": utcnow()}, "$unset": {"code": ""}})
    await call("sendMessage", {"chat_id": chat["id"], "text": "✅ Saige AI is connected. You'll get your job alerts here.", "parse_mode": "HTML"})
    await log_action(db, user_id=user["_id"], action="integration.telegram_connected", entity="integration")
    return await telegram_status(user, db)


@router.delete("")
async def telegram_disconnect(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    await db[c.INTEGRATIONS].delete_many({"user_id": user["_id"], "provider": "telegram"})
    await log_action(db, user_id=user["_id"], action="integration.telegram_disconnected", entity="integration")
    return _status(None)

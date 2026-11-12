"""Saige on WhatsApp: two-way chat through the official WhatsApp Business Cloud API (Meta).

The CallMeBot mirror in services/whatsapp.py stays as the one-way option. Here the user links their number from
Integrations (Saige sends a 6-digit code; they reply with it on WhatsApp or type it in the app), then chats:
jobs, apply N (+ yes/no), status, digest, pause, resume, help. "apply" only prepares; the user's "yes" is the human
approval (AGENTS.md rule 3) and then the normal application approval path runs. Needs WHATSAPP_TOKEN,
WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_VERIFY_TOKEN and WHATSAPP_APP_SECRET; without them everything reports "not configured".
"""

import hashlib
import hmac
import logging
import re
import secrets
from datetime import timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from pymongo import DESCENDING

from app.auth.deps import db_dep, get_current_user
from app.config import get_settings
from app.database import collections as c
from app.services.audit import log_action
from app.services.rate_limit import RateLimiter
from app.utils import new_id, utcnow

logger = logging.getLogger("saige.whatsapp_cloud")
router = APIRouter(prefix="/integrations/whatsapp-cloud", tags=["integrations"])
webhook_router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
GRAPH = "https://graph.facebook.com/v21.0/{}/messages"
PROVIDER = "whatsapp_cloud"
inbound_limiter = RateLimiter(20, 60)  # per phone number
code_limiter = RateLimiter(5, 3600)  # link codes per user per hour

HELP = ("*Saige AI on WhatsApp*\n"
        "• *jobs*: your top 5 new matches\n"
        "• *apply 2*: prepare job 2 from the list (then reply *yes* or *no*)\n"
        "• *status*: your pipeline\n"
        "• *digest*: today's summary\n"
        "• *pause* / *resume*: stop or restart all automation\n"
        "• *help*: this list")


def http_client() -> httpx.AsyncClient:
    """Factory (patched in tests)."""
    return httpx.AsyncClient(timeout=10)


def configured() -> bool:
    s = get_settings()
    return bool(s.whatsapp_token and s.whatsapp_phone_number_id and s.whatsapp_verify_token and s.whatsapp_app_secret)


def digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


async def send_text(to: str, text: str) -> None:
    s = get_settings()
    async with http_client() as client:
        r = await client.post(GRAPH.format(s.whatsapp_phone_number_id), headers={"Authorization": f"Bearer {s.whatsapp_token}"},
                              json={"messaging_product": "whatsapp", "to": digits(to), "type": "text",
                                    "text": {"preview_url": False, "body": text[:4000]}})
    if r.status_code >= 400:
        raise RuntimeError(f"WhatsApp error {r.status_code}")


def valid_signature(body: bytes, header: str | None) -> bool:
    secret = get_settings().whatsapp_app_secret
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[7:])


# ---------- linking (Integrations) ----------

def _status(integ: dict | None) -> dict:
    integ = integ or {}
    phone = integ.get("phone")
    return {"available": configured(), "connected": bool(integ.get("verified")), "pending": bool(phone and not integ.get("verified")),
            "phone": (phone[:-4] + "••••") if phone and len(phone) > 6 else phone, "digest": integ.get("digest", True)}


class LinkIn(BaseModel):
    phone: str = Field(min_length=8, max_length=24)


class CodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class PrefsIn(BaseModel):
    digest: bool


async def _integ(db: AsyncIOMotorDatabase, uid: str) -> dict | None:
    return await db[c.INTEGRATIONS].find_one({"user_id": uid, "provider": PROVIDER})


@router.get("")
async def wa_status(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return _status(await _integ(db, user["_id"]))


@router.post("/link")
async def wa_link(body: LinkIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Send a 6-digit code to the number; the user replies with it on WhatsApp or enters it here."""
    if not configured():
        raise HTTPException(status.HTTP_409_CONFLICT, "Saige on WhatsApp isn't configured on this server yet (WHATSAPP_TOKEN).")
    phone = digits(body.phone)
    if not 8 <= len(phone) <= 15:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Enter the number with country code, e.g. +91 98765 43210.")
    if not code_limiter.hit(f"wa-code:{user['_id']}"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many codes. Try again in an hour.")
    taken = await db[c.INTEGRATIONS].find_one({"provider": PROVIDER, "phone": phone, "verified": True, "user_id": {"$ne": user["_id"]}})
    if taken:
        raise HTTPException(status.HTTP_409_CONFLICT, "This number is already linked to another Saige account.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    try:
        await send_text(phone, f"Your Saige AI code is *{code}*. Reply with this code here (or type it in Saige) to link WhatsApp.")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Couldn't send the code on WhatsApp. Check the number.") from exc
    await db[c.INTEGRATIONS].update_one(
        {"user_id": user["_id"], "provider": PROVIDER},
        {"$set": {"phone": phone, "code_hash": hashlib.sha256(code.encode()).hexdigest(), "code_expires": utcnow() + timedelta(minutes=15),
                  "verified": False, "enabled": False, "updated_at": utcnow()},
         "$setOnInsert": {"_id": new_id(), "user_id": user["_id"], "provider": PROVIDER, "digest": True}}, upsert=True)
    await log_action(db, user_id=user["_id"], action="integration.whatsapp_cloud_code_sent", entity="integration")
    return _status(await _integ(db, user["_id"]))


async def _verify(db: AsyncIOMotorDatabase, integ: dict, code: str) -> bool:
    exp = integ.get("code_expires")
    if not integ.get("code_hash") or not exp:
        return False
    if exp.tzinfo is None:
        from datetime import UTC
        exp = exp.replace(tzinfo=UTC)
    if exp < utcnow() or not hmac.compare_digest(integ["code_hash"], hashlib.sha256(code.strip().encode()).hexdigest()):
        return False
    await db[c.INTEGRATIONS].update_one({"_id": integ["_id"]}, {"$set": {"verified": True, "enabled": True, "connected_at": utcnow()},
                                                               "$unset": {"code_hash": "", "code_expires": ""}})
    await log_action(db, user_id=integ["user_id"], action="integration.whatsapp_cloud_connected", entity="integration")
    from app.services.notify import notify

    await notify(db, user_id=integ["user_id"], kind="integration", title="WhatsApp connected", body="Chat with Saige on WhatsApp. Send 'help'.",
                 link="/integrations")
    return True


@router.post("/verify")
async def wa_verify(body: CodeIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    integ = await _integ(db, user["_id"])
    if not integ or not await _verify(db, integ, body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That code is wrong or expired. Send a new one.")
    try:
        await send_text(integ["phone"], "✅ Saige AI is linked. " + HELP)
    except Exception:  # noqa: BLE001
        logger.warning("WhatsApp welcome message failed")
    return _status(await _integ(db, user["_id"]))


@router.put("")
async def wa_prefs(body: PrefsIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    await db[c.INTEGRATIONS].update_one({"user_id": user["_id"], "provider": PROVIDER}, {"$set": {"digest": body.digest}})
    return _status(await _integ(db, user["_id"]))


@router.delete("")
async def wa_unlink(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    await db[c.INTEGRATIONS].delete_many({"user_id": user["_id"], "provider": PROVIDER})
    await db[c.WHATSAPP_SESSIONS].delete_many({"user_id": user["_id"]})
    await log_action(db, user_id=user["_id"], action="integration.whatsapp_cloud_disconnected", entity="integration")
    return _status(None)


# ---------- commands ----------

async def _session(db: AsyncIOMotorDatabase, uid: str) -> dict:
    return await db[c.WHATSAPP_SESSIONS].find_one({"user_id": uid}) or {}


async def _save_session(db: AsyncIOMotorDatabase, uid: str, **fields) -> None:
    await db[c.WHATSAPP_SESSIONS].update_one({"user_id": uid}, {"$set": {**fields, "updated_at": utcnow()},
                                                                "$setOnInsert": {"_id": new_id(), "user_id": uid}}, upsert=True)


async def cmd_jobs(db: AsyncIOMotorDatabase, uid: str) -> str:
    jobs = await db[c.JOBS].find({"user_id": uid, "status": {"$in": ["new", "saved", None]}}).sort(
        [("match.overall", DESCENDING), ("created_at", DESCENDING)]).to_list(5)
    if not jobs:
        return "No new matches right now. I'll tell you when strong ones arrive."
    await _save_session(db, uid, last_jobs=[j["_id"] for j in jobs], pending=None)
    lines = ["*Your top new matches*"]
    for i, j in enumerate(jobs, 1):
        score = (j.get("match") or {}).get("overall")
        lines.append(f"{i}. {j['title']} at {j['company']}" + (f" ({score}%)" if score is not None else ""))
    lines.append("\nReply *apply 2* to prepare one.")
    return "\n".join(lines)


async def cmd_apply(db: AsyncIOMotorDatabase, uid: str, n: int) -> str:
    from app.applications import service as svc

    ids = (await _session(db, uid)).get("last_jobs") or []
    if not 1 <= n <= len(ids):
        return "Send *jobs* first, then *apply* with a number from that list."
    job = await db[c.JOBS].find_one({"_id": ids[n - 1], "user_id": uid})
    if not job:
        return "That job is no longer available."
    a = await db[c.APPLICATIONS].find_one({"user_id": uid, "job_id": job["_id"]})
    if not a:
        a = await svc.create(db, uid, job["_id"], None, None)
    await _save_session(db, uid, pending={"application_id": a["_id"], "at": utcnow()})
    await log_action(db, user_id=uid, action="whatsapp.apply_prepared", entity="application", entity_id=a["_id"])
    return (f"Prepared: *{a['role']}* at *{a['company']}* (status {a['status']}).\n"
            "Reply *yes* to approve this application or *no* to cancel. Nothing is sent until you say yes.")


async def cmd_confirm(db: AsyncIOMotorDatabase, uid: str, yes: bool) -> str:
    from app.applications import service as svc

    pending = (await _session(db, uid)).get("pending")
    if not pending:
        return "Nothing is waiting for your approval. Send *jobs* to see matches."
    await _save_session(db, uid, pending=None)
    if not yes:
        await log_action(db, user_id=uid, action="whatsapp.apply_cancelled", entity="application", entity_id=pending["application_id"])
        return "Cancelled. Nothing was sent."
    try:
        a = await svc.get_owned(db, uid, pending["application_id"])
        res = await svc.approve_and_apply(db, uid, a)  # the user's "yes" on WhatsApp is the human approval
    except HTTPException as exc:
        return f"Couldn't approve: {exc.detail}"
    await log_action(db, user_id=uid, action="whatsapp.apply_approved", entity="application", entity_id=pending["application_id"],
                     details={"channel": "whatsapp"})
    msg = f"Approved: {res['application']['role']} at {res['application']['company']}."
    if res.get("handoff_url"):
        msg += f"\nFinish on the employer's site, then tap 'I've submitted' in Saige:\n{res['handoff_url']}"
    return msg


async def cmd_status(db: AsyncIOMotorDatabase, uid: str) -> str:
    counts: dict[str, int] = {}
    async for a in db[c.APPLICATIONS].find({"user_id": uid}, {"status": 1}):
        counts[a["status"]] = counts.get(a["status"], 0) + 1
    if not counts:
        return "No applications yet. Send *jobs* to start."
    rows = sorted(counts.items(), key=lambda kv: -kv[1])
    return "*Your pipeline*\n" + "\n".join(f"• {k.replace('_', ' ').title()}: {v}" for k, v in rows)


async def build_digest(db: AsyncIOMotorDatabase, uid: str) -> str:
    since = utcnow() - timedelta(days=1)
    new_jobs = await db[c.JOBS].count_documents({"user_id": uid, "created_at": {"$gte": since}})
    strong = await db[c.JOBS].count_documents({"user_id": uid, "created_at": {"$gte": since}, "match.overall": {"$gte": 75}})
    waiting = await db[c.APPLICATIONS].count_documents({"user_id": uid, "status": {"$in": ["READY_TO_APPLY", "APPROVAL_REQUIRED"]}})
    applied = await db[c.APPLICATIONS].count_documents({"user_id": uid, "applied_at": {"$gte": since}})
    due = await db[c.FOLLOWUPS].count_documents({"user_id": uid, "status": "due"})
    interviews = await db[c.INTERVIEWS].count_documents({"user_id": uid, "scheduled_at": {"$gte": utcnow(), "$lte": utcnow() + timedelta(days=7)}})
    return ("*Your Saige digest*\n"
            f"• New jobs (24h): {new_jobs} ({strong} strong)\n• Waiting for your approval: {waiting}\n• Applied (24h): {applied}\n"
            f"• Follow-ups due: {due}\n• Interviews this week: {interviews}\n\nSend *jobs* to see matches.")


async def cmd_pause(db: AsyncIOMotorDatabase, uid: str, pause: bool) -> str:
    from app.automation import service as auto

    s = await auto.get_settings_doc(db, uid)
    s.paused_all = pause
    await auto.save(db, uid, s, "automation.paused_all" if pause else "automation.resumed_all", {"paused_all": pause, "channel": "whatsapp"})
    return "⏸ All automation is paused." if pause else "▶ Automation resumed."


async def handle_command(db: AsyncIOMotorDatabase, uid: str, text: str) -> str:
    t = text.strip().lower()
    if t in {"jobs", "job", "matches"}:
        return await cmd_jobs(db, uid)
    m = re.fullmatch(r"apply\s*#?(\d{1,2})", t)
    if m:
        return await cmd_apply(db, uid, int(m.group(1)))
    if t in {"yes", "y", "approve"}:
        return await cmd_confirm(db, uid, True)
    if t in {"no", "n", "cancel"}:
        return await cmd_confirm(db, uid, False)
    if t == "status":
        return await cmd_status(db, uid)
    if t in {"digest", "summary", "today"}:
        return await build_digest(db, uid)
    if t in {"pause", "stop"}:
        return await cmd_pause(db, uid, True)
    if t in {"resume", "start"}:
        return await cmd_pause(db, uid, False)
    return HELP


async def handle_inbound(db: AsyncIOMotorDatabase, sender: str, text: str) -> str | None:
    """Returns the reply text (None = ignore the sender)."""
    phone = digits(sender)
    integ = await db[c.INTEGRATIONS].find_one({"provider": PROVIDER, "phone": phone}, sort=[("verified", DESCENDING)])
    if not integ:
        return None  # unknown numbers get no reply
    if not inbound_limiter.hit(f"wa:{phone}"):
        return None
    if not integ.get("verified"):
        if re.fullmatch(r"\d{6}", text.strip()) and await _verify(db, integ, text):
            return "✅ Saige AI is linked. " + HELP
        return "Reply with the 6-digit code Saige sent to link this number."
    uid = integ["user_id"]
    reply = await handle_command(db, uid, text)
    await log_action(db, user_id=uid, action="whatsapp.command", entity="integration", details={"command": text.strip().lower()[:30]})
    return reply


@webhook_router.get("/webhook")
async def webhook_verify(mode: str = Query("", alias="hub.mode"), token: str = Query("", alias="hub.verify_token"),
                         challenge: str = Query("", alias="hub.challenge")):
    s = get_settings()
    if mode == "subscribe" and s.whatsapp_verify_token and hmac.compare_digest(token, s.whatsapp_verify_token):
        return Response(challenge, media_type="text/plain")
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Verification failed")


@webhook_router.post("/webhook")
async def webhook(request: Request, db: AsyncIOMotorDatabase = Depends(db_dep)):
    body = await request.body()
    if not configured() or not valid_signature(body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid signature")
    try:
        payload = await request.json()
    except ValueError:
        return {"ok": True}
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            for msg in (change.get("value") or {}).get("messages") or []:
                if msg.get("type") != "text":
                    continue
                sender, text = msg.get("from", ""), (msg.get("text") or {}).get("body", "")
                try:
                    reply = await handle_inbound(db, sender, text)
                    if reply:
                        await send_text(sender, reply)
                except Exception:  # noqa: BLE001 - always 200 so Meta doesn't retry forever
                    logger.exception("WhatsApp inbound failed")
    return {"ok": True}


async def send_daily_digest(db: AsyncIOMotorDatabase, uid: str) -> bool:
    """Best effort: called from the morning report."""
    if not configured():
        return False
    integ = await db[c.INTEGRATIONS].find_one({"user_id": uid, "provider": PROVIDER, "verified": True})
    if not integ or not integ.get("digest", True):
        return False
    try:
        await send_text(integ["phone"], await build_digest(db, uid))
        await log_action(db, user_id=uid, action="whatsapp.digest_sent", entity="integration")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("WhatsApp digest failed", extra={"user_id": uid, "error": str(exc)[:200]})
        return False

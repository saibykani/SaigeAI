import logging
import secrets
from datetime import timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from pymongo import DESCENDING

from app.auth.deps import db_dep, get_current_user
from app.automation.service import is_allowed
from app.config import get_settings
from app.database import collections as c
from app.email import gmail, imap
from app.email import service as svc
from app.services import crypto
from app.services.agent_runs import agent_run
from app.services.audit import log_action
from app.services.notify import notify
from app.services.rate_limit import RateLimiter
from app.utils import new_id, utcnow

router = APIRouter(tags=["email"])
LINK_COOKIE = "saige_gmail_link"
LINK_PATH = "/api/auth/google"


class EmailIn(BaseModel):
    sender: str = Field(min_length=3, max_length=300)
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=20000)


# ------------------------------------------------------------------ Gmail connection

@router.post("/auth/connect/gmail")
async def connect_gmail(response: Response, user: dict = Depends(get_current_user)):
    """Returns Google's consent URL and sets a short-lived signed cookie binding the flow to this user."""
    s = get_settings()
    if not s.google_oauth_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google OAuth is not configured")
    state = secrets.token_urlsafe(24)
    link = jwt.encode({"sub": user["_id"], "state": state, "purpose": "gmail", "exp": utcnow() + timedelta(minutes=10)},
                      s.jwt_secret, algorithm=s.jwt_algorithm)
    response.set_cookie(LINK_COOKIE, link, max_age=600, httponly=True, secure=s.cookie_secure, samesite="lax", path=LINK_PATH)
    return {"url": gmail.authorization_url(state)}


async def complete_gmail_link(db: AsyncIOMotorDatabase, code: str, state: str, cookie: str | None) -> RedirectResponse:
    """Called from the shared Google OAuth callback when a Gmail link cookie is present."""
    s = get_settings()
    fail = RedirectResponse(f"{s.frontend_url}/integrations?gmail=error", status_code=302)
    try:
        claims = jwt.decode(cookie or "", s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.PyJWTError:
        return fail
    if claims.get("purpose") != "gmail" or not secrets.compare_digest(claims.get("state", ""), state):
        return fail
    try:
        tokens = await gmail.exchange_code(code)
    except (gmail.GmailError, KeyError):
        return fail
    if gmail.SCOPES[-1] not in tokens.get("scope", "") or not tokens.get("refresh_token"):
        return RedirectResponse(f"{s.frontend_url}/integrations?gmail=scope", status_code=302)
    uid = claims["sub"]
    now = utcnow()
    await db[c.INTEGRATIONS].update_one(
        {"user_id": uid, "provider": "gmail"},
        {"$set": {"email": tokens.get("email"), "scopes": tokens.get("scope", "").split(),
                  "refresh_token_enc": crypto.encrypt(tokens["refresh_token"]), "status": "connected",
                  "connected_at": now, "updated_at": now},
         "$setOnInsert": {"_id": new_id(), "user_id": uid, "last_sync_at": None}},
        upsert=True)
    await log_action(db, user_id=uid, action="integration.connected", entity="integration",
                     details={"provider": "gmail", "email": tokens.get("email")})
    resp = RedirectResponse(f"{s.frontend_url}/inbox?gmail=connected", status_code=302)
    resp.delete_cookie(LINK_COOKIE, path=LINK_PATH)
    return resp


class AppPasswordIn(BaseModel):
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    app_password: str = Field(min_length=16, max_length=40)


connect_limiter = RateLimiter(max_calls=5, window_seconds=300)


@router.post("/auth/connect/gmail-app-password")
async def connect_gmail_app_password(body: AppPasswordIn, user: dict = Depends(get_current_user),
                                     db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Connect Gmail with a Google App Password (no Google Cloud verification needed)."""
    if not connect_limiter.hit(f"gmail_app:{user['_id']}"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Wait a few minutes and try again.")
    address = body.email.strip().lower()
    try:
        await imap.verify(address, body.app_password)
    except gmail.GmailError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    now = utcnow()
    await db[c.INTEGRATIONS].update_one(
        {"user_id": user["_id"], "provider": "gmail"},
        {"$set": {"email": address, "method": "app_password", "scopes": ["imap.readonly"],
                  "app_password_enc": crypto.encrypt(imap.normalize_password(body.app_password)),
                  "refresh_token_enc": None, "status": "connected", "error": None, "connected_at": now, "updated_at": now},
         "$setOnInsert": {"_id": new_id(), "user_id": user["_id"], "last_sync_at": None}},
        upsert=True)
    await log_action(db, user_id=user["_id"], action="integration.connected", entity="integration",
                     details={"provider": "gmail", "method": "app_password", "email": address})
    return {"connected": True, "email": address}


@router.delete("/auth/connect/gmail", status_code=204)
async def disconnect_gmail(delete_emails: bool = False, user: dict = Depends(get_current_user),
                           db: AsyncIOMotorDatabase = Depends(db_dep)):
    integ = await db[c.INTEGRATIONS].find_one({"user_id": user["_id"], "provider": "gmail"})
    if integ and integ.get("refresh_token_enc"):
        try:
            await gmail.revoke(crypto.decrypt(integ["refresh_token_enc"]))
        except Exception:  # noqa: BLE001 - revocation is best effort; tokens are deleted regardless
            logging.getLogger(__name__).warning("Gmail token revocation failed; deleting the stored token anyway")
    await db[c.INTEGRATIONS].delete_one({"user_id": user["_id"], "provider": "gmail"})
    if delete_emails:
        await db[c.EMAILS].delete_many({"user_id": user["_id"]})
        await db[c.EMAIL_CLASSIFICATIONS].delete_many({"user_id": user["_id"]})
    await log_action(db, user_id=user["_id"], action="integration.disconnected", entity="integration",
                     details={"provider": "gmail", "emails_deleted": delete_emails})
    return Response(status_code=204)


# ------------------------------------------------------------------ emails

@router.get("/emails")
async def list_emails(category: str | None = None, limit: int = Query(100, ge=1, le=300),
                      user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    q: dict = {"user_id": user["_id"]}
    if category:
        q["category"] = category
    docs = await db[c.EMAILS].find(q).sort("received_at", DESCENDING).to_list(limit)
    return [svc.email_out(e) for e in docs]


@router.post("/emails/import", status_code=201)
async def import_email(body: EmailIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Paste an email (works without Gmail): classified and applied exactly like a synced one."""
    return svc.email_out(await svc.ingest(db, user["_id"], body.model_dump(), source="pasted"))


@router.post("/emails/sync")
async def sync_emails(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    integ = await db[c.INTEGRATIONS].find_one({"user_id": uid, "provider": "gmail"})
    if not integ:
        raise HTTPException(status.HTTP_409_CONFLICT, "Connect Gmail first")
    if not await is_allowed(db, uid, "gmail_sync"):
        raise HTTPException(status.HTTP_423_LOCKED, "Gmail sync is paused. Resume it in Automation settings.")
    return await run_sync(db, uid, integ)


async def run_sync(db: AsyncIOMotorDatabase, uid: str, integ: dict) -> dict:
    async with agent_run(db, "gmail_agent", uid, {"provider": "gmail"}) as run:
        try:
            known = {e["gmail_id"] async for e in db[c.EMAILS].find({"user_id": uid, "gmail_id": {"$ne": None}}, {"gmail_id": 1})}
            if integ.get("method") == "app_password":
                messages = await imap.fetch_messages(integ["email"], crypto.decrypt(integ["app_password_enc"]), skip=known)
            else:
                token = await gmail.access_token(crypto.decrypt(integ["refresh_token_enc"]))
                messages = await gmail.fetch_messages(token, skip=known)
        except gmail.GmailError as exc:
            run.errors.append(str(exc))
            await db[c.INTEGRATIONS].update_one({"_id": integ["_id"]}, {"$set": {"status": "error", "error": str(exc)}})
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
        counts: dict[str, int] = {}
        actions = 0
        for m in messages:
            doc = await svc.ingest(db, uid, m, source="gmail")
            counts[doc["category"]] = counts.get(doc["category"], 0) + 1
            if doc.get("action"):
                actions += 1
                run.action(f"{doc['category']} -> {doc['action']}")
        run.output = {"fetched": len(messages), "by_category": counts, "status_updates": actions}
    await db[c.INTEGRATIONS].update_one({"_id": integ["_id"]}, {"$set": {"last_sync_at": utcnow(), "status": "connected", "error": None}})
    if actions:
        await notify(db, user_id=uid, kind="gmail_sync", title=f"Gmail: {actions} application update(s) detected", link="/inbox")
    return run.output


@router.delete("/emails", status_code=204)
async def delete_emails(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    await db[c.EMAILS].delete_many({"user_id": user["_id"]})
    await db[c.EMAIL_CLASSIFICATIONS].delete_many({"user_id": user["_id"]})
    return Response(status_code=204)


# ------------------------------------------------------------------ integrations overview

@router.get("/integrations")
async def integrations(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    s = get_settings()
    g = await db[c.INTEGRATIONS].find_one({"user_id": uid, "provider": "gmail"})
    boards = await db[c.JOB_SOURCES].count_documents({"user_id": uid})
    li = await db[c.LINKEDIN_PROFILES].find_one({"user_id": uid})
    nk = await db[c.NAUKRI_PROFILES].find_one({"user_id": uid})
    return {
        "google": {"connected": bool(user.get("google_sub")), "available": s.google_oauth_enabled},
        "gmail": {"connected": bool(g), "available": s.google_oauth_enabled, "email": g.get("email") if g else None,
                  "method": (g.get("method") or "oauth") if g else None,
                  "status": g.get("status") if g else "not_connected", "error": g.get("error") if g else None,
                  "last_sync_at": g["last_sync_at"].isoformat() if g and g.get("last_sync_at") else None},
        "linkedin": {"snapshot": bool(li), "mode": "copy-ready updates"},
        "naukri": {"snapshot": bool(nk), "mode": "copy-ready updates"},
        "ats_boards": {"count": boards},
        "claude": {"enabled": s.llm_enabled, "model": s.llm_model if s.llm_enabled else None},
    }

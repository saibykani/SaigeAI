"""Web Push (phone notifications from the installed PWA). Standard VAPID + aes128gcm, built on py-vapid and http-ece
(pure Python over `cryptography`), sent with httpx. Every notify() is mirrored to the user's subscribed devices; dead
subscriptions (404/410) are removed. Needs VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY (see docs/DEPLOYMENT.md)."""

import base64
import json
import logging
import os
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.auth.deps import db_dep, get_current_user
from app.config import get_settings
from app.database import collections as c
from app.services.audit import log_action
from app.utils import new_id, utcnow

logger = logging.getLogger("saige.webpush")
router = APIRouter(prefix="/integrations/push", tags=["integrations"])


def http_client() -> httpx.AsyncClient:
    """Factory (patched in tests)."""
    return httpx.AsyncClient(timeout=10)


def configured() -> bool:
    s = get_settings()
    return bool(s.vapid_public_key and s.vapid_private_key)


def _b64d(v: str) -> bytes:
    return base64.urlsafe_b64decode(v + "=" * (-len(v) % 4))


def encrypt(payload: bytes, p256dh: str, auth: str) -> bytes:
    import http_ece
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    return http_ece.encrypt(payload, salt=os.urandom(16), private_key=key, dh=_b64d(p256dh), auth_secret=_b64d(auth),
                            version="aes128gcm")


def vapid_headers(endpoint: str) -> dict:
    from py_vapid import Vapid02

    s = get_settings()
    u = urlparse(endpoint)
    v = Vapid02.from_string(private_key=s.vapid_private_key)
    return v.sign({"aud": f"{u.scheme}://{u.netloc}", "sub": s.vapid_subject})


async def send_one(sub: dict, data: dict) -> int:
    """Sends one push; returns the push service HTTP status."""
    keys = sub.get("keys") or {}
    body = encrypt(json.dumps(data).encode(), keys["p256dh"], keys["auth"])
    headers = {**vapid_headers(sub["endpoint"]), "Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream",
               "TTL": "86400", "Urgency": "normal"}
    async with http_client() as client:
        r = await client.post(sub["endpoint"], content=body, headers=headers)
    return r.status_code


async def push_user(db: AsyncIOMotorDatabase, user_id: str, data: dict) -> int:
    """Sends `data` to every subscription of the user. Returns how many were delivered; prunes gone subscriptions."""
    if not configured():
        return 0
    sent = 0
    async for sub in db[c.PUSH_SUBSCRIPTIONS].find({"user_id": user_id}):
        try:
            code = await send_one(sub, data)
        except Exception as e:  # noqa: BLE001 - best effort
            logger.warning("push failed: %s", e)
            continue
        if code in (404, 410):
            await db[c.PUSH_SUBSCRIPTIONS].delete_one({"_id": sub["_id"]})
        elif code < 300:
            sent += 1
    return sent


async def mirror(db: AsyncIOMotorDatabase, user_id: str, title: str, body: str, link: str | None, kind: str = "") -> None:
    """Best effort: never raises (the in-app notification already exists)."""
    try:
        await push_user(db, user_id, {"title": title, "body": (body or "")[:300], "link": link or "/notifications", "tag": kind or None})
    except Exception as e:  # noqa: BLE001
        logger.warning("push mirror failed: %s", e)


class SubKeys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=200)
    auth: str = Field(min_length=8, max_length=100)


class SubscribeIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)
    keys: SubKeys
    device: str | None = Field(default=None, max_length=200)


class UnsubscribeIn(BaseModel):
    endpoint: str | None = Field(default=None, max_length=1000)


@router.get("/public-key")
async def public_key():
    return {"configured": configured(), "public_key": get_settings().vapid_public_key if configured() else None}


@router.get("")
async def status_(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    n = await db[c.PUSH_SUBSCRIPTIONS].count_documents({"user_id": user["_id"]})
    return {"configured": configured(), "devices": n}


@router.post("/subscribe")
async def subscribe(body: SubscribeIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    if not body.endpoint.startswith("https://"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Push endpoint must be https")
    await db[c.PUSH_SUBSCRIPTIONS].update_one(
        {"user_id": user["_id"], "endpoint": body.endpoint},
        {"$set": {"keys": body.keys.model_dump(), "device": body.device, "updated_at": utcnow()},
         "$setOnInsert": {"_id": new_id(), "created_at": utcnow()}},
        upsert=True,
    )
    await log_action(db, user_id=user["_id"], action="push_subscribed", entity="push_subscription", details={"device": body.device})
    return {"subscribed": True, "devices": await db[c.PUSH_SUBSCRIPTIONS].count_documents({"user_id": user["_id"]})}


@router.delete("/subscribe")
async def unsubscribe(body: UnsubscribeIn | None = None, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    q = {"user_id": user["_id"]}
    if body and body.endpoint:
        q["endpoint"] = body.endpoint
    r = await db[c.PUSH_SUBSCRIPTIONS].delete_many(q)
    await log_action(db, user_id=user["_id"], action="push_unsubscribed", entity="push_subscription", details={"removed": r.deleted_count})
    return {"removed": r.deleted_count}


@router.post("/test")
async def test(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    if not configured():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Web push is not configured on the server (VAPID keys missing)")
    sent = await push_user(db, user["_id"], {"title": "Saige AI", "body": "Phone notifications are working.", "link": "/dashboard"})
    return {"sent": sent}

"""User and session management with rotating refresh tokens."""

from datetime import timedelta

from fastapi import HTTPException, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.auth.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_opaque_token,
    verify_password,
)
from app.config import get_settings
from app.database import collections as c
from app.services.audit import log_action
from app.utils import as_utc, new_id, utcnow

REFRESH_COOKIE = "saige_refresh"
REFRESH_COOKIE_PATH = "/api/auth"
# A rotated refresh token presented again within this window is a concurrent-refresh race
# (two tabs, a quick reload), not theft.
ROTATION_GRACE_SECONDS = 60


def user_out(user: dict) -> dict:
    providers = []
    if user.get("password_hash"):
        providers.append("password")
    if user.get("google_sub"):
        providers.append("google")
    return {
        "id": user["_id"],
        "email": user["email"],
        "name": user.get("name", ""),
        "roles": user.get("roles", ["user"]),
        "auth_providers": providers,
    }


async def create_user(
    db: AsyncIOMotorDatabase, *, email: str, name: str, password: str | None = None,
    google_sub: str | None = None,
) -> dict:
    now = utcnow()
    user = {
        "_id": new_id(),
        "email": email.lower(),
        "name": name,
        "password_hash": hash_password(password) if password else None,
        "roles": ["user"],
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    if google_sub:
        user["google_sub"] = google_sub
    if await db[c.USERS].find_one({"email": user["email"]}):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    try:
        await db[c.USERS].insert_one(user)
    except DuplicateKeyError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Account already exists") from exc
    await log_action(db, user_id=user["_id"], action="user.registered", entity="user",
                     entity_id=user["_id"], details={"provider": "google" if google_sub else "password"})
    return user


async def authenticate(db: AsyncIOMotorDatabase, email: str, password: str) -> dict:
    user = await db[c.USERS].find_one({"email": email.lower()})
    # Always run a hash check to reduce user-enumeration timing differences.
    ok = verify_password(password, user.get("password_hash") if user else None)
    if not user or not ok or not user.get("is_active", True):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return user


def _set_refresh_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        REFRESH_COOKIE, token, max_age=s.refresh_token_days * 86400, httponly=True,
        secure=s.cookie_secure, samesite="strict", path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)


async def issue_session(
    db: AsyncIOMotorDatabase, user: dict, response: Response, family_id: str | None = None
) -> dict:
    s = get_settings()
    refresh = new_opaque_token()
    await db[c.REFRESH_TOKENS].insert_one({
        "_id": hash_token(refresh),
        "user_id": user["_id"],
        "family_id": family_id or new_id(),
        "revoked": False,
        "created_at": utcnow(),
        "expires_at": utcnow() + timedelta(days=s.refresh_token_days),
    })
    _set_refresh_cookie(response, refresh)
    access, expires_in = create_access_token(user["_id"], user.get("roles", ["user"]))
    return {"access_token": access, "token_type": "bearer", "expires_in": expires_in}


async def rotate_session(db: AsyncIOMotorDatabase, refresh: str | None, response: Response) -> dict:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    if not refresh:
        raise unauthorized
    record = await db[c.REFRESH_TOKENS].find_one({"_id": hash_token(refresh)})
    if not record:
        raise unauthorized
    if record["revoked"]:
        rotated_at = record.get("rotated_at")
        benign_race = (rotated_at is not None and not record.get("family_revoked")
                       and utcnow() - as_utc(rotated_at) < timedelta(seconds=ROTATION_GRACE_SECONDS))
        if benign_race:
            # Two tabs (or a fast reload) refreshed with the same cookie at once: not theft.
            user = await db[c.USERS].find_one({"_id": record["user_id"], "is_active": True})
            if not user:
                raise unauthorized
            return await issue_session(db, user, response, family_id=record["family_id"])
        # Reuse of a rotated token outside the grace window: assume theft, revoke the family.
        await db[c.REFRESH_TOKENS].update_many(
            {"family_id": record["family_id"]}, {"$set": {"revoked": True, "family_revoked": True}}
        )
        await log_action(db, user_id=record["user_id"], action="auth.refresh_token_reuse",
                         entity="session", entity_id=record["family_id"])
        raise unauthorized
    if as_utc(record["expires_at"]) < utcnow():
        raise unauthorized
    user = await db[c.USERS].find_one({"_id": record["user_id"], "is_active": True})
    if not user:
        raise unauthorized
    await db[c.REFRESH_TOKENS].update_one({"_id": record["_id"]},
                                          {"$set": {"revoked": True, "rotated_at": utcnow()}})
    return await issue_session(db, user, response, family_id=record["family_id"])


async def revoke_session(db: AsyncIOMotorDatabase, refresh: str | None) -> None:
    if not refresh:
        return
    record = await db[c.REFRESH_TOKENS].find_one({"_id": hash_token(refresh)})
    if record:
        await db[c.REFRESH_TOKENS].update_many(
            {"family_id": record["family_id"]}, {"$set": {"revoked": True, "family_revoked": True}}
        )

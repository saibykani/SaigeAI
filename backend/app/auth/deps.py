"""FastAPI dependencies for authentication, RBAC and CSRF protection."""

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.security import decode_access_token
from app.database import collections as c
from app.database.mongo import get_db

_bearer = HTTPBearer(auto_error=False)

CSRF_HEADER = "X-Requested-With"
CSRF_VALUE = "saige"


def db_dep() -> AsyncIOMotorDatabase:
    return get_db()


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> dict:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers={"WWW-Authenticate": "Bearer"}
    )
    if creds is None:
        raise unauthorized
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.PyJWTError as exc:
        raise unauthorized from exc
    user = await db[c.USERS].find_one({"_id": payload["sub"], "is_active": True})
    if not user:
        raise unauthorized
    return user


def require_role(role: str):
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if role not in user.get("roles", []):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return _check


async def require_csrf_header(
    x_requested_with: str | None = Header(default=None, alias=CSRF_HEADER),
) -> None:
    """Cookie-authenticated endpoints require a custom header, which a cross-site form or
    simple request cannot set without a CORS preflight (defence in depth with SameSite)."""
    if x_requested_with != CSRF_VALUE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing CSRF header")

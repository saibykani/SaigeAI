"""Password hashing and token primitives."""

import hashlib
import secrets
from datetime import timedelta

import bcrypt
import jwt

from app.config import get_settings
from app.utils import new_id, utcnow


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: str, roles: list[str]) -> tuple[str, int]:
    s = get_settings()
    now = utcnow()
    expires_in = s.access_token_minutes * 60
    payload = {
        "sub": user_id,
        "roles": roles,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        "jti": new_id(),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm), expires_in


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError on any invalid / expired token."""
    s = get_settings()
    payload = jwt.decode(
        token, s.jwt_secret, algorithms=[s.jwt_algorithm], options={"require": ["exp", "sub"]}
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return payload


def new_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

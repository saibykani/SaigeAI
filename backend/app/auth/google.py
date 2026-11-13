"""Google OAuth 2.0 authorization-code flow (sign-in only; Gmail scopes arrive in Phase 5)."""

import time
from urllib.parse import urlencode

import httpx
import jwt

from app.config import get_settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - public endpoint, not a secret
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SIGNIN_SCOPES = ["openid", "email", "profile"]


def authorization_url(state: str) -> str:
    s = get_settings()
    params = {
        "client_id": s.google_client_id,
        "redirect_uri": s.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SIGNIN_SCOPES),
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    """Exchange the authorization code and return the verified OpenID userinfo."""
    s = get_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(TOKEN_URL, data={
            "code": code,
            "client_id": s.google_client_id,
            "client_secret": s.google_client_secret,
            "redirect_uri": s.google_redirect_uri,
            "grant_type": "authorization_code",
        })
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]
        info = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        info.raise_for_status()
        # Google access token is discarded; we only needed identity for sign-in.
        return info.json()


# ---------------------------------------------------------------- ID token (native mobile sign-in)

CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("accounts.google.com", "https://accounts.google.com")
_jwks_cache: dict = {"keys": None, "at": 0.0}
_JWKS_TTL = 3600.0


class InvalidIdToken(Exception):
    pass


async def _jwks(force: bool = False) -> list[dict]:
    now = time.monotonic()
    if force or not _jwks_cache["keys"] or now - _jwks_cache["at"] > _JWKS_TTL:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(CERTS_URL)
            resp.raise_for_status()
            _jwks_cache.update(keys=resp.json()["keys"], at=now)
    return _jwks_cache["keys"]


async def verify_id_token(id_token: str) -> dict:
    """Verify a Google ID token (RS256, Google's public certs) and return its claims.

    Checks signature, exp, iss, aud == GOOGLE_CLIENT_ID (the web client id) and email_verified.
    Raises InvalidIdToken on any problem; httpx errors propagate if the certs cannot be fetched."""
    s = get_settings()
    if not s.google_client_id:
        raise InvalidIdToken("not configured")
    try:
        kid = jwt.get_unverified_header(id_token).get("kid")
    except jwt.PyJWTError as e:
        raise InvalidIdToken("malformed") from e
    key = next((k for k in await _jwks() if k.get("kid") == kid), None)
    if key is None:  # Google rotates keys: refresh once
        key = next((k for k in await _jwks(force=True) if k.get("kid") == kid), None)
    if key is None:
        raise InvalidIdToken("unknown key")
    try:
        claims = jwt.decode(id_token, jwt.PyJWK(key).key, algorithms=["RS256"], audience=s.google_client_id,
                            options={"require": ["exp", "iss", "aud", "sub"]}, leeway=30)
    except jwt.PyJWTError as e:
        raise InvalidIdToken(str(e)) from e
    if claims.get("iss") not in ISSUERS:
        raise InvalidIdToken("bad issuer")
    if claims.get("email_verified") not in (True, "true") or not claims.get("email"):
        raise InvalidIdToken("email not verified")
    return claims

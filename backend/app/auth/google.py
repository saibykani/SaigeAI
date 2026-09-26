"""Google OAuth 2.0 authorization-code flow (sign-in only; Gmail scopes arrive in Phase 5)."""

from urllib.parse import urlencode

import httpx

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

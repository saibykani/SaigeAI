"""Gmail API client (official OAuth, read-only scope). Nothing here sends, deletes or modifies mail."""

import base64
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.jobs.jd_parser import html_to_text

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - public endpoint
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
API = "https://gmail.googleapis.com/gmail/v1/users/me"
SCOPES = ["openid", "email", "https://www.googleapis.com/auth/gmail.readonly"]
# Only job-search mail: skip promotions/social, look back 30 days.
DEFAULT_QUERY = "newer_than:30d -category:promotions -category:social"


class GmailError(Exception):
    pass


def http_client() -> httpx.AsyncClient:
    """Factory (patched in tests)."""
    return httpx.AsyncClient(timeout=20)


def authorization_url(state: str) -> str:
    s = get_settings()
    return f"{AUTH_URL}?" + urlencode({
        "client_id": s.google_client_id, "redirect_uri": s.google_redirect_uri, "response_type": "code",
        "scope": " ".join(SCOPES), "state": state, "access_type": "offline", "prompt": "consent",
        "include_granted_scopes": "true",
    })


async def exchange_code(code: str) -> dict:
    s = get_settings()
    async with http_client() as c:
        r = await c.post(TOKEN_URL, data={"code": code, "client_id": s.google_client_id,
                                          "client_secret": s.google_client_secret,
                                          "redirect_uri": s.google_redirect_uri, "grant_type": "authorization_code"})
        if r.status_code != 200:
            raise GmailError("Google rejected the authorization code")
        tokens = r.json()
        info = await c.get(USERINFO_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"})
        tokens["email"] = info.json().get("email") if info.status_code == 200 else None
        return tokens


async def access_token(refresh_token: str) -> str:
    s = get_settings()
    async with http_client() as c:
        r = await c.post(TOKEN_URL, data={"client_id": s.google_client_id, "client_secret": s.google_client_secret,
                                          "refresh_token": refresh_token, "grant_type": "refresh_token"})
    if r.status_code != 200:
        raise GmailError("Gmail access was revoked or expired - reconnect Gmail")
    return r.json()["access_token"]


async def revoke(token: str) -> None:
    async with http_client() as c:
        await c.post(REVOKE_URL, data={"token": token})


def _header(headers: list[dict], name: str) -> str:
    return next((h["value"] for h in headers if h["name"].lower() == name.lower()), "")


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def _body(payload: dict) -> str:
    """Prefer text/plain; fall back to text/html converted to text."""
    plain, html = [], []

    def walk(part: dict) -> None:
        mime = part.get("mimeType", "")
        data = (part.get("body") or {}).get("data")
        if data and mime == "text/plain":
            plain.append(_decode(data))
        elif data and mime == "text/html":
            html.append(_decode(data))
        for p in part.get("parts", []) or []:
            walk(p)

    walk(payload)
    if plain:
        return "\n".join(plain)
    return html_to_text("\n".join(html)) if html else ""


async def fetch_messages(token: str, query: str = DEFAULT_QUERY, limit: int = 50, skip: set[str] | None = None) -> list[dict]:
    skip = skip or set()
    headers = {"Authorization": f"Bearer {token}"}
    async with http_client() as c:
        r = await c.get(f"{API}/messages", params={"q": query, "maxResults": limit}, headers=headers)
        if r.status_code != 200:
            raise GmailError(f"Gmail list failed (HTTP {r.status_code})")
        out = []
        for m in r.json().get("messages", []):
            if m["id"] in skip:
                continue
            d = await c.get(f"{API}/messages/{m['id']}", params={"format": "full"}, headers=headers)
            if d.status_code != 200:
                continue
            msg = d.json()
            hs = msg.get("payload", {}).get("headers", [])
            out.append({
                "gmail_id": msg["id"], "thread_id": msg.get("threadId"), "sender": _header(hs, "From"),
                "subject": _header(hs, "Subject"), "body": _body(msg.get("payload", {}))[:20000],
                "received_ms": int(msg.get("internalDate", "0")), "snippet": msg.get("snippet", ""),
            })
        return out

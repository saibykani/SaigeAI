"""LinkedIn's official API for posting on the member's behalf ("Share on LinkedIn", scope w_member_social).

Setup (once, by the app owner): create an app at https://www.linkedin.com/developers/apps, add the products
"Sign In with LinkedIn using OpenID Connect" and "Share on LinkedIn", add the redirect URL
{FRONTEND_URL}/api/linkedin/callback, and set LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET.
Reading comments or post analytics needs LinkedIn partner access (r_member_social), which self-serve
apps don't get, so comments are handled with the browser extension instead.
"""

from urllib.parse import urlencode

import httpx

from app.config import get_settings

AUTH = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN = "https://www.linkedin.com/oauth/v2/accessToken"  # noqa: S105 - URL, not a secret
API = "https://api.linkedin.com"
SCOPES = "openid profile email w_member_social"


class LinkedInError(RuntimeError):
    pass


def http_client() -> httpx.AsyncClient:
    """Factory (patched in tests)."""
    return httpx.AsyncClient(timeout=40)


def enabled() -> bool:
    s = get_settings()
    return bool(s.linkedin_client_id and s.linkedin_client_secret)


def redirect_uri() -> str:
    return get_settings().frontend_url.rstrip("/") + "/api/linkedin/callback"


def authorize_url(state: str) -> str:
    s = get_settings()
    return f"{AUTH}?" + urlencode({"response_type": "code", "client_id": s.linkedin_client_id, "redirect_uri": redirect_uri(),
                                   "state": state, "scope": SCOPES})


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "LinkedIn-Version": get_settings().linkedin_api_version,
            "X-Restli-Protocol-Version": "2.0.0", "Content-Type": "application/json"}


async def exchange(code: str) -> dict:
    s = get_settings()
    async with http_client() as c:
        r = await c.post(TOKEN, data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri(),
                                      "client_id": s.linkedin_client_id, "client_secret": s.linkedin_client_secret})
        if r.status_code != 200:
            raise LinkedInError(f"LinkedIn sign-in failed ({r.status_code})")
        tok = r.json()
        me = await c.get(f"{API}/v2/userinfo", headers={"Authorization": f"Bearer {tok['access_token']}"})
        if me.status_code != 200:
            raise LinkedInError("Couldn't read your LinkedIn profile id")
    info = me.json()
    return {"access_token": tok["access_token"], "expires_in": tok.get("expires_in", 5184000), "sub": info["sub"],
            "name": info.get("name"), "email": info.get("email")}


async def _upload(c: httpx.AsyncClient, token: str, kind: str, owner: str, data: bytes) -> str:
    """kind: "images" or "documents". Returns the asset URN."""
    r = await c.post(f"{API}/rest/{kind}?action=initializeUpload", headers=_headers(token),
                     json={"initializeUploadRequest": {"owner": owner}})
    if r.status_code >= 300:
        raise LinkedInError(f"LinkedIn upload init failed ({r.status_code}): {r.text[:160]}")
    v = r.json()["value"]
    up = await c.put(v["uploadUrl"], content=data, headers={"Authorization": f"Bearer {token}"})
    if up.status_code >= 300:
        raise LinkedInError(f"LinkedIn upload failed ({up.status_code})")
    return v.get("image") or v.get("document")


async def publish(token: str, sub: str, text: str, *, image: bytes | None = None, document: bytes | None = None,
                  doc_title: str = "Carousel", alt: str = "") -> str:
    """Create a public post; returns its URN (e.g. urn:li:share:123)."""
    author = f"urn:li:person:{sub}"
    body: dict = {"author": author, "commentary": text, "visibility": "PUBLIC", "lifecycleState": "PUBLISHED",
                  "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
                  "isReshareDisabledByAuthor": False}
    async with http_client() as c:
        if document:
            urn = await _upload(c, token, "documents", author, document)
            body["content"] = {"media": {"title": doc_title[:100], "id": urn}}
        elif image:
            urn = await _upload(c, token, "images", author, image)
            body["content"] = {"media": {"id": urn, "altText": alt[:300]}}
        r = await c.post(f"{API}/rest/posts", headers=_headers(token), json=body)
    if r.status_code not in (200, 201):
        raise LinkedInError(f"LinkedIn rejected the post ({r.status_code}): {r.text[:200]}")
    return r.headers.get("x-restli-id") or r.headers.get("x-linkedin-id") or ""


def share_url(text: str) -> str:
    """Manual fallback: opens LinkedIn's composer with the text filled in."""
    return "https://www.linkedin.com/feed/?" + urlencode({"shareActive": "true", "text": text[:2800]})

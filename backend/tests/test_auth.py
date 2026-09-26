from app.auth.service import REFRESH_COOKIE
from app.database import collections as c
from app.services.rate_limit import auth_limiter
from tests.conftest import CSRF, register


async def test_register_and_me(client):
    headers = await register(client)
    r = await client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "asha@example.com"
    assert body["auth_providers"] == ["password"]
    assert "password_hash" not in body


async def test_password_is_hashed_not_stored(client, db):
    await register(client)
    user = await db[c.USERS].find_one({"email": "asha@example.com"})
    assert user["password_hash"] != "correct-horse-battery"
    assert user["password_hash"].startswith("$2")


async def test_duplicate_email_rejected(client):
    await register(client)
    r = await client.post("/api/auth/register", json={
        "email": "ASHA@example.com", "password": "another-password", "name": "X"})
    assert r.status_code == 409


async def test_login_wrong_password(client):
    await register(client)
    r = await client.post("/api/auth/login",
                          json={"email": "asha@example.com", "password": "wrong-password"})
    assert r.status_code == 401


async def test_login_success(client):
    await register(client)
    r = await client.post("/api/auth/login",
                          json={"email": "asha@example.com", "password": "correct-horse-battery"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"


async def test_short_password_rejected(client):
    r = await client.post("/api/auth/register",
                          json={"email": "a@example.com", "password": "short", "name": "A"})
    assert r.status_code == 422


async def test_protected_route_requires_token(client):
    assert (await client.get("/api/profile")).status_code == 401
    r = await client.get("/api/profile", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


async def test_refresh_requires_csrf_header(client):
    await register(client)
    r = await client.post("/api/auth/refresh")
    assert r.status_code == 403


async def test_refresh_rotates_token(client):
    await register(client)
    first = client.cookies.get(REFRESH_COOKIE)
    r = await client.post("/api/auth/refresh", headers=CSRF)
    assert r.status_code == 200, r.text
    second = client.cookies.get(REFRESH_COOKIE)
    assert first and second and first != second
    me = await client.get("/api/auth/me",
                          headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.status_code == 200


async def test_concurrent_refresh_within_grace_is_not_theft(client):
    """Two tabs refreshing with the same cookie at the same moment must not sign the user out."""
    await register(client)
    same = client.cookies.get(REFRESH_COOKIE)
    assert (await client.post("/api/auth/refresh", headers=CSRF)).status_code == 200
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, same, path="/api/auth")
    assert (await client.post("/api/auth/refresh", headers=CSRF)).status_code == 200


async def test_refresh_token_reuse_after_grace_revokes_family(client, db):
    await register(client)
    stolen = client.cookies.get(REFRESH_COOKIE)
    assert (await client.post("/api/auth/refresh", headers=CSRF)).status_code == 200
    legit = client.cookies.get(REFRESH_COOKIE)
    # Age the rotation beyond the grace window, as if the old token leaked and is replayed later.
    from datetime import timedelta

    from app.auth.security import hash_token
    from app.utils import utcnow
    await db[c.REFRESH_TOKENS].update_one({"_id": hash_token(stolen)},
                                          {"$set": {"rotated_at": utcnow() - timedelta(minutes=5)}})

    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, stolen, path="/api/auth")
    assert (await client.post("/api/auth/refresh", headers=CSRF)).status_code == 401

    # The legitimate (newer) token is now revoked too.
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, legit, path="/api/auth")
    assert (await client.post("/api/auth/refresh", headers=CSRF)).status_code == 401


async def test_logout_revokes_session(client):
    await register(client)
    token = client.cookies.get(REFRESH_COOKIE)
    assert (await client.post("/api/auth/logout", headers=CSRF)).status_code == 204
    client.cookies.set(REFRESH_COOKIE, token, path="/api/auth")
    assert (await client.post("/api/auth/refresh", headers=CSRF)).status_code == 401


async def test_login_rate_limited(client):
    auth_limiter.reset()
    codes = []
    for _ in range(12):
        r = await client.post("/api/auth/login",
                              json={"email": "nobody@example.com", "password": "whatever-pass"})
        codes.append(r.status_code)
    assert 429 in codes


async def test_google_not_configured(client):
    r = await client.get("/api/auth/google/authorize", follow_redirects=False)
    assert r.status_code == 503


async def test_connections_never_expose_credentials(client, auth):
    r = await client.get("/api/auth/connections", headers=auth)
    assert r.status_code == 200
    providers = {x["provider"]: x for x in r.json()}
    assert set(providers) == {"google", "gmail", "linkedin", "naukri"}
    assert all(not x["connected"] for x in r.json())


async def test_audit_log_redacts_secrets(client, db, auth):
    logs = await db[c.AUDIT_LOGS].find({}).to_list(length=None)
    assert logs
    assert "correct-horse-battery" not in str(logs)


async def test_google_callback_denied_redirects_to_login(client):
    r = await client.get("/api/auth/google/callback", params={"error": "access_denied"}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].endswith("/login?error=google_denied")
    r = await client.get("/api/auth/google/callback", follow_redirects=False)
    assert r.status_code == 302

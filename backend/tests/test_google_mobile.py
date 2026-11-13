import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth import google
from app.config import get_settings
from app.database import collections as c
from tests.conftest import register

URL = "/api/auth/google/mobile"
TOKEN = "x" * 40


@pytest.fixture
def claims(monkeypatch):
    data = {"sub": "g-1", "email": "new@example.com", "email_verified": True, "name": "New Person"}

    async def fake(_t):
        return data

    monkeypatch.setattr(google, "verify_id_token", fake)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "web-client")
    get_settings.cache_clear()
    yield data
    get_settings.cache_clear()


async def test_creates_user_and_session(client, db, claims):
    r = await client.post(URL, json={"id_token": TOKEN, "role": "recruiter"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert "saige_refresh" in r.headers.get("set-cookie", "")
    u = await db[c.USERS].find_one({"email": "new@example.com"})
    assert u["google_sub"] == "g-1" and u["role"] == "recruiter"
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["email"] == "new@example.com"


async def test_links_existing_email_account(client, db, claims):
    await register(client)
    claims.update(email="asha@example.com", sub="g-2")
    r = await client.post(URL, json={"id_token": TOKEN, "role": "recruiter"})
    assert r.status_code == 200
    u = await db[c.USERS].find_one({"email": "asha@example.com"})
    assert u["google_sub"] == "g-2" and u.get("role") != "recruiter"


async def test_disabled_user_rejected(client, db, claims):
    await register(client)
    await db[c.USERS].update_one({"email": "asha@example.com"}, {"$set": {"is_active": False}})
    claims.update(email="asha@example.com")
    assert (await client.post(URL, json={"id_token": TOKEN})).status_code == 403


async def test_invalid_token_401(client, monkeypatch):
    async def bad(_t):
        raise google.InvalidIdToken("nope")

    monkeypatch.setattr(google, "verify_id_token", bad)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "web-client")
    get_settings.cache_clear()
    assert (await client.post(URL, json={"id_token": TOKEN})).status_code == 401
    get_settings.cache_clear()


async def test_verify_id_token_checks(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "web-client")
    get_settings.cache_clear()
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True) | {"kid": "k1", "alg": "RS256"}

    async def keys(force=False):
        return [jwk]

    monkeypatch.setattr(google, "_jwks", keys)

    def make(**over):
        p = {"iss": "https://accounts.google.com", "aud": "web-client", "sub": "s", "email": "a@b.com",
             "email_verified": True, "exp": int(time.time()) + 600} | over
        return jwt.encode(p, key, algorithm="RS256", headers={"kid": "k1"})

    assert (await google.verify_id_token(make()))["email"] == "a@b.com"
    for bad in (make(aud="other"), make(iss="evil.com"), make(email_verified=False), make(exp=int(time.time()) - 600)):
        with pytest.raises(google.InvalidIdToken):
            await google.verify_id_token(bad)
    get_settings.cache_clear()

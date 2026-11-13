
from app.config import get_settings
from app.database import collections as c
from app.services import webpush
from app.services.notify import notify


async def test_push_subscribe_send_and_prune(client, auth, db, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "vapid_public_key", "pub")
    monkeypatch.setattr(s, "vapid_private_key", "priv")
    calls = []
    status_code = {"v": 201}

    async def fake_send(sub, data):
        calls.append((sub["endpoint"], data))
        return status_code["v"]

    monkeypatch.setattr(webpush, "send_one", fake_send)
    assert (await client.get("/api/integrations/push/public-key")).json()["public_key"] == "pub"
    body = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "k" * 20, "auth": "a" * 10}}
    assert (await client.post("/api/integrations/push/subscribe", json=body, headers=auth)).json()["devices"] == 1
    uid = (await db[c.USERS].find_one({}))["_id"]
    await notify(db, user_id=uid, kind="x", title="Hello", body="B", link="/jobs")
    assert calls and calls[0][1]["title"] == "Hello"
    assert (await client.post("/api/integrations/push/test", headers=auth)).json()["sent"] == 1
    status_code["v"] = 410
    await notify(db, user_id=uid, kind="x", title="Gone")
    assert await db[c.PUSH_SUBSCRIPTIONS].count_documents({}) == 0
    await client.post("/api/integrations/push/subscribe", json=body, headers=auth)
    r = await client.request("DELETE", "/api/integrations/push/subscribe", json={"endpoint": body["endpoint"]}, headers=auth)
    assert r.json()["removed"] == 1


async def test_real_encrypt_and_vapid_roundtrip():
    import base64

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from py_vapid import Vapid02

    k = ec.generate_private_key(ec.SECP256R1())
    pub = k.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    b64 = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")  # noqa: E731
    assert webpush.encrypt(b'{"a":1}', b64(pub), b64(b"0123456789abcdef"))
    v = Vapid02()
    v.generate_keys()
    s = get_settings()
    s.vapid_private_key = b64(v.private_key.private_numbers().private_value.to_bytes(32, "big"))
    try:
        assert "Authorization" in webpush.vapid_headers("https://push.example/x")
    finally:
        s.vapid_private_key = None

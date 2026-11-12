"""Saige on WhatsApp (Cloud API): linking, signed webhook, commands, approval by "yes"."""

import hashlib
import hmac
import json

import pytest

from app.config import get_settings
from app.database import collections as c
from app.services import whatsapp_cloud as wa
from tests.test_email import PROFILE, SDET_JD

SECRET = "app-secret"


class FakeResp:
    status_code = 200


class FakeClient:
    sent: list = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None):
        FakeClient.sent.append(json)
        return FakeResp()


@pytest.fixture
def configured(monkeypatch):
    s = get_settings()
    for k, v in {"whatsapp_token": "tok", "whatsapp_phone_number_id": "123", "whatsapp_verify_token": "vt", "whatsapp_app_secret": SECRET}.items():
        monkeypatch.setattr(s, k, v)
    FakeClient.sent = []
    monkeypatch.setattr(wa, "http_client", lambda: FakeClient())
    wa.inbound_limiter.reset()
    wa.code_limiter.reset()


async def inbound(client, text, sender="919876543210"):
    body = json.dumps({"entry": [{"changes": [{"value": {"messages": [{"from": sender, "type": "text", "text": {"body": text}}]}}]}]}).encode()
    sig = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    r = await client.post("/api/whatsapp/webhook", content=body, headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"})
    assert r.status_code == 200
    return FakeClient.sent[-1]["text"]["body"] if FakeClient.sent else None


async def test_not_configured(client, auth):
    r = await client.get("/api/integrations/whatsapp-cloud", headers=auth)
    assert r.json()["available"] is False
    assert (await client.post("/api/integrations/whatsapp-cloud/link", headers=auth, json={"phone": "+919876543210"})).status_code == 409
    assert (await client.post("/api/whatsapp/webhook", content=b"{}")).status_code == 403


async def test_webhook_verify_and_bad_signature(client, configured):
    r = await client.get("/api/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "vt", "hub.challenge": "42"})
    assert r.status_code == 200 and r.text == "42"
    bad = await client.get("/api/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "1"})
    assert bad.status_code == 403
    assert (await client.post("/api/whatsapp/webhook", content=b"{}", headers={"X-Hub-Signature-256": "sha256=00"})).status_code == 403


async def test_link_commands_and_yes_approval(client, auth, db, configured):
    r = await client.post("/api/integrations/whatsapp-cloud/link", headers=auth, json={"phone": "+91 98765 43210"})
    assert r.json()["pending"]
    code = FakeClient.sent[0]["text"]["body"].split("*")[1]
    assert "linked" in await inbound(client, code)
    assert (await client.get("/api/integrations/whatsapp-cloud", headers=auth)).json()["connected"]
    assert await inbound(client, "hello", sender="911111111111") == FakeClient.sent[-1]["text"]["body"]  # unknown: no new reply
    n = len(FakeClient.sent)
    await inbound(client, "jobs", sender="911111111111")
    assert len(FakeClient.sent) == n

    await client.put("/api/profile", headers=auth, json=PROFILE)
    await client.post("/api/jobs/import", headers=auth, json={"title": "Senior SDET", "company": "PayCo", "description": SDET_JD,
                                                              "application_url": "https://payco.example/sdet"})
    assert "Senior SDET at PayCo" in await inbound(client, "jobs")
    assert "Reply *yes*" in await inbound(client, "apply 1")
    assert await db[c.APPLICATIONS].count_documents({}) == 1
    reply = await inbound(client, "yes")
    assert "Approved" in reply or "Couldn't approve" in reply
    assert await db[c.AUDIT_LOGS].count_documents({"action": "whatsapp.apply_prepared"}) == 1
    assert "Nothing is waiting" in await inbound(client, "no")
    assert "pipeline" in await inbound(client, "status")
    assert "digest" in await inbound(client, "digest")
    assert "paused" in await inbound(client, "pause")
    assert not await __import__("app.automation.service", fromlist=["x"]).is_allowed(db, (await db.users.find_one())["_id"], "applications")
    assert "resumed" in await inbound(client, "resume")
    assert "jobs" in await inbound(client, "help")
    uid = (await db.users.find_one())["_id"]
    assert await wa.send_daily_digest(db, uid)


async def test_wrong_code(client, auth, configured, monkeypatch):
    monkeypatch.setattr(wa.secrets, "randbelow", lambda n: 123456)
    await client.post("/api/integrations/whatsapp-cloud/link", headers=auth, json={"phone": "+919876543210"})
    assert (await client.post("/api/integrations/whatsapp-cloud/verify", headers=auth, json={"code": "000000"})).status_code == 400
    ok = await client.post("/api/integrations/whatsapp-cloud/verify", headers=auth, json={"code": "123456"})
    assert ok.json()["connected"]

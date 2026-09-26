"""WhatsApp mirroring of notifications (CallMeBot)."""

import pytest

from app.database import collections as c
from app.services import whatsapp


class FakeResp:
    def __init__(self, status=200, text="Message queued"):
        self.status_code, self.text = status, text


class FakeClient:
    sent: list = []
    fail = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None):
        assert url == whatsapp.API
        if params["apikey"] == "badkey":
            return FakeResp(203, "APIKey is invalid. ERROR")
        if FakeClient.fail:
            raise OSError("network down")
        FakeClient.sent.append(params)
        return FakeResp()


@pytest.fixture(autouse=True)
def fake_callmebot(monkeypatch):
    FakeClient.sent, FakeClient.fail = [], False
    monkeypatch.setattr(whatsapp, "http_client", lambda: FakeClient())


async def test_connect_sends_test_message_and_rejects_bad_key(client, auth, db):
    bad = await client.put("/api/integrations/whatsapp", headers=auth, json={"phone": "+91 98765 43210", "apikey": "badkey"})
    assert bad.status_code == 400 and await db[c.INTEGRATIONS].count_documents({"provider": "whatsapp"}) == 0
    r = await client.put("/api/integrations/whatsapp", headers=auth, json={"phone": "+91 98765 43210", "apikey": "123456"})
    assert r.status_code == 200 and r.json()["phone"] == "+919876543210"
    assert FakeClient.sent[0]["phone"] == "+919876543210" and "WhatsApp connected" in FakeClient.sent[0]["text"]
    doc = await db[c.INTEGRATIONS].find_one({"provider": "whatsapp"})
    assert "123456" not in str(doc)  # key stored encrypted
    info = (await client.get("/api/integrations", headers=auth)).json()["whatsapp"]
    assert info["enabled"] and info["phone"].endswith("••••")


async def test_every_notification_is_mirrored(client, auth, db):
    from tests.test_email import _app

    await client.put("/api/integrations/whatsapp", headers=auth, json={"phone": "+919876543210", "apikey": "123456"})
    FakeClient.sent.clear()
    a = await _app(client, auth)  # "Application ready" notification
    await client.post("/api/emails/import", headers=auth, json={
        "sender": "Talent Team <careers@payco.com>", "subject": "Interview invitation - Senior SDET",
        "body": "We'd like to invite you to an interview for the Senior SDET role at PayCo on 2 October 2026 at 3 PM IST."})
    texts = [p["text"] for p in FakeClient.sent]
    assert any("High-match job" in t for t in texts), texts
    assert any("Interview" in t and "Detected from Gmail" in t for t in texts), texts  # received email -> WhatsApp
    assert all(t.startswith("*Saige AI*") for t in texts)
    assert any(f"/applications/{a['id']}" in t for t in texts)  # deep link back into Saige


async def test_whatsapp_outage_never_breaks_the_app(client, auth, db):
    from tests.test_email import _app

    await client.put("/api/integrations/whatsapp", headers=auth, json={"phone": "+919876543210", "apikey": "123456"})
    FakeClient.fail = True
    a = await _app(client, auth)
    assert a["id"]  # the action succeeded
    assert await db[c.NOTIFICATIONS].count_documents({}) >= 1  # in-app notification still created
    assert "network down" in (await db[c.INTEGRATIONS].find_one({"provider": "whatsapp"}))["error"]


async def test_toggle_off_stops_messages(client, auth, db):
    from tests.test_email import _app

    await client.put("/api/integrations/whatsapp", headers=auth, json={"phone": "+919876543210", "apikey": "123456"})
    await client.post("/api/integrations/whatsapp/toggle", headers=auth, params={"enabled": "false"})
    FakeClient.sent.clear()
    await _app(client, auth)
    assert FakeClient.sent == []
    assert (await client.delete("/api/integrations/whatsapp", headers=auth)).status_code == 204

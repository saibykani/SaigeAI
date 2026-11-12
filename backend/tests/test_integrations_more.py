# ruff: noqa: E501  (fixture payloads)
import httpx

from app.config import get_settings
from app.connectors import router as conn
from app.database import collections as c
from app.jobs import discover
from app.services import drive, telegram


def _client(handler):
    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_telegram_link_and_mirror(client, auth, db, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "telegram_bot_token", "123:abc")
    monkeypatch.setattr(s, "telegram_bot_username", "SaigeBot")
    sent = []
    code = {}

    def handler(req):
        method = req.url.path.rsplit("/", 1)[1]
        if method == "getUpdates":
            return httpx.Response(200, json={"ok": True, "result": [{"message": {"text": f"/start {code['v']}", "chat": {"id": 42, "first_name": "Asha"}}}]})
        sent.append(req.read().decode())
        return httpx.Response(200, json={"ok": True, "result": {}})

    monkeypatch.setattr(telegram, "http_client", _client(handler))
    st = (await client.post("/api/integrations/telegram/start", headers=auth)).json()
    assert st["link"].startswith("https://t.me/SaigeBot?start=")
    code["v"] = st["link"].rsplit("=", 1)[1]
    ok = (await client.post("/api/integrations/telegram/confirm", headers=auth)).json()
    assert ok["connected"] and ok["name"] == "Asha"
    uid = (await db[c.USERS].find_one({}))["_id"]
    from app.services.notify import notify

    await notify(db, user_id=uid, kind="high_match_job", title="New 95% match", body="SDET at Acme", link="/jobs")
    assert any("New 95% match" in s for s in sent)


async def test_coding_profile_feeds_interview_prep(client, auth, monkeypatch):
    def handler(req):
        if "leetcode" in str(req.url):
            return httpx.Response(200, json={"data": {"matchedUser": {"profile": {"ranking": 120000}, "submitStatsGlobal": {"acSubmissionNum": [
                {"difficulty": "All", "count": 150}, {"difficulty": "Easy", "count": 90}, {"difficulty": "Medium", "count": 55},
                {"difficulty": "Hard", "count": 5}]}, "tagProblemCounts": {"advanced": [], "intermediate": [{"tagName": "Array", "tagSlug": "array",
                "problemsSolved": 80}], "fundamental": [{"tagName": "String", "tagSlug": "string", "problemsSolved": 40}]}}}})
        return httpx.Response(200, json={"models": [{"badge_name": "Java", "stars": 4}]})

    monkeypatch.setattr(conn, "coding_client", _client(handler))
    r = (await client.put("/api/connectors/coding", headers=auth, json={"leetcode": "asha", "hackerrank": "asha"})).json()
    plan = r["plan"]
    assert plan["leetcode"]["medium"] == 55 and plan["hackerrank"][0]["name"] == "Java"
    assert plan["practise"][0]["solved"] == 0 and "leetcode.com/tag/" in plan["practise"][0]["url"]


async def test_drive_upload_when_scope_granted(db, monkeypatch):
    from app.email import gmail
    from app.services import crypto

    calls = []

    async def token(rt):
        return "tok"

    def handler(req):
        calls.append(str(req.url))
        if "upload" in str(req.url):
            return httpx.Response(200, json={"id": "f1", "webViewLink": "https://drive.google.com/file/d/f1"})
        return httpx.Response(200, json={"id": "folder1"})

    monkeypatch.setattr(gmail, "access_token", token)
    monkeypatch.setattr(drive, "http_client", _client(handler))
    await db[c.INTEGRATIONS].insert_one({"user_id": "u1", "provider": "gmail", "refresh_token_enc": crypto.encrypt("rt"), "scopes": [gmail.DRIVE_SCOPE]})
    assert await drive.upload(db, "u1", "Asha_Rao.pdf", b"%PDF-1.4") == "https://drive.google.com/file/d/f1"
    assert await drive.upload(db, "nobody", "x.pdf", b"%PDF") is None
    assert len([u for u in calls if "upload" in u]) == 1


async def test_jooble_provider(monkeypatch):
    monkeypatch.setattr(get_settings(), "jooble_api_key", "k")
    assert "jooble" in discover.enabled_providers()

    def handler(req):
        return httpx.Response(200, json={"jobs": [{"id": 1, "title": "Sales Executive", "company": "Acme", "location": "Pune", "link": "https://j/1",
                                                   "snippet": "B2B sales role", "updated": "2026-11-11T00:00:00"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as cl:
        out = await discover.jooble(cl, "sales executive", None, "India")
    assert out[0]["source"] == "jooble" and out[0]["title"] == "Sales Executive"

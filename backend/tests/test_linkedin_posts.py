"""LinkedIn posting agent, auto outreach mode and custom templates."""

from app.database import collections as c
from app.email import smtp
from app.linkedin_posts import client as li
from app.scheduler import service as sched
from tests.job_fixtures import PROFILE
from tests.test_discover_send import FakeSMTP


async def _uid(db):
    return (await db[c.USERS].find_one())["_id"]


async def test_post_generation_media_and_manual_ready(client, auth, db):
    await client.put("/api/profile", headers=auth, json=PROFILE)
    await client.put("/api/automation/settings", headers=auth, json={"linkedin_posts": {"enabled": True, "disclaimer": "Views are my own."}})
    st = (await client.get("/api/linkedin/status", headers=auth)).json()
    assert st["connected"] is False and st["settings"]["enabled"] is True
    formats = []
    for _ in range(3):
        p = (await client.post("/api/linkedin/posts/generate", headers=auth)).json()
        formats.append(p["format"])
        assert "#" in p["text"] and p["text"].rstrip().endswith("Views are my own.")
        if p["format"] != "text":
            m = await client.get(f"/api/linkedin/posts/{p['id']}/media", headers=auth)
            assert m.status_code == 200 and m.headers["content-type"] in ("image/png", "application/pdf")
    assert set(formats) == {"image", "carousel", "text"}
    pub = (await client.post(f"/api/linkedin/posts/{p['id']}/publish", headers=auth)).json()
    assert pub["status"] == "ready" and pub["share_url"].startswith("https://www.linkedin.com/feed/?shareActive=true")
    r = await client.post(f"/api/linkedin/posts/{p['id']}/stats", headers=auth, json={"reactions": 12, "comments": 3})
    assert r.json()["stats"] == {"reactions": 12, "comments": 3}


async def test_daily_job_publishes_through_linkedin_api(client, auth, db, monkeypatch):
    from app.services import crypto
    from app.utils import utcnow

    await client.put("/api/profile", headers=auth, json=PROFILE)
    lp = {"enabled": True, "time": "06:00", "days": [0, 1, 2, 3, 4, 5, 6]}
    await client.put("/api/automation/settings", headers=auth, json={"linkedin_posts": lp})
    uid = await _uid(db)
    from datetime import timedelta
    await db[c.INTEGRATIONS].insert_one({"_id": "li", "user_id": uid, "provider": "linkedin_api", "sub": "abc123",
                                         "access_token_enc": crypto.encrypt("tok"), "expires_at": utcnow() + timedelta(days=30)})
    sent = {}

    async def fake_publish(token, sub, text, image=None, document=None, doc_title="", alt=""):
        sent.update(token=token, sub=sub, text=text, media=bool(image or document))
        return "urn:li:share:777"

    monkeypatch.setattr(li, "publish", fake_publish)
    from datetime import UTC, datetime
    res = {r["job"]: r for r in await sched.run_for_user(db, uid, datetime(2026, 9, 28, 5, 0, tzinfo=UTC))}  # 10:30 IST
    assert res["linkedin_post"]["status"] == "succeeded", res["linkedin_post"]
    assert sent["token"] == "tok" and sent["sub"] == "abc123" and sent["media"]
    posts = (await client.get("/api/linkedin/posts", headers=auth)).json()
    assert posts[0]["status"] == "published" and posts[0]["url"] == "https://www.linkedin.com/feed/update/urn:li:share:777/"
    assert await db[c.NOTIFICATIONS].find_one({"kind": "linkedin_post", "title": {"$regex": "^Posted on LinkedIn"}})
    again = await sched.run_for_user(db, uid, datetime(2026, 9, 28, 6, 0, tzinfo=UTC), only="linkedin_post", trigger="manual")
    assert again[0]["result"] == {"skipped": "already posted today"}


async def test_comment_reply_drafts(client, auth):
    r = await client.post("/api/linkedin/comment-replies", headers=auth, json={"comments": [
        {"author": "Ravi Kumar", "text": "Great tip, thanks!"}, {"author": "Meera", "text": "How do you handle iframes?"}]})
    replies = r.json()["replies"]
    assert replies[0]["reply"].startswith("Thanks Ravi!") and "question" in replies[1]["reply"]


async def test_auto_mode_sends_reply_and_custom_template(client, auth, db, monkeypatch):
    from app.email import imap
    from tests.test_gmail_imap import FakeIMAP

    FakeSMTP.sent = []
    monkeypatch.setattr(smtp, "SMTP_FACTORY", FakeSMTP)
    monkeypatch.setattr(imap, "IMAP_FACTORY", FakeIMAP)
    await client.put("/api/profile", headers=auth, json=PROFILE)
    await client.post("/api/auth/connect/gmail-app-password", headers=auth, json={"email": "asha@gmail.com", "app_password": "abcdefghijklmnop"})
    await client.post("/api/emails/import", headers=auth, json={
        "sender": "Meera Iyer <meera@globex.com>", "subject": "SDET role at Globex",
        "body": "Hi, I'm a recruiter at Globex. Are you open to a chat?"})
    uid = await _uid(db)
    s = await sched.get_settings_doc(db, uid)
    from app.recruiters.auto_outreach import run
    assert (await run(db, uid, s))["skipped"].startswith("outreach is in manual")
    await client.put("/api/automation/settings", headers=auth, json={"outreach": {"mode": "auto", "templates": {
        "cold": "Hi {{firstName}}, I'm {{myName}} ({{myRole}}). Interested in {{jobTitle}} at {{companyName}}."}}})
    s = await sched.get_settings_doc(db, uid)
    out = await run(db, uid, s)
    assert out["replies"] == 1 and FakeSMTP.sent[-1]["To"] == "meera@globex.com"
    ct = (await client.post("/api/recruiters", headers=auth, json={"name": "Priya Nair", "company": "PayCo", "email": "priya@payco.com"})).json()
    d = (await client.post("/api/outreach/draft", headers=auth, json={"contact_id": ct["id"], "kind": "cold"})).json()
    assert d["body"] == "Hi Priya, I'm Asha Rao (Senior QA Engineer). Interested in the role at PayCo."

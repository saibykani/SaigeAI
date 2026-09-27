"""Saige assistant (built-in and Claude paths), insights, find-people, WhatsApp test/errors."""

from app.agents import llm
from app.database import collections as c
from tests.job_fixtures import PROFILE


async def test_builtin_assistant_answers_from_records(client, auth, db):
    llm.set_provider(None)
    await client.put("/api/profile", headers=auth, json=PROFILE)
    r = await client.post("/api/assistant/chat", headers=auth, json={"messages": [{"role": "user", "content": "what skills do I have?"}]})
    assert r.status_code == 200
    body = r.json()
    assert body["engine"] == "builtin" and "Selenium" in body["reply"]
    assert any(a["href"] == "/profile" for a in body["actions"])
    r = await client.post("/api/assistant/chat", headers=auth, json={"messages": [{"role": "user", "content": "hello"}]})
    assert "Asha" in r.json()["reply"]


class FakeLLM:
    name = "fake"
    seen: dict = {}

    async def chat(self, *, system, messages):
        FakeLLM.seen = {"system": system, "messages": messages}
        return "You could start with the SDET roles."


async def test_claude_assistant_gets_grounded_context(client, auth):
    llm.set_provider(FakeLLM())
    try:
        await client.put("/api/profile", headers=auth, json=PROFILE)
        r = await client.post("/api/assistant/chat", headers=auth, json={"messages": [
            {"role": "user", "content": "Which jobs should I apply to?"}]})
        assert r.json()["engine"] == "claude" and r.json()["reply"].startswith("You could")
        assert "Asha Rao" in FakeLLM.seen["system"] and "Never invent" in FakeLLM.seen["system"]
    finally:
        llm.set_provider(None)


async def test_insights_and_find_people(client, auth):
    from tests.job_fixtures import SDET_JD

    await client.put("/api/profile", headers=auth, json=PROFILE)
    body = {"title": "Senior SDET", "company": "PayCo", "description": SDET_JD}
    job = (await client.post("/api/jobs/import", headers=auth, json=body)).json()["job"]
    await client.post("/api/applications", headers=auth, json={"job_id": job["id"]})
    ins = (await client.get("/api/analytics/insights", headers=auth)).json()
    assert ins["jobs_by_source"][0]["count"] == 1 and ins["top_companies"][0]["label"] == "PayCo"
    assert sum(b["count"] for b in ins["match_distribution"]) == 1
    people = (await client.get("/api/recruiters/find-people", headers=auth)).json()
    assert people[0]["company"] == "PayCo" and "application" in people[0]["sources"]
    assert any("QA%20Manager%20PayCo" in s["url"] for s in people[0]["searches"])


async def test_whatsapp_rejection_shows_callmebot_answer(client, auth, db, monkeypatch):
    from app.services import whatsapp

    class R:
        status_code = 200
        text = "<html><body><p>APIKey is invalid. Please send the message again.</p></body></html>"

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None):
            return R()

    monkeypatch.setattr(whatsapp, "http_client", lambda: Client())
    r = await client.put("/api/integrations/whatsapp", headers=auth, json={"phone": "+91 98765 43210", "apikey": "1234567", "enabled": True})
    assert r.status_code == 400 and "APIKey is invalid" in r.json()["detail"]
    assert not await db[c.INTEGRATIONS].find_one({"provider": "whatsapp"})
    bad = await client.put("/api/integrations/whatsapp", headers=auth, json={"phone": "98765", "apikey": "1234567", "enabled": True})
    assert bad.status_code == 422
    R.text = "<html><p>Message queued. You will receive it in a few seconds.</p></html>"
    ok = await client.put("/api/integrations/whatsapp", headers=auth, json={"phone": "+91 98765 43210", "apikey": "1234567", "enabled": True})
    assert ok.status_code == 200
    t = await client.post("/api/integrations/whatsapp/test", headers=auth)
    assert t.status_code == 200 and "queued" in t.json()["answer"]


async def test_ats_optimize_creates_better_version(client, auth):
    from tests.job_fixtures import SDET_JD
    from tests.test_resume_ai import upload

    await client.put("/api/profile", headers=auth, json=PROFILE)
    rid = (await upload(client, auth)).json()["id"]
    r = await client.post("/api/resumes/ats-optimize", headers=auth, json={"resume_id": rid, "jd_text": SDET_JD, "title": "SDET"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["after"]["score"] >= body["before"]["score"] and body["resume_id"] != rid
    assert "Kubernetes" not in body["after"]["matched_keywords"]  # never invented
    assert "Kubernetes" not in " ".join(body["after"]["missing_required"]) or body["gaps"] is not None
    listed = (await client.get("/api/resumes", headers=auth)).json()
    assert any(x["id"] == body["resume_id"] for x in listed)


async def test_interview_prep(client, auth):
    from tests.job_fixtures import SDET_JD

    await client.put("/api/profile", headers=auth, json=PROFILE)
    body = {"title": "Senior SDET", "company": "PayCo", "description": SDET_JD}
    job = (await client.post("/api/jobs/import", headers=auth, json=body)).json()["job"]
    r = (await client.get(f"/api/jobs/{job['id']}/interview-prep", headers=auth)).json()
    skills = {t["skill"]: t for t in r["technical"]}
    assert skills["Selenium"]["you_have_it"] and skills["Selenium"]["questions"]
    assert len(r["behavioural"]) == 5 and r["ask_them"] and "Asha Rao" in r["pitch"]
    assert all("Kubernetes" != s for s in r["pitch"].split(", "))

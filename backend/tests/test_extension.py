"""Phase 9: personal access tokens and the browser-extension API."""

from app.database import collections as c
from tests.job_fixtures import SDET_JD
from tests.test_resume_ai import PROFILE

URL = "https://boards.greenhouse.io/payco/jobs/123"
PAGE = {"url": URL, "title": "Senior SDET", "company": "PayCo", "location": "Bengaluru", "text": SDET_JD}


async def _token(client, auth, name="Chrome extension") -> str:
    r = await client.post("/api/auth/tokens", headers=auth, json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["token"]


async def test_token_lifecycle(client, auth, db):
    r = await client.post("/api/auth/tokens", headers=auth, json={"name": "Laptop"})
    body = r.json()
    assert body["token"].startswith("saige_pat_") and body["prefix"] == body["token"][:14]
    doc = await db[c.API_TOKENS].find_one({"_id": body["id"]})
    assert body["token"] not in str(doc)  # only the hash is stored
    listed = (await client.get("/api/auth/tokens", headers=auth)).json()
    assert [t["name"] for t in listed] == ["Laptop"] and "token" not in listed[0]
    pat = {"Authorization": f"Bearer {body['token']}"}
    me = await client.get("/api/ext/me", headers=pat)
    assert me.status_code == 200 and me.json()["email"] == "asha@example.com"
    assert (await client.get("/api/auth/tokens", headers=auth)).json()[0]["last_used_at"]
    assert (await client.delete(f"/api/auth/tokens/{body['id']}", headers=auth)).status_code == 204
    assert (await client.get("/api/ext/me", headers=pat)).status_code == 401
    for _ in range(5):
        await _token(client, auth)
    assert (await client.post("/api/auth/tokens", headers=auth, json={})).status_code == 409


async def test_token_is_limited_to_extension_endpoints(client, auth):
    pat = {"Authorization": f"Bearer {await _token(client, auth)}"}
    for path in ("/api/profile", "/api/auth/me", "/api/jobs", "/api/auth/tokens"):
        assert (await client.get(path, headers=pat)).status_code == 401, path
    assert (await client.get("/api/ext/me", headers=auth)).status_code == 401  # and a session JWT can't use /ext
    assert (await client.get("/api/ext/me", headers={"Authorization": "Bearer saige_pat_forged"})).status_code == 401


async def test_analyze_does_not_save_then_save_and_answers(client, auth, db):
    await client.put("/api/profile", headers=auth, json=PROFILE)
    pat = {"Authorization": f"Bearer {await _token(client, auth)}"}
    r = (await client.post("/api/ext/analyze", headers=pat, json=PAGE)).json()
    assert 0 < r["score"] <= 100 and "Selenium" in r["matched_skills"] and r["saved_job_id"] is None
    assert await db[c.JOBS].count_documents({}) == 0

    saved = await client.post("/api/ext/save", headers=pat, json=PAGE)
    assert saved.status_code == 201 and saved.json()["created"] is True
    job_id = saved.json()["job_id"]
    job = await db[c.JOBS].find_one({"_id": job_id})
    assert job["source"] == "extension" and job["company"] == "PayCo"
    again = (await client.post("/api/ext/save", headers=pat, json=PAGE)).json()
    assert again["created"] is False and again["job_id"] == job_id  # de-duplicated by URL
    assert (await client.post("/api/ext/analyze", headers=pat, json=PAGE)).json()["saved_job_id"] == job_id

    assert (await client.get("/api/ext/answers", headers=pat, params={"url": URL})).json()["answers"] == []
    app_id = (await client.post("/api/applications", headers=auth, json={"job_id": job_id})).json()["id"]
    await client.post(f"/api/applications/{app_id}/prepare", headers=auth,
                      json={"questions": ["What is your notice period?", "Why do you want to join PayCo?"]})
    ans = (await client.get("/api/ext/answers", headers=pat, params={"url": URL})).json()
    assert ans["application_id"] == app_id
    assert [a["question"] for a in ans["answers"]] == ["What is your notice period?"]  # unanswered ones are omitted
    assert ans["answers"][0]["needs_review"] is False


async def test_tokens_are_deleted_with_account(client, auth, db):
    await _token(client, auth)
    r = await client.request("DELETE", "/api/privacy/account", headers={**auth, "X-Requested-With": "saige"})
    assert r.status_code == 204
    assert await db[c.API_TOKENS].count_documents({}) == 0


async def test_autofill_resume_and_profile_edits(client, auth, db):
    from app.database import collections as c
    from app.utils import new_id, utcnow
    from tests.job_fixtures import PROFILE
    from tests.test_resumes import upload

    await client.put("/api/profile", headers=auth, json=PROFILE)
    await upload(client, auth)
    pat = {"Authorization": f"Bearer {await _token(client, auth)}"}
    af = (await client.get("/api/ext/autofill", headers=pat)).json()
    assert af["fields"]["first_name"] == "Asha" and af["fields"]["last_name"] == "Rao" and af["fields"]["notice_period"] == "30"
    assert af["resume"].endswith(".docx")
    doc = await client.get("/api/ext/resume.docx", headers=pat)
    assert doc.status_code == 200 and doc.content[:2] == b"PK"
    uid = (await db[c.USERS].find_one())["_id"]
    await db[c.PROFILE_CHANGES].insert_one({"_id": "ch1", "user_id": uid, "platform": "naukri", "field": "headline",
                                            "before": "QA", "after": "Senior QA Engineer | Selenium · Java",
                                            "approval_status": "USER_APPROVAL_REQUIRED", "created_at": utcnow(),
                                            "updated_at": utcnow(), "applied_at": None, "id2": new_id()})
    edits = (await client.get("/api/ext/profile-edits", headers=pat, params={"platform": "naukri"})).json()
    assert edits[0]["field_name"] == "Headline" and edits[0]["text"].startswith("Senior QA")
    assert (await client.post("/api/ext/profile-edits/ch1/applied", headers=pat)).status_code == 200
    assert (await db[c.PROFILE_CHANGES].find_one({"_id": "ch1"}))["approval_status"] == "USER_APPROVED"
    assert (await client.get("/api/ext/profile-edits", headers=pat)).json() == []

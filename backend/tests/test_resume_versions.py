from datetime import timedelta

from app.database import collections as c
from app.utils import utcnow


async def test_resume_versions_group_by_company_and_count_replies(client, db, auth):
    me = (await client.get("/api/auth/me", headers=auth)).json()
    uid, now = me["id"], utcnow()
    await db[c.RESUMES].insert_many([
        {"_id": "r1", "user_id": uid, "name": "SDET · PayCo", "kind": "ATS Resume", "company": "PayCo", "status": "active", "created_at": now},
        {"_id": "r2", "user_id": uid, "name": "Master", "kind": "Master", "status": "active", "created_at": now},
        {"_id": "rx", "user_id": "other", "name": "Not mine", "kind": "Master", "status": "active", "created_at": now},
    ])
    await db[c.JOBS].insert_many([{"_id": "j1", "user_id": uid, "company": "PayCo", "title": "SDET"},
                                  {"_id": "j2", "user_id": uid, "company": "Acme", "title": "QA"}])
    await db[c.APPLICATIONS].insert_many([
        {"_id": "a1", "user_id": uid, "job_id": "j1", "resume_id": "r1", "status": "INTERVIEW_SCHEDULED", "applied_at": now - timedelta(days=5)},
        {"_id": "a2", "user_id": uid, "job_id": "j2", "resume_id": "r2", "status": "APPLIED", "applied_at": now - timedelta(days=3)},
        {"_id": "ax", "user_id": "other", "job_id": "j1", "resume_id": "rx", "status": "OFFER", "applied_at": now},
    ])
    r = await client.get("/api/resume-versions", headers=auth)
    assert r.status_code == 200, r.text
    out = r.json()
    names = {co["company"]: co for co in out["companies"]}
    assert set(names) == {"PayCo", "Acme"}
    assert names["PayCo"]["replied"] == 1 and names["Acme"]["replied"] == 0
    assert {x["resume_id"] for x in out["resumes"]} == {"r1", "r2"} and out["best"] is None  # under 3 sends: no winner claimed

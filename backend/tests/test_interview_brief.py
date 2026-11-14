from datetime import timedelta

from app.database import collections as c
from app.utils import new_id, utcnow

PROFILE = {
    "personal": {"name": "Asha Rao", "current_designation": "QA Engineer", "current_company": "Acme"},
    "skills": {"primary": ["Java", "Selenium"]},
    "knowledge": {
        "experience": [{"company": "Acme", "title": "QA Engineer", "technologies": ["Java"], "achievements": ["Built the regression suite"]}],
        "projects": [{"name": "Checkout Automation", "description": "Automated checkout tests", "technologies": ["Selenium", "Java"],
                      "highlights": ["Caught defects before release"]}],
    },
}


async def _uid(db):
    return (await db[c.USERS].find_one({}))["_id"]


async def test_brief_for_interview(client, auth, db):
    assert (await client.put("/api/profile", headers=auth, json=PROFILE)).status_code == 200
    uid = await _uid(db)
    job_id = new_id()
    await db[c.JOBS].insert_one({"_id": job_id, "user_id": uid, "company": "Globex", "company_key": "globex", "title": "SDET",
                                 "skills": ["Java", "Selenium", "Kubernetes"], "requirements": ["3+ years in test automation"],
                                 "description": "SDET role", "analysis": {}, "updated_at": utcnow()})
    app_id = new_id()
    await db[c.APPLICATIONS].insert_one({"_id": app_id, "user_id": uid, "company": "Globex", "role": "SDET", "job_id": job_id})
    iid = new_id()
    now = utcnow()
    await db[c.INTERVIEWS].insert_one({"_id": iid, "user_id": uid, "application_id": app_id, "company": "Globex", "role": "SDET",
                                       "round": "Technical", "scheduled_at": now + timedelta(days=1),
                                       "meeting_url": "https://meet.google.com/x", "status": "upcoming", "created_at": now})
    r = await client.get(f"/api/interviews/{iid}/brief", headers=auth)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["company"] == "Globex" and b["meeting_url"] == "https://meet.google.com/x" and b["has_job"]
    assert b["brush_up"] == ["Kubernetes"] and "Selenium" in b["skills"]
    assert {m["name"] for m in b["matching"]} >= {"Checkout Automation"}
    assert 6 <= len(b["questions"]) <= 8 and b["checklist"]
    assert (await client.get("/api/interviews/nope/brief", headers=auth)).status_code == 404


async def test_brief_from_email_matches_saved_job_by_company(client, auth, db):
    assert (await client.put("/api/profile", headers=auth, json=PROFILE)).status_code == 200
    uid = await _uid(db)
    await db[c.JOBS].insert_one({"_id": new_id(), "user_id": uid, "company": "Initech", "company_key": "initech", "title": "QA Lead",
                                 "skills": ["Java", "Docker"], "description": "", "analysis": {}, "updated_at": utcnow()})
    eid = new_id()
    await db[c.EMAILS].insert_one({"_id": eid, "user_id": uid, "subject": "Interview invite", "sender": "hr@initech.com", "body": "",
                                   "received_at": utcnow(), "category": "INTERVIEW_INVITE",
                                   "extracted": {"company": "Initech", "meeting_url": "https://zoom.us/j/1",
                                                 "interview_at": "2030-01-01T10:00:00+00:00"}})
    r = await client.get("/api/interviews/brief", params={"email_id": eid}, headers=auth)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["company"] == "Initech" and b["meeting_url"] == "https://zoom.us/j/1" and b["has_job"] and b["brush_up"] == ["Docker"]
    assert (await client.get("/api/interviews/brief", params={"email_id": "zzz"}, headers=auth)).status_code == 404

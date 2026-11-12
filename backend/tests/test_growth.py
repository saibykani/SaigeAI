from datetime import timedelta

from app.database import collections as c
from app.utils import utcnow
from tests.job_fixtures import PROFILE, SDET_JD


async def _uid(db):
    return (await db[c.USERS].find_one({}))["_id"]


async def test_ghosting_goals_salary_roles(client, auth, db):
    prof = {**PROFILE, "personal": {**PROFILE["personal"], "expected_ctc": 12},
            "preferences": {**PROFILE.get("preferences", {}), "target_roles": ["SDET"]}}
    assert (await client.put("/api/profile", headers=auth, json=prof)).status_code == 200
    uid = await _uid(db)
    old = utcnow() - timedelta(days=14)
    await db[c.JOBS].insert_one({"_id": "j1", "user_id": uid, "title": "SDET II", "company": "Razorpay", "salary_min": 1500000,
                                 "salary_max": 2500000, "currency": "INR"})
    await db[c.APPLICATIONS].insert_one({"_id": "a1", "user_id": uid, "job_id": "j1", "status": "APPLIED", "applied_at": old})
    await db[c.CAREER_JOBS].insert_many([
        {"_id": f"cj{i}", "user_id": uid, "title": t, "company": co, "salary_lpa": v, "salary_currency": "INR"}
        for i, (t, co, v) in enumerate([("QA Automation Engineer", "Zoho", 10.0), ("SDET", "PhonePe", 22.0),
                                        ("Manual Tester", "Acme", 4.0), ("Software Engineer in Test", "Swiggy", 18.0)])])
    g = (await client.get("/api/growth/ghosting", headers=auth)).json()
    assert g[0]["company"] == "Razorpay" and g[0]["silent_days"] >= 14
    goals = (await client.put("/api/growth/goals", headers=auth, json={"applications": 5, "outreach": 3, "resumes": 2, "prep": 1})).json()
    assert {x["key"]: x["target"] for x in goals["goals"]}["applications"] == 5
    s = (await client.get("/api/growth/salary", headers=auth)).json()
    assert s["role"] == "SDET" and s["overall"]["postings"] >= 3 and s["verdict"]
    assert any(co["company"] == "Razorpay" and co["median"] == 20.0 for co in s["companies"])
    assert all("ambitionbox.com" in co["links"][0]["url"] for co in s["companies"])
    r = (await client.get("/api/growth/roles?q=SDET", headers=auth)).json()
    assert "QA Automation Engineer" in r["related"] and "manual" in r["hide_words"]
    assert not any("Manual" in t for t in r["from_companies"])


async def test_interview_prep_uses_real_projects(client, auth, db):
    prof = {**PROFILE, "knowledge": {**PROFILE["knowledge"], "projects": [
        {"name": "VCIP", "technologies": ["Selenium", "JMeter"], "highlights": ["Automated KYC video flows with Selenium."]}]}}
    assert (await client.put("/api/profile", headers=auth, json=prof)).status_code == 200
    j = (await client.post("/api/jobs/import", headers=auth, json={"title": "SDET", "company": "Acme", "description": SDET_JD})).json()
    jid = j.get("id") or j.get("job", {}).get("id") or j.get("_id")
    p = (await client.get(f"/api/jobs/{jid}/interview-prep", headers=auth)).json()
    assert p["projects"][0]["name"] == "VCIP" and "Selenium" in p["projects"][0]["uses"]

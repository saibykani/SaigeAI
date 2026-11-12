from app.database import collections as c
from tests.job_fixtures import PROFILE


async def test_setup_gate_and_fill_from_resumes(client, auth, db):
    s = (await client.get("/api/profile/setup-status", headers=auth)).json()
    assert s["needs_setup"] is True and s["has_resume"] is False
    me = await db[c.USERS].find_one({})
    await db[c.RESUMES].insert_one({"_id": "r1", "user_id": me["_id"], "name": "Mine", "kind": "Master", "current_version_id": "v1",
                                    "updated_at": __import__("datetime").datetime(2026, 11, 1)})
    await db[c.RESUME_VERSIONS].insert_one({"_id": "v1", "resume_id": "r1", "parsed": {
        "name": "Asha Rao", "phone": "+91 90000 00000", "summary": "QA engineer.", "skills": ["Selenium", "Java"],
        "projects": [{"name": "VCIP", "highlights": ["Load tested KYC APIs."]}]}})
    r = (await client.post("/api/profile/fill-from-resumes", headers=auth)).json()
    assert r["resumes"] == 1 and "personal.phone" in r["applied"]
    p = (await client.get("/api/profile", headers=auth)).json()
    assert p["personal"]["phone"] == "+91 90000 00000" and p["knowledge"]["projects"][0]["name"] == "VCIP"
    assert (await client.get("/api/profile/setup-status", headers=auth)).json()["needs_setup"] is False


async def test_ats_coach_for_any_role(client, auth, db):
    assert (await client.put("/api/profile", headers=auth, json=PROFILE)).status_code == 200
    me = await db[c.USERS].find_one({})
    await db[c.RESUMES].insert_one({"_id": "r2", "user_id": me["_id"], "name": "Mine", "kind": "Master", "current_version_id": "v2"})
    await db[c.RESUME_VERSIONS].insert_one({"_id": "v2", "resume_id": "r2", "parsed": {"name": "Asha", "skills": ["Java"], "experience": [
        {"company": "Acme", "title": "QA", "start_date": "2021-01", "responsibilities": ["Tested the app"]}]}})
    r = await client.post("/api/resumes/ats-coach", headers=auth, json={"resume_id": "r2", "role": "SDET"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["projected"] >= out["score"] and out["sections"]
    assert "Selenium" in out["can_add"]  # proven in the profile, missing on the resume
    assert all(s not in out["can_add"] for s in out["confirm"])

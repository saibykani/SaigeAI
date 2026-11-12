from app.database import collections as c
from app.resumes import health
from app.schemas.resume import ParsedResume
from tests.job_fixtures import PROFILE

R = {"name": "Asha", "email": "a@x.com", "phone": "+91 9", "summary": "QA engineer.",
     "skills": [f"Skill{i}" for i in range(40)] + ["Selenium", "JMeter"],
     "experience": [{"company": "Acme", "title": "QA", "start_date": "2021-01", "responsibilities": [
         "Worked on Selenium automation for the payments app", "Responsible for JMeter load testing of the gateway",
         "Designed the regression suite, reviewed test plans with developers and product managers across three squads, "
         "and maintained nightly runs in Jenkins while triaging failures and reporting flaky tests "
         "to their owners every single morning before the daily standup meeting"]}]}


def test_report_lists_exact_lines_and_rewrites():
    rep = health.report(ParsedResume.model_validate(R))
    by = {s["area"]: s for s in rep["sections"]}
    assert by["Strong verbs"]["items"][0]["after"].startswith("Delivered Selenium")
    assert by["Quantified impact"]["items"][0]["ask"].startswith("How many test cases")
    assert not by["Skills"]["ok"] and "Selenium" in by["Skills"]["items"][0]["after"]
    assert by["Bullet length"]["fixable"]


async def test_fix_creates_version_with_user_numbers(client, auth, db):
    assert (await client.put("/api/profile", headers=auth, json=PROFILE)).status_code == 200
    uid = (await db[c.USERS].find_one({}))["_id"]
    await db[c.RESUMES].insert_one({"_id": "r9", "user_id": uid, "name": "Mine", "kind": "Master", "current_version_id": "v9", "version_count": 1})
    await db[c.RESUME_VERSIONS].insert_one({"_id": "v9", "resume_id": "r9", "parsed": R})
    edit = {R["experience"][0]["responsibilities"][0]: "Worked on Selenium automation for the payments app covering 320 test cases"}
    r = await client.post("/api/resumes/r9/health/fix", headers=auth, json={"edits": edit, "verbs": True, "split": True})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["score"] >= out["before"] and any("Stronger verb" in x for x in out["changes"])
    doc = await db[c.RESUMES].find_one({"_id": "r9"})
    v = await db[c.RESUME_VERSIONS].find_one({"_id": doc["current_version_id"]})
    assert v["parsed"]["experience"][0]["responsibilities"][0] == "Delivered Selenium automation for the payments app covering 320 test cases"

# ruff: noqa: E501
"""Bullet checker, recruiter view, versions + reply rate, coverage chips, ATS eval set, outcome-weighted ML labels."""

from datetime import timedelta

from app.database import collections as c
from app.schemas.resume import ParsedResume
from app.studio import quality
from app.utils import new_id, utcnow
from tests import ats_evalset
from tests.job_fixtures import PROFILE
from tests.test_studio_apply import SDET_JD

# measured before the vocabulary / matcher tuning: extraction F1 0.809 (P 0.923, R 0.72), matching F1 0.962
BASELINE = {"extraction": 0.809, "matching": 0.962}


def test_ats_eval_set_beats_the_baseline():
    s = ats_evalset.score()
    assert s["extraction"]["f1"] > BASELINE["extraction"] + 0.1 and s["extraction"]["recall"] >= 0.95
    assert s["matching"]["f1"] >= BASELINE["matching"] and s["matching"]["recall"] >= 0.95


def test_synonyms_and_longest_match_first():
    from app.services.skills_vocab import canonical, find_skills

    assert canonical("JS") == "JavaScript" and canonical("Selenium WebDriver") == "Selenium" and canonical("CI / CD") == "CI/CD"
    assert canonical("ReactJS") == "React" and canonical("continuous integration") == "CI/CD"
    assert "GitHub" not in find_skills("We use GitHub Actions for builds") and "GitHub Actions" in find_skills("We use GitHub Actions")


def test_bullet_checker_flags_and_never_invents_a_metric():
    r = quality.check_bullet("Responsible for testing the payment module that was built by the team")
    codes = {f["code"] for f in r["flags"]}
    assert {"weak_verb", "no_outcome", "passive"} <= codes
    assert r["rewrite"].startswith("Tested") and r["ask"]["field"] == "metric"
    assert not any(ch.isdigit() for ch in r["rewrite"])  # no number appears out of nowhere
    with_metric = quality.check_bullet("Responsible for testing the payment module", metric="cutting regression time by 30%")
    assert with_metric["ask"] is None and with_metric["rewrite"].endswith("cutting regression time by 30%.")
    good = quality.check_bullet("Reduced regression time by 40% by automating 120 Selenium tests")
    assert good["flags"] == [] and good["score"] == 100
    long = quality.check_bullet("Automated " + "very detailed work " * 14 + "for the checkout flow, which improved stability")
    assert any(f["code"] == "too_long" for f in long["flags"])


async def _resume(client, auth):
    await client.put("/api/profile", headers=auth, json=PROFILE)
    return (await client.post("/api/studio/resume", headers=auth, json={"jd_text": SDET_JD, "title": "SDET", "company": "Acme"})).json()


async def test_recruiter_view_bullets_and_coverage(client, auth):
    out = await _resume(client, auth)
    rid = out["id"]
    v = (await client.get(f"/api/studio/resumes/{rid}/recruiter-view", headers=auth)).json()
    assert v["seen_first"]["name"] and v["heatmap"] and set(v["heatmap"][0]["counts"]) == {"summary", "skills", "experience", "projects"}
    assert "fits" in v["one_page"] and v["one_page"]["pages"] > 0 and v["top_third_sections"]
    b = (await client.get(f"/api/studio/resumes/{rid}/bullets", headers=auth)).json()
    assert b["total"] == len(b["items"]) and all("flags" in i for i in b["items"])
    assert (await client.post("/api/studio/bullets/check", headers=auth, json={"text": "Worked on testing"})).json()["flags"]

    cov = (await client.get(f"/api/studio/resumes/{rid}/coverage", headers=auth)).json()
    assert cov["total"] >= 1 and {c_["state"] for c_ in cov["chips"]} <= {"on_resume", "can_add", "needs_confirmation"}
    unverified = next((c_ for c_ in cov["chips"] if c_["state"] == "needs_confirmation"), None)
    if unverified:  # never added silently
        r = await client.post(f"/api/studio/resumes/{rid}/add-skill", headers=auth, json={"skill": unverified["keyword"]})
        assert r.status_code == 409 and r.json()["detail"]["status"] == "CONFIRMATION_REQUIRED"
        await client.post("/api/studio/skills/confirm", headers=auth, json={"skills": [unverified["keyword"]]})
        ok = await client.post(f"/api/studio/resumes/{rid}/add-skill", headers=auth, json={"skill": unverified["keyword"]})
        assert ok.status_code == 200 and ok.json()["added"]


async def test_versions_compare_and_reply_rate_per_version(client, auth, db):
    a = await _resume(client, auth)
    b = (await client.post("/api/studio/resume", headers=auth, json={"jd_text": SDET_JD + "\nAlso: Docker, Kubernetes", "title": "SDET", "company": "Beta"})).json()
    uid = (await db[c.USERS].find_one({"email": "asha@example.com"}))["_id"]
    for i, status in enumerate(["replied", "sent", "sent"]):
        await db[c.SENT_EMAILS].insert_one({"_id": new_id(), "user_id": uid, "kind": "apply", "resume_id": a["id"], "to_email": f"h{i}@x.com",
                                            "to_domain": "x.com", "subject": "s", "status": status, "reply_category": "Interview Invitation",
                                            "sent_at": utcnow() - timedelta(days=2)})
    items = (await client.get("/api/studio/versions", headers=auth)).json()["items"]
    by = {i["id"]: i for i in items}
    assert by[a["id"]]["sent"] == 3 and by[a["id"]]["replies"] == 1 and by[a["id"]]["reply_rate"] == 33.3 and by[a["id"]]["interviews"] == 1
    assert by[b["id"]]["sent"] == 0 and by[b["id"]]["reply_rate"] is None
    assert [i["company"] for i in (await client.get("/api/studio/versions?company=Beta", headers=auth)).json()["items"]] == ["Beta"]
    cmp = (await client.get(f"/api/studio/versions/compare?a={a['id']}&b={b['id']}", headers=auth)).json()
    assert cmp["a"]["reply_rate"] == 33.3 and {"skills_added", "bullets_added", "summary"} <= set(cmp["diff"])


def test_diff_resumes_lists_added_and_removed_skills():
    x = ParsedResume(skills=["Java", "Selenium"], summary="a")
    y = ParsedResume(skills=["Selenium", "Docker"], summary="b")
    d = quality.diff_resumes(x, y)
    assert d["skills_added"] == ["Docker"] and d["skills_removed"] == ["Java"] and d["summary"]["changed"]


async def test_interview_outcomes_weigh_more_than_replies_in_training(db):
    from app.ml import service as ml

    uid = "u1"
    for jid, st in (("j1", "INTERVIEW_SCHEDULED"), ("j2", "RECRUITER_REPLIED")):
        await db[c.CAREER_JOBS].insert_one({"_id": jid, "user_id": uid, "saved_job_id": f"s{jid}", "title": "QA", "company": "Acme", "active": True})
        await db[c.APPLICATIONS].insert_one({"_id": f"a{jid}", "user_id": uid, "job_id": f"s{jid}", "status": st})
    assert await ml._harvest_outcomes(db, uid) == 2
    w = {s["job_id"]: s["weight"] for s in await db[c.ML_SAMPLES].find({"user_id": uid}).to_list(10)}
    assert w == {"j1": 3.0, "j2": 2.0}

# ruff: noqa: E501
"""Recruiter review, auto-improve, new templates, impact-ranked suggestions."""

from app.database import collections as c
from app.jobs.jd_parser import analyze_jd
from app.schemas.resume import ParsedEducation, ParsedExperience, ParsedResume
from app.studio import render, reviewer
from app.utils import new_id, utcnow
from tests.job_fixtures import PROFILE
from tests.test_studio_apply import SDET_JD


def _resume(**kw) -> ParsedResume:
    return ParsedResume(name="Asha Rao", email="a@x.com", phone="9", skills=["Selenium", "Java"], summary="QA engineer.",
                        experience=[ParsedExperience(company="Acme", title="QA", start_date="Jan 2020", end_date="Jan 2021", is_current=False,
                                                     responsibilities=kw.get("bullets", ["Worked on testing the login module"]))],
                        education=[ParsedEducation(degree="BTech", institution="X")])


def test_new_templates_are_ats_safe_in_every_format():
    new = ["refined", "studio", "atelier"]
    assert all(t in render.TEMPLATES for t in new) and len(render.TEMPLATES) >= 15
    r = _resume()
    for t in new:
        for fmt in ("pdf", "docx", "html", "txt", "md"):
            data = render.render(r, t, fmt, "QA Engineer")
            assert data and (fmt != "pdf" or data.startswith(b"%PDF"))
        html = render.render(r, t, "html", "QA Engineer").decode()
        assert "<table" not in html and "<img" not in html and "Professional Summary" in html and "Experience" in html
        assert "Login module".lower() in render.render(r, t, "txt").decode().lower()


def test_review_verdict_fixes_and_truthful_rewrites():
    jd = analyze_jd("SDET", "Requirements:\n- Selenium\n- Java\n- Playwright\n- Kubernetes\n- Rest Assured\n")
    out = reviewer.review(_resume(), jd)
    assert out["verdict"] in {"maybe", "reject"} and 0 <= out["score"] <= 100 and len(out["top_fixes"]) <= 5
    assert out["top_fixes"] == sorted(out["top_fixes"], key=lambda f: -f["points"])
    assert any(f["kind"] == "confirm_skills" for f in out["top_fixes"])
    rw = out["rewrites"][0]
    assert rw["rewrite"].startswith("Tested") and rw["ask"]["field"] == "metric" and not any(ch.isdigit() for ch in rw["rewrite"])
    strong = reviewer.review(_resume(bullets=["Reduced regression time by 40% by automating 120 Selenium tests in Java"]),
                             analyze_jd("SDET", "Requirements:\n- Selenium\n- Java\n"))
    assert strong["verdict"] == "shortlist" and not strong["rewrites"]


def test_review_flags_gaps_and_keyword_stuffing():
    r = _resume()
    r.experience.append(ParsedExperience(company="Beta", title="QA", start_date="Jan 2023", end_date="Jan 2024", is_current=False))
    r.skills = [f"Skill{i}" for i in range(45)]
    flags = reviewer.review(r, analyze_jd("QA", "Requirements:\n- Selenium\n"))["red_flags"]
    assert any("Gap" in f for f in flags) and any("keyword stuffing" in f for f in flags)


async def test_auto_improve_is_bounded_truthful_and_honest_about_the_ceiling(client, auth, db):
    await client.put("/api/profile", headers=auth, json=PROFILE)
    out = (await client.post("/api/studio/resume", headers=auth, json={"jd_text": SDET_JD + "\n- Kubernetes\n- Terraform", "title": "SDET",
                                                                       "company": "Acme"})).json()
    rid = out["id"]
    before = (await client.get(f"/api/studio/resumes/{rid}", headers=auth)).json()["ats"]["score"]
    r = await client.post(f"/api/studio/resumes/{rid}/auto-improve", headers=auth)
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["before"] == before and res["after"] >= before and len(res["rounds"]) <= 3
    assert res["max_truthful_score"] == res["after"]
    if not res["reached_100"]:
        assert res["message"].startswith("Max truthful score")
        assert res["blockers"]["missing_skills"] and res["score_if_confirmed"] >= res["after"]
    skills = {s.lower() for s in res["resume"]["skills"]}
    for m in res["blockers"]["missing_skills"]:
        assert m["skill"].lower() not in skills  # a skill the profile lacks is never added
    assert await db[c.AGENT_RUNS].find_one({"agent_name": "resume_auto_improve"}) and await db[c.AUDIT_LOGS].find_one({"action": "studio.auto_improve"})
    again = (await client.post(f"/api/studio/resumes/{rid}/auto-improve", headers=auth)).json()
    assert again["after"] == res["after"] and not again["saved"]  # nothing left to improve: no new version

    rv = (await client.get(f"/api/studio/resumes/{rid}/review", headers=auth)).json()
    assert rv["verdict"] in {"shortlist", "maybe", "reject"} and rv["engine"] == "deterministic"
    assert await db[c.AGENT_RUNS].find_one({"agent_name": "recruiter_review"})


async def test_suggestions_are_ranked_by_impact_with_one_line_explanations(client, auth, db):
    await client.put("/api/profile", headers=auth, json=PROFILE)
    uid = (await db[c.USERS].find_one({"email": "asha@example.com"}))["_id"]
    base = (await client.get("/api/suggestions", headers=auth)).json()
    assert base and all(1 <= s["impact"] <= 100 and s["explain"] for s in base)
    assert [s["impact"] for s in base] == sorted((s["impact"] for s in base), reverse=True)
    for i in range(6):  # real outcomes: lots of sent mail and no replies makes resume fixes matter more
        await db[c.SENT_EMAILS].insert_one({"_id": new_id(), "user_id": uid, "kind": "apply", "status": "sent", "to_email": f"h{i}@x.com",
                                            "to_domain": "x.com", "subject": "s", "sent_at": utcnow()})
    after = {s["id"]: s for s in (await client.get("/api/suggestions", headers=auth)).json()}
    old = {s["id"]: s for s in base}
    resume_items = [k for k, v in after.items() if v["area"] == "resume" and k in old]
    assert resume_items and all(after[k]["impact"] >= old[k]["impact"] for k in resume_items)
    assert any("reply" in after[k]["explain"] for k in resume_items)

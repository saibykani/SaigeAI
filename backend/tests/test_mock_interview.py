from app.agents import llm
from app.database import collections as c
from app.mock_interview.scoring import score_answer

PROFILE = {
    "personal": {"name": "Asha Rao", "current_designation": "QA Engineer", "current_company": "Acme", "total_experience_years": 4,
                 "notice_period_days": 30},
    "skills": {"primary": ["Java", "Selenium"], "tools": ["Jira"]},
    "knowledge": {
        "professional_summary": "QA engineer focused on test automation.",
        "experience": [{"company": "Acme", "title": "QA Engineer", "responsibilities": ["Built Selenium regression suite in Java"],
                        "achievements": ["Cut regression time from 2 days to 4 hours"], "technologies": ["Selenium", "Java"]}],
        "projects": [{"name": "Checkout Automation", "description": "Automated checkout flow tests", "role": "Lead",
                      "technologies": ["Selenium", "Java"], "highlights": ["Caught 40 defects before release"]}],
    },
}
JD = "We need an SDET with Java, Selenium, Kubernetes and Python. Experience with CI pipelines."


async def _setup(client, auth):
    r = await client.put("/api/profile", headers=auth, json=PROFILE)
    assert r.status_code == 200, r.text


async def test_start_answer_finish_flow(client, auth, db):
    await _setup(client, auth)
    r = await client.post("/api/mock-interview/sessions", headers=auth,
                          json={"role": "SDET", "jd_text": JD, "interview_type": "mixed", "num_questions": 8, "language": "en"})
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["generated_by"] == "templates" and len(s["questions"]) == 8
    kinds = {q["kind"] for q in s["questions"]}
    assert {"project", "skill", "gap"} <= kinds
    texts = " ".join(q["text"] for q in s["questions"])
    assert "Checkout Automation" in texts
    assert "Kubernetes" in s["missing"] and "Selenium" in s["have"]

    proj = next(q for q in s["questions"] if q["kind"] == "project")
    good = ("In the Checkout Automation project my role was lead. The situation was that checkout releases kept breaking, "
            "so the task was to automate regression. I built a Selenium and Java framework, I set up nightly runs and "
            "I worked with developers on flaky tests. As a result we caught 40 defects before release and the team "
            "delivered faster. The hardest challenge was test data, which I fixed with API seeding.")
    a = (await client.post(f"/api/mock-interview/sessions/{s['id']}/answer", headers=auth,
                           json={"index": proj["index"], "text": good})).json()
    assert a["score"] >= 60 and all(a["star"].values())
    assert any("Caught 40 defects" in line for line in a["outline"])

    gap = next(q for q in s["questions"] if q["kind"] == "gap")
    await client.post(f"/api/mock-interview/sessions/{s['id']}/answer", headers=auth, json={"index": gap["index"], "skipped": True})

    rep = (await client.post(f"/api/mock-interview/sessions/{s['id']}/finish", headers=auth)).json()
    assert 0 < rep["overall"] < 100 and rep["answered"] == 1
    assert any(x["skill"] == "Projects" for x in rep["skills"])
    assert rep["improvements"]

    assert await db[c.AGENT_RUNS].count_documents({"agent_name": "mock_interview"}) == 1
    assert await db[c.AUDIT_LOGS].count_documents({"action": "mock_interview.finish"}) == 1
    lst = (await client.get("/api/mock-interview/sessions", headers=auth)).json()
    assert lst[0]["status"] == "completed" and lst[0]["score"] == rep["overall"]
    assert c.MOCK_INTERVIEWS in c.USER_SCOPED


async def test_role_only_and_validation(client, auth):
    await _setup(client, auth)
    r = await client.post("/api/mock-interview/sessions", headers=auth, json={"role": "QA Engineer", "interview_type": "technical",
                                                                            "num_questions": 5, "difficulty": "hard"})
    assert r.status_code == 201
    assert any(q["kind"] == "skill" and q["skill"] == "Java" for q in r.json()["questions"])
    assert (await client.post("/api/mock-interview/sessions", headers=auth, json={})).status_code == 422
    assert (await client.post("/api/mock-interview/sessions", headers=auth, json={"role": "x", "num_questions": 20})).status_code == 422
    assert (await client.get("/api/mock-interview/sessions/nope", headers=auth)).status_code == 404


async def test_from_saved_job(client, auth, db):
    await _setup(client, auth)
    await db[c.JOBS].insert_one({"_id": "j1", "user_id": (await db[c.USERS].find_one({}))["_id"], "title": "SDET", "company": "Beta",
                                 "description": JD, "skills": ["Python"]})
    r = await client.post("/api/mock-interview/sessions", headers=auth, json={"job_id": "j1", "interview_type": "hr", "num_questions": 5})
    assert r.status_code == 201 and r.json()["company"] == "Beta"


def test_scoring_penalises_fillers_and_short():
    q = {"text": "Tell me about a deadline", "kind": "behavioural", "keywords": ["deadline", "plan", "result"], "star": True}
    bad = score_answer(q, "um like basically um I uh did it", [])
    assert bad["score"] < 30 and bad["filler_count"] >= 4
    assert score_answer(q, "", [])["score"] == 0


async def test_llm_questions_used_when_available(client, auth):
    await _setup(client, auth)

    class Fake:
        name = "fake"

        async def extract(self, *, system, prompt, schema):
            return schema(questions=[{"text": f"Q{i} about Selenium?", "kind": "skill", "skill": "Selenium", "keywords": ["selenium"]}
                                     for i in range(5)] + [{"text": "Invented?", "kind": "skill", "skill": "Cobol"}])

    llm.set_provider(Fake())
    try:
        r = await client.post("/api/mock-interview/sessions", headers=auth, json={"role": "SDET", "jd_text": JD, "num_questions": 6})
    finally:
        llm.set_provider(None)
    body = r.json()
    assert body["generated_by"] == "claude"
    assert body["questions"][5]["kind"] == "technical" and body["questions"][5]["skill"] is None

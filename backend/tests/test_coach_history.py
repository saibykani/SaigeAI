from tests.job_fixtures import PROFILE, SDET_JD


async def test_coach_suggests_and_history_lists_it(client, auth, db):
    prof = {**PROFILE, "knowledge": {**PROFILE["knowledge"], "projects": [], "certifications": []}}
    assert (await client.put("/api/profile", headers=auth, json=prof)).status_code == 200
    r = await client.post("/api/suggestions/run", headers=auth)
    assert r.status_code == 200, r.text
    titles = [s["title"] for s in r.json()]
    assert "Add more projects" in titles and all(s["link"].startswith("/") for s in r.json())
    h = (await client.get("/api/activity/history?days=1", headers=auth)).json()
    assert any(x["kind"] == "agent" and x["action"] == "profile_coach" for x in h)


async def test_extension_builds_and_downloads_an_ats_resume(client, auth):
    assert (await client.put("/api/profile", headers=auth, json=PROFILE)).status_code == 200
    tok = (await client.post("/api/auth/tokens", headers=auth, json={"name": "ext"})).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    r = await client.post("/api/ext/resume", headers=h, json={"title": "SDET II", "company": "Acme", "text": SDET_JD,
                                                               "url": "https://www.linkedin.com/jobs/view/1"})
    assert r.status_code == 201, r.text
    assert r.json()["score"] > 0
    d = await client.get(f"/api/ext/studio/{r.json()['id']}/download?format=pdf&on=2026-11-12", headers=h)
    assert d.status_code == 200 and d.content.startswith(b"%PDF") and "Asha_Rao_2026-11-12_Acme.pdf" in d.headers["content-disposition"]

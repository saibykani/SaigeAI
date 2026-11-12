"""Skill-gap learning path."""

from app.learning.catalog import resources_for
from tests.test_email import PROFILE, SDET_JD


def test_catalog_fallback():
    res, hours = resources_for("Docker")
    assert res[0]["url"].startswith("https://docs.docker.com") and hours == 10
    res, _ = resources_for("Quantum Basket Weaving")
    assert all("Quantum" in r["url"] or "Quantum+" in r["url"] for r in res)


async def test_path_progress_and_confirm(client, auth, db):
    await client.put("/api/profile", headers=auth, json={**PROFILE, "preferences": {"target_roles": ["DevOps Engineer"]}})
    await client.post("/api/jobs/import", headers=auth, json={"title": "Senior SDET", "company": "PayCo", "description": SDET_JD})
    r = await client.get("/api/learning", headers=auth)
    assert r.status_code == 200
    data = r.json()
    keys = [s["key"] for s in data["skills"]]
    assert "terraform" in keys and data["plan"]
    tf = next(s for s in data["skills"] if s["key"] == "terraform")
    r = await client.put("/api/learning/resources", headers=auth, json={"skill": "terraform", "resource_id": tf["resources"][0]["id"], "done": True})
    tf = next(s for s in r.json()["skills"] if s["key"] == "terraform")
    assert tf["status"] == "in_progress" and tf["progress"] == 100
    await client.put("/api/learning/skills/terraform", headers=auth, json={"status": "done", "name": "Terraform"})
    goals = (await client.get("/api/growth/goals", headers=auth)).json()
    assert goals["learning"]["done"] == 1
    bad = await client.post("/api/learning/skills/terraform/confirm", headers=auth, json={"name": "Terraform", "confirmed": False})
    assert bad.status_code == 400
    ok = await client.post("/api/learning/skills/terraform/confirm", headers=auth, json={"name": "Terraform", "confirmed": True})
    assert ok.json()["added"] == ["Terraform"]
    prof = (await client.get("/api/profile", headers=auth)).json()
    assert "Terraform" in str(prof)
    assert "terraform" not in [s["key"] for s in (await client.get("/api/learning", headers=auth)).json()["skills"]]
    assert (await client.put("/api/learning/settings", headers=auth, json={"hours_per_week": 10})).json()["hours_per_week"] == 10

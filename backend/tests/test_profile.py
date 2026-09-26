from app.database import collections as c
from tests.conftest import register


async def test_empty_profile_marks_unknowns(client, auth):
    r = await client.get("/api/profile", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["completeness"] == 0
    assert "Total Experience" in body["unknown_fields"]
    assert body["personal"]["total_experience_years"] is None


async def test_partial_update_and_completeness(client, auth):
    r = await client.put("/api/profile", headers=auth, json={
        "personal": {"name": "Asha Rao", "email": "asha@example.com", "total_experience_years": 5,
                     "linkedin_url": "https://www.linkedin.com/in/asha"},
        "skills": {"primary": ["Java", "Selenium"]},
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["personal"]["name"] == "Asha Rao"
    assert body["skills"]["primary"] == ["Java", "Selenium"]
    assert 0 < body["completeness"] < 100

    # Updating one section must not wipe another.
    r = await client.put("/api/profile", headers=auth,
                         json={"preferences": {"target_roles": ["SDET"]}})
    assert r.json()["skills"]["primary"] == ["Java", "Selenium"]
    assert r.json()["preferences"]["timezone"] == "Asia/Kolkata"


async def test_invalid_values_rejected(client, auth):
    r = await client.put("/api/profile", headers=auth,
                         json={"personal": {"linkedin_url": "not a url"}})
    assert r.status_code == 422
    r = await client.put("/api/profile", headers=auth,
                         json={"personal": {"total_experience_years": -2}})
    assert r.status_code == 422
    r = await client.put("/api/profile", headers=auth, json={"unexpected": {}})
    assert r.status_code == 422


async def test_profile_change_is_audited(client, db, auth):
    await client.put("/api/profile", headers=auth,
                     json={"personal": {"current_designation": "QA Engineer"}})
    log = await db[c.AUDIT_LOGS].find_one({"action": "profile.updated"})
    assert log
    change = next(ch for ch in log["details"]["changes"]
                  if ch["field"] == "personal.current_designation")
    assert change == {"field": "personal.current_designation", "before": None,
                      "after": "QA Engineer"}


async def test_profiles_are_isolated_between_users(client, auth):
    await client.put("/api/profile", headers=auth, json={"personal": {"name": "Asha Rao"}})
    other = await register(client, email="ravi@example.com", name="Ravi")
    r = await client.get("/api/profile", headers=other)
    assert r.json()["personal"]["name"] is None


async def test_validate_claims_endpoint(client, auth):
    await client.put("/api/profile", headers=auth, json={"skills": {"primary": ["Java"]}})
    r = await client.post("/api/profile/validate-claims", headers=auth,
                          json={"skills": ["Java", "Kubernetes"]})
    assert r.status_code == 200
    assert r.json()["status"] == "VALIDATION FAILED"
    assert [v["value"] for v in r.json()["violations"]] == ["Kubernetes"]


async def test_partial_field_update_keeps_sibling_fields(client, auth):
    await client.put("/api/profile", headers=auth,
                     json={"personal": {"name": "Asha Rao", "phone": "+91 90000 00000"}})
    r = await client.put("/api/profile", headers=auth, json={"personal": {"phone": "+91 91111 11111"}})
    assert r.json()["personal"]["name"] == "Asha Rao"
    assert r.json()["personal"]["phone"] == "+91 91111 11111"


async def test_explicit_null_clears_a_field(client, auth):
    await client.put("/api/profile", headers=auth, json={"personal": {"name": "Asha", "phone": "123"}})
    r = await client.put("/api/profile", headers=auth, json={"personal": {"phone": None}})
    assert r.json()["personal"]["phone"] is None
    assert r.json()["personal"]["name"] == "Asha"

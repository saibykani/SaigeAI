import json

from app.config import get_settings
from app.database import collections as c
from tests.conftest import CSRF
from tests.test_admin_hiring import _reg, _uid

OWNER = "saibykani07@gmail.com"


async def test_non_super_forbidden_and_owner_default(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "super_admin_email", None)  # unset env: the owner is still super admin
    h = await _reg(client, "plain@example.com")
    for path in ("/overview", "/users", "/health", "/audit", "/funnel", "/cohorts", "/features", "/announcements", "/search?q=ab", "/live"):
        assert (await client.get("/api/superadmin" + path, headers=h)).status_code == 403
    owner = await _reg(client, OWNER)
    assert (await client.get("/api/auth/me", headers=owner)).json()["is_super_admin"] is True
    r = await client.get("/api/superadmin/overview", headers=owner)
    assert r.status_code == 200 and r.json()["kpis"]["total_users"]["value"] == 2


async def test_comma_list(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "super_admin_email", "a@example.com, b@example.com")
    h = await _reg(client, "b@example.com")
    assert (await client.get("/api/superadmin/users", headers=h)).status_code == 200


async def test_actions_logged_and_users(client, db):
    owner = await _reg(client, OWNER)
    await _reg(client, "victim@example.com")
    uid = await _uid(db, "victim@example.com")
    r = await client.get("/api/superadmin/users?q=victim&page_size=25", headers=owner)
    assert r.json()["total"] == 1
    d = (await client.get(f"/api/superadmin/users/{uid}", headers=owner)).json()
    assert "password_hash" not in json.dumps(d)
    h = {**owner, **CSRF}
    assert (await client.patch(f"/api/superadmin/users/{uid}", json={"role": "admin"}, headers=h)).json()["role"] == "admin"
    assert (await client.patch(f"/api/superadmin/users/{uid}", json={"is_active": False}, headers=h)).json()["is_active"] is False
    assert (await client.post(f"/api/superadmin/users/{uid}/sign-out", headers=h)).status_code == 200
    bad = await client.post(f"/api/superadmin/users/{uid}/delete", json={"confirm_email": "nope"}, headers=h)
    assert bad.status_code == 400
    ok = await client.post(f"/api/superadmin/users/{uid}/delete", json={"confirm_email": "VICTIM@example.com"}, headers=h)
    assert ok.status_code == 200 and await db[c.USERS].find_one({"_id": uid}) is None
    acts = {a["action"] for a in await db[c.AUDIT_LOGS].find({}).to_list(length=None)}
    assert {"superadmin.user_updated", "superadmin.force_sign_out", "superadmin.user_deleted"} <= acts
    csv_r = await client.get("/api/superadmin/audit/export.csv?action=superadmin", headers=owner)
    assert csv_r.status_code == 200 and "superadmin.user_deleted" in csv_r.text


async def test_health_has_no_secrets_and_announcements(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "jooble_api_key", "SECRET-JOOBLE-KEY")
    owner = await _reg(client, OWNER)
    other = await _reg(client, "u@example.com")
    r = await client.get("/api/superadmin/health", headers=owner)
    assert r.json()["feature_flags"]["Jooble"] is True and "SECRET-JOOBLE-KEY" not in r.text
    h = {**owner, **CSRF}
    a = await client.post("/api/superadmin/announcements", json={"title": "Hi", "message": "Maintenance tonight"}, headers=h)
    assert a.status_code == 201
    assert [x["title"] for x in (await client.get("/api/announcements", headers=other)).json()] == ["Hi"]
    assert (await client.delete(f"/api/superadmin/announcements/{a.json()['id']}", headers=h)).status_code == 204
    assert (await client.get("/api/announcements", headers=other)).json() == []

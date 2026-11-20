from datetime import timedelta

from app.database import collections as c
from app.main import app
from app.utils import new_id, utcnow
from app.warroom.router import router as _war_room_router  # noqa: E402

if not any(getattr(r, "path", "").startswith("/api/war-room") for r in app.routes):  # until main.py includes it
    app.include_router(_war_room_router, prefix="/api")

PROFILE = {
    "personal": {"name": "Asha Rao", "current_designation": "QA Engineer", "current_company": "Acme"},
    "skills": {"primary": ["Java", "Selenium"]},
    "knowledge": {
        "experience": [{"company": "Acme", "title": "QA Engineer", "technologies": ["Java"], "achievements": ["Built the regression suite"]}],
        "projects": [{"name": "Checkout Automation", "description": "Automated checkout tests", "technologies": ["Selenium", "Java"],
                      "highlights": ["Caught defects before release"]}],
    },
}


async def _seed(client, auth, db, profile=True):
    if profile:
        assert (await client.put("/api/profile", headers=auth, json=PROFILE)).status_code == 200
    uid = (await db[c.USERS].find_one({}))["_id"]
    await db[c.JOBS].insert_one({"_id": new_id(), "user_id": uid, "company": "Globex", "company_key": "globex", "title": "SDET",
                                 "skills": ["Java", "Selenium", "Kubernetes"], "requirements": ["Selenium test automation"],
                                 "description": "SDET", "analysis": {}, "updated_at": utcnow()})
    iid = new_id()
    now = utcnow()
    await db[c.INTERVIEWS].insert_one({"_id": iid, "user_id": uid, "company": "Globex", "role": "SDET", "round": "Technical",
                                       "scheduled_at": now + timedelta(hours=5), "meeting_url": "https://meet.google.com/x",
                                       "status": "upcoming", "created_at": now})
    return uid, iid


async def test_war_room_payload(client, auth, db):
    uid, iid = await _seed(client, auth, db)
    await db[c.QUESTION_BANK].insert_one({"_id": new_id(), "user_id": uid, "key": "k", "text": "Explain the test pyramid?",
                                          "companies": ["Globex"], "skills": [], "updated_at": utcnow()})
    r = await client.get(f"/api/war-room/{iid}", headers=auth)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["company"] == "Globex" and b["links"]["join"] and b["links"]["ics"].endswith(f"{iid}.ics")
    assert {s["name"] for s in b["stories"]} >= {"Checkout Automation"}
    assert "Kubernetes" in b["brush_up"]
    texts = [q["text"] for q in b["questions"]]
    assert "Explain the test pyramid?" in texts and len(texts) == len(set(texts))
    assert b["requirements"][0]["evidence"] == "Checkout Automation"
    assert b["checklist"]["total"] >= 3 and b["checklist"]["done"] == 0
    assert await db[c.AGENT_RUNS].count_documents({"agent_name": "war_room"}) == 1


async def test_unknown_when_no_profile_story(client, auth, db):
    _, iid = await _seed(client, auth, db, profile=False)
    b = (await client.get(f"/api/war-room/{iid}", headers=auth)).json()
    assert b["stories"] == [] and b["stories_note"] == "UNKNOWN"
    assert all(q["story"]["line"] == "UNKNOWN" for q in b["questions"])


async def test_checklist_persists_and_custom_items(client, auth, db):
    _, iid = await _seed(client, auth, db)
    b = (await client.get(f"/api/war-room/{iid}", headers=auth)).json()
    first = b["checklist"]["items"][0]["id"]
    r = await client.patch(f"/api/war-room/{iid}/checklist", headers=auth, json={"item_id": first, "done": True})
    assert r.status_code == 200 and r.json()["done"] == 1
    r = await client.patch(f"/api/war-room/{iid}/checklist", headers=auth, json={"add": "Charge laptop"})
    custom = [x for x in r.json()["items"] if x["custom"]][0]
    again = (await client.get(f"/api/war-room/{iid}", headers=auth)).json()["checklist"]
    assert again["done"] == 1 and any(x["text"] == "Charge laptop" for x in again["items"])
    assert (await client.patch(f"/api/war-room/{iid}/checklist", headers=auth, json={"remove": custom["id"]})).status_code == 200
    assert (await client.patch(f"/api/war-room/{iid}/checklist", headers=auth, json={"remove": first})).status_code == 404
    assert (await client.patch(f"/api/war-room/{iid}/checklist", headers=auth, json={})).status_code == 422
    assert await db[c.AUDIT_LOGS].count_documents({"action": "war_room.checklist"}) >= 3


async def test_list_and_404(client, auth, db):
    _, iid = await _seed(client, auth, db)
    r = await client.get("/api/war-room", headers=auth)
    assert [x["interview_id"] for x in r.json()["interviews"]] == [iid]
    assert (await client.get("/api/war-room/nope", headers=auth)).status_code == 404
    assert (await client.patch("/api/war-room/nope/checklist", headers=auth, json={"add": "x"})).status_code == 404

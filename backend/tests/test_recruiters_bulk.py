"""Recruiters page: paging, filters, company types, email templates and capped bulk send."""

from datetime import timedelta

from app.database import collections as c
from app.jobs.dedupe import company_key
from app.recruiters import company_types as ct
from app.recruiters import email_templates as et
from app.schemas.profile import Profile
from app.utils import new_id, utcnow
from tests.job_fixtures import PROFILE


async def _uid(db):
    return (await db[c.USERS].find_one({}))["_id"]


async def _seed(db, rows, source="csv"):
    uid = await _uid(db)
    now = utcnow()
    docs = [{"_id": new_id(), "user_id": uid, "name": n, "company": co, "email": e, "email_key": e.lower() if e else None,
             "company_key": company_key(co), "role": "recruiter", "tags": [], "source": source, "unsubscribed": False,
             "last_contacted_at": None, "created_at": now, "updated_at": now} for n, co, e in rows]
    await db[c.RECRUITER_CONTACTS].insert_many(docs)
    return docs


async def _gmail(db, monkeypatch):
    uid = await _uid(db)
    await db[c.INTEGRATIONS].insert_one({"_id": new_id(), "user_id": uid, "provider": "gmail", "email": "me@gmail.com",
                                         "app_password_enc": "x"})
    sent = []

    async def fake_send(integ, from_name, to, subject, body, attachments=None, html=None):
        sent.append((to, subject, body, attachments))
        return f"<{len(sent)}@x>"
    monkeypatch.setattr("app.email.outbound.send", fake_send)
    return sent


def test_company_types():
    assert ct.auto_company_type("Tata Consultancy Services Ltd") == "service"
    assert ct.auto_company_type("Infosys BPM") == "service"
    assert ct.auto_company_type("Google India") == "product"
    assert ct.auto_company_type("Random Startup Pvt Ltd") == "unknown"
    assert ct.auto_company_type("Acme", "hr@wipro.com") == "service"
    assert ct.auto_company_type("Acme", "hr@gmail.com") == "unknown"
    assert ct.effective_type({"company": "Google", "ctype_user": "startup"}) == "startup"


async def test_pagination_filters_and_type_override(client, auth, db):
    rows = [(f"HR Team (Co{i})", f"Co{i}", f"hr{i}@co{i}.com") for i in range(60)]
    rows += [("Asha", "Infosys", "a@infosys.com"), ("Bela", "Google", None), ("Carl", "Wipro", "c@wipro.com")]
    await _seed(db, rows)

    async def get(**params):
        return (await client.get("/api/recruiters", headers=auth, params={"paged": 1, **params})).json()

    r = await get(page_size=25)
    assert r["total"] == 63 and len(r["items"]) == 25 and r["page"] == 1
    p3 = await get(page_size=25, page=3)
    assert len(p3["items"]) == 13
    assert len({x["id"] for x in r["items"]} | {x["id"] for x in p3["items"]}) == 38
    assert isinstance((await client.get("/api/recruiters", headers=auth)).json(), list)  # backward compatible
    names = (await get(sort="name", page_size=100))["items"]
    assert [x["name"] for x in names] == sorted(x["name"] for x in names)
    assert {x["company"] for x in (await get(company_type="service"))["items"]} == {"Infosys", "Wipro"}
    assert (await get(company_type="product"))["total"] == 1
    assert (await get(company_type="unknown"))["total"] == 60
    assert (await get(has_email="false"))["total"] == 1
    assert (await get(q="INFOSYS"))["total"] == 1
    assert (await get(company="Wipro"))["total"] == 1
    assert (await get(contacted="true"))["total"] == 0
    assert (await get(source="manual"))["total"] == 0
    comps = (await client.get("/api/recruiters/companies", headers=auth, params={"q": "co1", "limit": 5})).json()
    assert len(comps) == 5 and all("co1" in x["company"].lower() for x in comps) and comps[0]["contacts"] == 1
    cid = (await get(q="Co7"))["items"][0]["id"]
    out = (await client.patch(f"/api/recruiters/{cid}", headers=auth, json={"company_type": "startup"})).json()
    assert out["company_type"] == "startup" and out["company_type_custom"] is True
    assert (await get(company_type="startup"))["total"] == 1
    assert (await get(company_type="unknown"))["total"] == 59
    back = (await client.patch(f"/api/recruiters/{cid}", headers=auth, json={"company_type": None})).json()
    assert back["company_type"] == "unknown"


def test_template_rendering_never_invents():
    p = Profile.model_validate({"personal": {"name": "Asha Rao"}, "skills": {"primary": ["Selenium", "Python"]}})
    subject, body = et.render_for(et.BUILTIN[0], p, {"name": "HR Team (Acme)", "company": "Acme"})
    assert body.startswith("Dear Hiring Team,")
    assert "Acme" in subject and "Asha Rao" in subject
    assert "Selenium, Python" in body
    for missing in ("years", "Phone", "LinkedIn", "Portfolio", "{{", "work as"):  # no verified value: line removed
        assert missing not in body
    assert body.endswith("Asha Rao")
    s2, b2 = et.render_for({"subject": "{{my_role}} at {{company}}", "body": "Hi {{hr_name}},\nI know {{unknown}}.\nBye"}, p,
                           {"name": "Priya Nair", "company": "Acme"})
    assert s2 == "at Acme" and b2 == "Hi Priya,\nBye"


async def test_template_crud(client, auth):
    lst = (await client.get("/api/recruiters/email-templates", headers=auth)).json()
    assert len(lst) == 5 and all(t["builtin"] for t in lst)
    t = (await client.post("/api/recruiters/email-templates", headers=auth,
                           json={"name": "Mine", "subject": "Hi {{company}}", "body": "Hello {{hr_name}}"})).json()
    assert (await client.put(f"/api/recruiters/email-templates/{t['id']}", headers=auth, json={"name": "Mine 2"})).json()["name"] == "Mine 2"
    assert (await client.put("/api/recruiters/email-templates/builtin:followup", headers=auth, json={"name": "x"})).status_code == 404
    assert (await client.delete("/api/recruiters/email-templates/builtin:followup", headers=auth)).status_code == 404
    assert (await client.delete(f"/api/recruiters/email-templates/{t['id']}", headers=auth)).status_code == 204
    assert len((await client.get("/api/recruiters/email-templates", headers=auth)).json()) == 5


async def test_bulk_send_respects_caps(client, auth, db, monkeypatch):
    assert (await client.put("/api/profile", headers=auth, json=PROFILE)).status_code == 200
    sent = await _gmail(db, monkeypatch)
    rows = [(f"HR Team (Co{i})", f"Co{i}", f"hr{i}@co{i}.com") for i in range(12)]
    rows += [("A", "Same", "a@same.com"), ("B", "Same", "b@same.com"), ("C", "Same", "c@same.com"), ("D", "Same", "d@same.com"),
             ("NoMail", "Nomail Co", None)]
    docs = await _seed(db, rows)
    await db[c.RECRUITER_CONTACTS].update_one({"_id": docs[0]["_id"]}, {"$set": {"unsubscribed": True}})
    # put the "Same" company first so its weekly cap matters among the 10 that go out today
    ids = [d["_id"] for d in docs[12:16]] + [d["_id"] for d in docs[:12]] + [docs[16]["_id"]]
    body = {"template_id": "builtin:cold_intro", "contact_ids": ids}
    pv = (await client.post("/api/recruiters/bulk/preview", headers=auth, json=body)).json()
    assert pv["selected"] == 17 and pv["eligible"] == 15 and pv["skipped_count"] == 2
    assert pv["send_now"] == 10 and pv["queued"] == 5 and pv["quota"]["remaining_today"] == 10
    assert pv["previews"][0]["body"] and "{{" not in pv["previews"][0]["body"]
    assert (await client.post("/api/recruiters/bulk/send", headers=auth, json=body)).status_code == 422  # needs confirm
    assert not sent
    r = (await client.post("/api/recruiters/bulk/send", headers=auth, json={**body, "confirm": True})).json()
    assert r["sent"] == 10 and r["queued"] == 5 and r["failed"] == 0 and len(sent) == 10
    assert await db[c.OUTREACH].count_documents({"company": "Same", "status": "sent"}) == 3  # 3 per company per week
    assert await db[c.OUTREACH].count_documents({"status": "sent"}) == 10
    assert await db[c.RECRUITER_CONTACTS].count_documents({"last_contacted_at": {"$ne": None}}) == 10
    assert await db[c.AUDIT_LOGS].count_documents({"action": "recruiter.bulk_send"}) == 1
    assert await db[c.AGENT_RUNS].count_documents({"agent_name": "recruiter_bulk_send"}) == 1
    # daily cap used up: a new bulk send queues everything and sends nothing
    more = await _seed(db, [("Z", "Zeta Labs", "z@zeta.com")])
    r2 = (await client.post("/api/recruiters/bulk/send", headers=auth,
                            json={"template_id": "builtin:followup", "contact_ids": [more[0]["_id"]], "confirm": True})).json()
    assert r2["sent"] == 0 and r2["queued"] == 1 and len(sent) == 10
    # queued messages never auto-send; send-queued needs confirm and respects the cap
    assert (await client.post("/api/recruiters/bulk/send-queued", headers=auth)).status_code == 422
    q = (await client.post("/api/recruiters/bulk/send-queued", params={"confirm": True}, headers=auth)).json()
    assert q["sent"] == 0 and len(sent) == 10 and q["still_queued"] == 6
    await db[c.OUTREACH].update_many({"status": "sent"}, {"$set": {"sent_at": utcnow() - timedelta(days=8)}})  # a new day and week
    q2 = (await client.post("/api/recruiters/bulk/send-queued", params={"confirm": True}, headers=auth)).json()
    assert q2["sent"] == 6 and len(sent) == 16 and q2["still_queued"] == 0


async def test_bulk_send_filter_attachment_and_pause(client, auth, db, monkeypatch):
    assert (await client.put("/api/profile", headers=auth, json=PROFILE)).status_code == 200
    sent = await _gmail(db, monkeypatch)
    await _seed(db, [("Asha", "Infosys", "a@infosys.com"), ("Bela", "Google", "b@google.com")])
    body = {"template_id": "builtin:application", "filter": {"company_type": "service"}, "confirm": True}
    r = (await client.post("/api/recruiters/bulk/send", headers=auth, json=body)).json()
    assert r["sent"] == 1 and [s[0] for s in sent] == ["a@infosys.com"]
    uid = await _uid(db)
    await db[c.SYSTEM_SETTINGS].update_one({"user_id": uid}, {"$set": {"automation.pauses.recruiter_outreach": True}}, upsert=True)
    paused = await client.post("/api/recruiters/bulk/send", headers=auth,
                               json={"template_id": "builtin:followup", "filter": {"company_type": "product"}, "confirm": True})
    assert paused.status_code == 423 and len(sent) == 1

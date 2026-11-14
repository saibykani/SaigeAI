from app.database import collections as c
from app.debrief import extract as ex

TEXT = ("The interviewer was Priya Nair. They asked me how do you handle flaky Selenium tests? "
        "Question was explain the difference between REST and SOAP. The Python coding round went well and I nailed the SQL part. "
        "I struggled with system design and forgot the Kubernetes details. HR will get back by next Friday.")


def test_extract():
    d = ex.extract(TEXT)
    assert len(d["questions"]) == 2 and all(q.endswith("?") for q in d["questions"])
    assert {"Selenium", "Python", "SQL"} <= set(d["skills"])
    assert any("nailed" in s for s in d["went_well"])
    assert any("struggled" in s for s in d["to_improve"])
    assert d["next_steps"] and d["interviewers"] == ["Priya Nair"]
    assert ex.extract("nothing much happened here")["questions"] == []


async def test_flow(client, auth, db, monkeypatch):
    r = await client.post("/api/debriefs", headers=auth, json={"company": "Acme", "role": "SDET", "text": TEXT})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["thank_you"]["status"] == "draft" and "Asha Rao" in d["thank_you"]["body"]
    await client.post("/api/debriefs", headers=auth, json={"company": "Beta", "role": "QA", "text": TEXT})
    qb = (await client.get("/api/question-bank", headers=auth)).json()
    assert len(qb["items"]) == 2 and qb["items"][0]["count"] == 2  # deduped across debriefs
    assert len((await client.get("/api/question-bank?company=acme", headers=auth)).json()["items"]) == 2
    assert (await client.get("/api/question-bank?skill=nothing", headers=auth)).json()["items"] == []
    assert len((await client.get("/api/debriefs", headers=auth)).json()) == 2
    assert await db[c.AGENT_RUNS].count_documents({"agent_name": "interview_debrief"}) == 2
    # send needs approval, then Gmail
    url = f"/api/debriefs/{d['id']}/thank-you/send"
    assert (await client.post(url, headers=auth, json={"to": "hr@acme.com"})).status_code == 409
    r = await client.post(url, headers=auth, json={"to": "hr@acme.com", "approved": True})
    assert r.status_code == 409 and "Gmail" in r.text
    from app.email import outbound

    async def fake_sender(db, uid):
        return {"email": "a@b.com"}

    async def fake_send(*a, **k):
        return "<id>"
    monkeypatch.setattr(outbound, "find_sender", fake_sender)
    monkeypatch.setattr(outbound, "send", fake_send)
    r = await client.post(url, headers=auth, json={"to": "hr@acme.com", "approved": True})
    assert r.status_code == 200 and r.json()["thank_you"]["status"] == "sent"
    assert (await client.post(url, headers=auth, json={"to": "hr@acme.com", "approved": True})).status_code == 409
    assert (await client.delete(f"/api/debriefs/{d['id']}", headers=auth)).status_code == 204
    assert len((await client.get("/api/question-bank", headers=auth)).json()["items"]) == 2
    assert (await client.get(f"/api/debriefs/{d['id']}", headers=auth)).status_code == 404

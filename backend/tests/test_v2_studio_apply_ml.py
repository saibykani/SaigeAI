# ruff: noqa: E501
"""Studio before/after + checklist + section order, apply-by-email variants/guard/preview, ML promotion + extra features."""

from datetime import timedelta

from app.database import collections as c
from app.ml import models
from app.ml import service as ml
from app.studio import render
from app.utils import new_id, utcnow
from tests.job_fixtures import PROFILE
from tests.test_studio_apply import SDET_JD

# ------------------------------------------------------------------ studio

def test_section_order_is_cleaned_and_applied():
    assert render.clean_order(None) is None and render.clean_order(["nope"]) is None
    assert render.clean_order(["Projects", "summary", "projects"]) == ["projects", "summary", "skills", "experience", "education", "certifications"]
    t = render.with_order(render.TEMPLATES["modern"], ["education", "experience"])
    assert t.order[:2] == ("education", "experience") and len(t.order) == 6


async def test_generate_returns_before_after_checklist_and_order_applies(client, auth):
    await client.put("/api/profile", headers=auth, json=PROFILE)
    out = (await client.post("/api/studio/resume", headers=auth, json={"jd_text": SDET_JD, "title": "SDET", "company": "Acme"})).json()
    ba = out["before_after"]
    assert ba["after"] == out["ats"]["score"] and isinstance(ba["items"], list) and ba["items"]
    assert out["keyword_map"] and all({"keyword", "verified", "on_resume", "mirrored"} <= set(k) for k in out["keyword_map"])
    # the checklist lists only skills that are NOT in the verified profile, and nothing is added without a confirm
    prof_before = (await client.get("/api/profile", headers=auth)).json()
    for item in out["skill_checklist"]:
        assert item["confirmed"] is False and item["skill"] not in out["resume"]["skills"]
    assert (await client.get("/api/profile", headers=auth)).json()["skills"] == prof_before["skills"]
    if out["skill_checklist"]:
        pick = out["skill_checklist"][0]["skill"]
        assert (await client.post("/api/studio/skills/confirm", headers=auth, json={"skills": [pick]})).json()["added"] == [pick]
        again = (await client.get(f"/api/studio/resumes/{out['id']}", headers=auth)).json()
        assert pick not in [x["skill"] for x in again["skill_checklist"]]

    r = await client.post(f"/api/studio/resumes/{out['id']}/order", headers=auth, json={"order": ["education", "experience", "skills"]})
    assert r.status_code == 200 and r.json()["section_order"][:3] == ["education", "experience", "skills"]
    assert (await client.post(f"/api/studio/resumes/{out['id']}/order", headers=auth, json={"order": ["bogus"]})).status_code == 422
    got = (await client.get(f"/api/studio/resumes/{out['id']}", headers=auth)).json()
    assert got["section_order"][0] == "education" and got["html"].lower().index("education") < got["html"].lower().index("experience")
    for fmt in ("pdf", "docx", "txt"):
        assert (await client.get(f"/api/studio/resumes/{out['id']}/download?format={fmt}", headers=auth)).status_code == 200


# ------------------------------------------------------------------ ML

def test_platt_calibration_and_promotion_rule():
    assert models.platt_fit([0.5] * 3, [1, 0, 1]) == (1.0, 0.0)  # too little data -> identity
    scores = [0.9, 0.95, 0.85, 0.9, 0.92, 0.88, 0.8, 0.9, 0.85, 0.95, 0.9, 0.8]
    y = [1, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 0]  # over-confident scores
    a, b = models.platt_fit(scores, y)
    m = models.LogisticModel({"x": 1.0}, (a, b))
    assert m.predict({"x": 2.0}) < models.sigmoid(2.0)
    assert models.beats({"auc": 0.9}, {"auc": 0.8}) and not models.beats({"auc": 0.7}, {"auc": 0.8})
    assert models.beats({"accuracy": 0.7}, None) and not models.beats(None, {"auc": 0.5})


def test_new_features_cover_title_overlap_seniority_location_company_source():
    ctx = {"roles": [{"senior", "engineer"}], "locations": {"hyderabad"}, "years": 6, "remote": None, "company_rate": {"acme": 0.75}}
    job = {"title": "Senior QA Engineer", "company": "Acme", "matched_skills": ["a", "b", "c"], "missing_skills": ["d"], "city": "Hyderabad",
           "source": "greenhouse", "scope": "country"}
    x = ml.features(job, ctx)
    assert x["title_sim"] > 0.5 and x["skill_overlap"] == 0.75 and x["seniority_match"] == 1.0
    assert x["loc_fit"] == 1.0 and x["company_rate"] == 0.75 and x["source:greenhouse"] == 1.0
    assert "title_sim" not in ml.features(job)  # no context -> only context-free features


async def _label(client, auth, db, careers, n):  # noqa: ANN001
    return None


async def test_worse_model_is_not_promoted_and_history_is_kept(client, auth, db):
    me = await client.get("/api/auth/me", headers=auth)
    uid = (me.json().get("id") or me.json().get("_id")) if me.status_code == 200 else (await db[c.USERS].find_one({}))["_id"]
    for i in range(16):
        await db[c.ML_SAMPLES].insert_one({"_id": f"{uid}:j{i}", "user_id": uid, "job_id": f"j{i}", "label": i % 2, "weight": 1.0,
                                           "source": "feedback",
                                           "features": {"bias": 1.0, "match": 0.9 if i % 2 else 0.1}, "text": "qa", "created_at": utcnow()})
    first = await ml.train(db, uid, trigger="manual")
    assert first["status"] == "trained" and first["promoted"] and "brier" in first["metrics"] and first["metrics"]["calibration"]
    # pretend the current model was perfect on k-fold: a retrain can't beat it, so it is kept
    await db[c.ML_MODELS].update_one({"_id": f"{uid}:relevance"}, {"$set": {"metrics": {"auc": 1.0, "accuracy": 1.0, "brier_calibrated": 0.0}}})
    for i in range(16):  # noisy new labels make the candidate worse
        await db[c.ML_SAMPLES].update_one({"_id": f"{uid}:j{i}"}, {"$set": {"label": (i // 2) % 2}})
    second = await ml.train(db, uid, trigger="daily")
    assert second["status"] == "kept_current" and second["promoted"] is False and second["version"] == first["version"]
    st = await ml.status(db, uid)
    hist = st["relevance"]["history"]
    assert len(hist) == 2 and hist[0]["promoted"] is False and hist[1]["promoted"] is True
    assert st["relevance"]["calibration"] and st["history"][0]["trigger"] == "daily"


# ------------------------------------------------------------------ apply by email

async def _app(client, auth, db, company="Acme", role="SDET"):
    await client.put("/api/profile", headers=auth, json=PROFILE)
    me = await db[c.USERS].find_one({"email": "asha@example.com"})
    uid = me["_id"]
    jid, aid = new_id(), new_id()
    await db[c.JOBS].insert_one({"_id": jid, "user_id": uid, "title": role, "company": company, "description": SDET_JD, "analysis": {
        "required_skills": ["Selenium", "Java"]}, "created_at": utcnow()})
    await db[c.APPLICATIONS].insert_one({"_id": aid, "user_id": uid, "job_id": jid, "company": company, "role": role, "status": "READY_TO_APPLY",
                                         "apply_email": "hr@acme.com", "resume_id": None, "auto": True, "created_at": utcnow()})
    return uid, aid


async def test_email_variants_preview_and_company_guard(client, auth, db, monkeypatch):
    from app.jobs import auto_apply

    uid, aid = await _app(client, auth, db)
    r = await client.post("/api/applications/approve-preview", headers=auth, json={"ids": [aid]})
    assert r.status_code == 200, r.text
    p = r.json()["items"][0]
    assert p["to"] == "hr@acme.com" and p["needs_approval"] == "USER_APPROVAL_REQUIRED" and len(p["variants"]) >= 2
    assert p["resume"]["will_tailor"] is True and p["company_guard"]["blocked"] is False
    r2 = await client.post("/api/applications/approve-preview", headers=auth, json={"ids": [aid], "variants": {aid: "concise"}})
    skills = r2.json()["items"][0]
    assert skills["variant"] == "concise" and skills["diff"] and any(d["op"] == "add" for d in skills["diff"])
    assert "Dear Hiring Team" not in skills["body"]
    assert (await db[c.SENT_EMAILS].count_documents({})) == 0  # preview sends nothing

    # reply rate per variant decides the default once there is enough data
    names = {"Direct": (6, 0), "Skills-led": (6, 3), "Concise": (6, 1)}
    for name, (n, replies) in names.items():
        for i in range(n):
            await db[c.SENT_EMAILS].insert_one({"_id": new_id(), "user_id": uid, "kind": "auto_apply", "template_name": f"Auto-apply: {name}",
                                                "to_email": f"x{i}@{name}.com", "to_domain": f"{name}.com", "company": f"Other{name}{i}",
                                                "subject": "s", "status": "replied" if i < replies else "sent", "sent_at": utcnow() - timedelta(days=40)})
    best = (await client.post("/api/applications/approve-preview", headers=auth, json={"ids": [aid]})).json()["items"][0]
    assert best["variant"] == "skills" and "best reply rate" in best["variant_reason"]
    assert {t["key"] for t in best["template_stats"]} == set(names)

    # one application email per company inside the cool-down window
    await db[c.SENT_EMAILS].insert_one({"_id": new_id(), "user_id": uid, "kind": "auto_apply", "template_name": "Auto-apply: Direct",
                                        "company": "Acme", "role": "QA", "to_email": "hr@acme.com", "to_domain": "acme.com", "subject": "s",
                                        "status": "sent", "sent_at": utcnow()})
    assert await auto_apply.company_recently_emailed(db, uid, "ACME Inc".replace(" Inc", ""))
    assert (await client.post("/api/applications/approve-preview", headers=auth, json={"ids": [aid]})).json()["items"][0]["company_guard"]["blocked"]
    from app.email import imap, smtp
    from tests.test_discover_send import FakeSMTP
    from tests.test_gmail_imap import FakeIMAP

    monkeypatch.setattr(smtp, "SMTP_FACTORY", FakeSMTP)
    monkeypatch.setattr(imap, "IMAP_FACTORY", FakeIMAP)
    await client.post("/api/auth/connect/gmail-app-password", headers=auth, json={"email": "asha@gmail.com", "app_password": "abcdefghijklmnop"})
    out = (await client.post("/api/applications/approve-bulk", headers=auth, json={"ids": [aid], "follow_up_days": 5})).json()
    assert out["errors"] == 1 and "already emailed" in out["results"][0]["message"].lower()


async def test_followup_reminder_is_scheduled(client, auth, db):
    from app.jobs import auto_apply

    uid, aid = await _app(client, auth, db, "Beta")
    a = await db[c.APPLICATIONS].find_one({"_id": aid})
    await auto_apply.schedule_followup(db, a, 5)
    f = await db[c.FOLLOWUPS].find_one({"application_id": aid, "custom": True})
    assert f and f["status"] == "scheduled" and 4 <= (f["due_at"] - utcnow()).days <= 5


async def test_approve_and_send_one_call(client, auth, db, monkeypatch):
    from app.email import imap, smtp
    from tests.test_discover_send import FakeSMTP
    from tests.test_gmail_imap import FakeIMAP

    FakeSMTP.sent = []
    monkeypatch.setattr(smtp, "SMTP_FACTORY", FakeSMTP)
    monkeypatch.setattr(imap, "IMAP_FACTORY", FakeIMAP)
    uid, aid = await _app(client, auth, db, "Gamma")
    no = await client.post(f"/api/applications/{aid}/approve-and-send", headers=auth)
    assert no.status_code == 409 and "Gmail" in no.json()["detail"] and not FakeSMTP.sent  # inline-friendly error
    await client.post("/api/auth/connect/gmail-app-password", headers=auth, json={"email": "asha@gmail.com", "app_password": "abcdefghijklmnop"})
    r = await client.post(f"/api/applications/{aid}/approve-and-send", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "sent" and len(FakeSMTP.sent) == 1 and FakeSMTP.sent[0]["To"] == "hr@acme.com"
    assert (await db[c.APPLICATIONS].find_one({"_id": aid}))["status"] == "APPLIED"
    audit = await db[c.AUDIT_LOGS].find_one({"action": "application.approved_and_sent"})
    assert audit["details"]["approval"] == "explicit_user_click"
    again = await client.post(f"/api/applications/{aid}/approve-and-send", headers=auth)  # 14-day company guard
    assert again.status_code == 409 and len(FakeSMTP.sent) == 1

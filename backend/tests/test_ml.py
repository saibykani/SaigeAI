from app.database import collections as c
from app.ml.models import LogisticModel, NaiveBayes, auc, evaluate
from tests.test_careers import _setup, careers  # noqa: F401 - fixture reused


def test_logistic_model_learns_a_preference():
    # the user likes manual-testing roles in Hyderabad and dislikes automation roles elsewhere
    X, y = [], []
    for i in range(30):
        like = i % 2 == 0
        x = {"bias": 1.0, "type:manual" if like else "type:automation": 1.0, f"city:{'hyderabad' if like else 'pune'}": 1.0,
             "match": 0.5 + (i % 5) / 20}
        X.append(x)
        y.append(int(like))
    m = LogisticModel().fit(X, y)
    assert m.predict({"bias": 1.0, "type:manual": 1.0, "city:hyderabad": 1.0}) > 0.8
    assert m.predict({"bias": 1.0, "type:automation": 1.0, "city:pune": 1.0}) < 0.2
    pos, neg = m.top()
    assert {k for k, _ in pos} & {"type:manual", "city:hyderabad"} and {k for k, _ in neg} & {"type:automation", "city:pune"}
    metrics = evaluate(X, y, [1.0] * len(X))
    assert metrics["accuracy"] >= 0.9 and metrics["auc"] >= 0.9
    assert auc([0.9, 0.1], [1, 0]) == 1.0 and auc([0.5], [1]) is None


def test_naive_bayes_job_type():
    nb = NaiveBayes().fit(["Manual tester regression test cases exploratory", "Selenium automation framework java",
                           "UAT functional testing manual", "Playwright cypress automation pipelines"],
                          ["manual", "automation", "manual", "automation"])
    assert nb.predict("manual regression testing of web app")[0] == "manual"
    assert nb.predict("selenium playwright automation")[0] == "automation"
    assert NaiveBayes(nb.state()).predict("cypress automation")[0] == "automation"


async def test_feedback_trains_ranks_and_suggests_tasks(client, auth, db, careers):  # noqa: F811
    await _setup(client, auth)
    await client.post("/api/careers/scan", headers=auth, json={})
    st = (await client.get("/api/ml/status", headers=auth)).json()
    assert st["relevance"]["trained"] is False
    tasks = (await client.get("/api/ml/tasks", headers=auth)).json()["items"]
    assert tasks and all("id" in t for t in tasks)
    jobs = await db[c.CAREER_JOBS].find({}).to_list(None)
    # not enough data yet: honest message
    r = await client.post("/api/ml/train", headers=auth)
    assert r.json()["status"] == "needs_data"
    # rate: like Indian postings, dislike abroad ones; repeat ratings on the same jobs overwrite, so add synthetic samples
    for d in jobs:
        rating = "up" if d.get("scope") != "abroad" else "down"
        assert (await client.post("/api/ml/feedback", headers=auth, json={"job_id": d["_id"], "rating": rating})).status_code == 200
    me = await db[c.USERS].find_one({"email": "asha@example.com"})
    for i in range(6):  # more labelled history (closed postings the user rated earlier)
        await db[c.ML_SAMPLES].insert_one({"_id": f"h{i}", "user_id": me["_id"], "job_id": f"old{i}", "label": i % 2,
                                           "weight": 1.0, "source": "feedback", "text": "QA",
                                           "features": {"bias": 1.0, "where:country" if i % 2 else "where:abroad": 1.0}})
    out = (await client.post("/api/ml/train", headers=auth)).json()
    assert out["status"] == "trained" and out["version"] >= 1 and out["scored"] >= 1
    assert out["metrics"]["accuracy"] is not None
    scored = await db[c.CAREER_JOBS].find({"ai_score": {"$ne": None}}).to_list(None)
    assert scored and all(0 <= d["ai_score"] <= 100 for d in scored)
    picks = (await client.get("/api/careers/jobs?sort=learned&fresh_first=false", headers=auth)).json()["items"]
    assert picks[0]["ai_score"] >= picks[-1]["ai_score"]
    st = (await client.get("/api/ml/status", headers=auth)).json()
    assert st["relevance"]["trained"] and st["history"] and st["labels"]["total"] >= 4
    assert st["relevance"]["top_positive"] or st["relevance"]["top_negative"]
    # job-type corrections are stored and pin the type
    fix = await client.post("/api/ml/feedback", headers=auth, json={"job_id": jobs[0]["_id"], "category": "manual"})
    assert fix.status_code == 200
    assert (await db[c.CAREER_JOBS].find_one({"_id": jobs[0]["_id"]}))["category_src"] == "user"
    assert await db[c.AGENT_RUNS].count_documents({"agent_name": "saige_learning"}) >= 2


async def test_behaviour_signals_and_starter_labels_feed_the_model(client, auth, db, careers):  # noqa: F811
    from app.ml import service as ml

    await _setup(client, auth)
    await client.post("/api/careers/scan", headers=auth, json={})
    me = await db[c.USERS].find_one({"email": "asha@example.com"})
    jobs = await db[c.CAREER_JOBS].find({}).to_list(None)
    # opening a job is a weak positive; a rating outranks it and is never overwritten by a weaker signal
    await client.get(f"/api/careers/jobs/{jobs[0]['_id']}", headers=auth)
    s = await db[c.ML_SAMPLES].find_one({"job_id": jobs[0]["_id"]})
    assert s["source"] == "opened" and s["label"] == 1 and s["weight"] == 0.3
    await client.post("/api/ml/feedback", headers=auth, json={"job_id": jobs[0]["_id"], "rating": "down"})
    await ml.record_implicit(db, me["_id"], jobs[0], "opened")
    s = await db[c.ML_SAMPLES].find_one({"job_id": jobs[0]["_id"]})
    assert s["source"] == "feedback" and s["label"] == 0
    # building a resume for a job is a strong positive
    r = await client.post("/api/studio/resume", headers=auth, json={"career_job_id": jobs[1]["_id"]})
    assert r.status_code == 201, r.text
    assert (await db[c.ML_SAMPLES].find_one({"job_id": jobs[1]["_id"]}))["source"] == "resume"
    # starter labels from very strong / very weak matches bootstrap the model
    for i in range(8):
        await db[c.CAREER_JOBS].insert_one({**jobs[2], "_id": f"seed{i}", "item_id": f"seed{i}", "score": 90 if i % 2 else 20,
                                            "title": "Manual QA Tester" if i % 2 else "Sales Manager"})
    out = await ml.train(db, me["_id"], trigger="manual")
    assert out["status"] == "trained" and out["auto_labels"] >= 8 and out["sources"]["feedback"] == 1
    st = (await client.get("/api/ml/status", headers=auth)).json()
    assert st["relevance"]["features"] > 10 and st["relevance"]["sources"]["resume"] == 1
    assert "bootstrapped" in st["relevance"]["metrics"]

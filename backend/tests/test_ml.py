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

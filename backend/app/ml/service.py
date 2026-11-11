"""Saige learning: per-user models that improve with every rating, save and application outcome.

Two models, both trained only on this user's own data:

* relevance: logistic regression that predicts how likely the user is to want a posting (👍, saved, applied,
  interview or offer = positive; 👎, rejected = negative). It ranks Career portals (sort "Saige picks").
* job type: naive Bayes over title + description, trained on the user's job-type corrections, that re-labels
  postings whose type came from the built-in rules once it has enough examples.

Training runs after every few new labels, daily from the scheduler, and on demand. Each run is evaluated with
cross-validation and recorded (agent run, audit log, history), so the user sees whether it is getting better.
"Training tasks" pick the postings the model is least sure about (uncertainty sampling) for the user to rate.
"""

import math

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING, UpdateOne

from app.database import collections as c
from app.ml.models import LogisticModel, NaiveBayes, evaluate, tokens
from app.services.agent_runs import agent_run
from app.services.audit import log_action
from app.utils import new_id, utcnow

MIN_SAMPLES = 6          # with both classes present
MIN_TYPE_SAMPLES = 6
RETRAIN_EVERY = 5        # new labels between automatic retrains
POSITIVE = {"RECRUITER_REPLIED", "SCREENING", "ASSESSMENT", "INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED", "OFFER"}
NEGATIVE = {"REJECTED"}
TYPES = ("manual", "automation", "qa", "other")


def features(d: dict) -> dict[str, float]:
    x: dict[str, float] = {"bias": 1.0, "match": (d.get("score") or 0) / 100, f"fit:{d.get('fit')}": 1.0,
                           f"type:{d.get('category') or 'other'}": 1.0, f"where:{d.get('scope') or 'unknown'}": 1.0,
                           f"company:{d.get('company_id')}": 1.0}
    for t in d.get("tiers") or []:
        x[f"group:{t}"] = 1.0
    for w in set(tokens(d.get("title") or "")):
        x[f"title:{w}"] = 1.0
    x["skills_matched"] = min(len(d.get("matched_skills") or []), 8) / 8
    x["skills_missing"] = min(len(d.get("missing_skills") or []), 6) / 6
    if d.get("exp_min") is not None:
        x[f"exp:{'0-2' if d['exp_min'] < 3 else '3-5' if d['exp_min'] < 6 else '6+'}"] = 1.0
    if d.get("salary_lpa") is not None:
        x["pay_listed"] = 1.0
    if d.get("remote"):
        x["remote"] = 1.0
    if d.get("city"):
        x[f"city:{d['city'].lower()}"] = 1.0
    return x


def _text(d: dict) -> str:
    return f"{d.get('title') or ''} {d.get('title') or ''} {(d.get('description') or d.get('snippet') or '')[:1500]}"


def label_name(k: str) -> str:
    kind, _, v = k.partition(":")
    names = {"match": "Saige match score", "skills_matched": "Skills you match", "skills_missing": "Skills you're missing",
             "pay_listed": "Pay listed", "remote": "Remote", "bias": "Baseline"}
    if not v:
        return names.get(k, k)
    return {"title": f"“{v}” in title", "company": f"Company: {v}", "group": f"Group: {v.replace('_', ' ')}", "type": f"Job type: {v}",
            "fit": f"Fit: {v}", "where": f"Where: {v}", "exp": f"Experience {v} yrs", "city": f"City: {v.title()}"}.get(kind, k)


# ------------------------------------------------------------------ labels

async def record(db: AsyncIOMotorDatabase, uid: str, job: dict, *, label: int | None = None, category: str | None = None,
                 source: str = "feedback", weight: float = 1.0) -> dict:
    """Store a training example (a snapshot, so it survives the posting closing)."""
    sid = f"{uid}:{job['_id']}"
    s = {"user_id": uid, "job_id": job["_id"], "features": features(job), "text": _text(job), "updated_at": utcnow()}
    if label is not None:
        s.update(label=int(label), weight=weight, source=source)
    if category:
        s["category"] = category
    await db[c.ML_SAMPLES].update_one({"_id": sid}, {"$set": s, "$setOnInsert": {"created_at": utcnow()}}, upsert=True)
    state = await db[c.ML_MODELS].find_one({"_id": f"{uid}:relevance"}, {"labels_since": 1}) or {}
    n = state.get("labels_since", 0) + 1
    await db[c.ML_MODELS].update_one({"_id": f"{uid}:relevance"}, {"$set": {"user_id": uid, "labels_since": n}}, upsert=True)
    trained = None
    if n >= RETRAIN_EVERY:
        trained = await train(db, uid, trigger="auto")
    return {"saved": True, "labels_since_training": 0 if trained else n, "trained": trained}


async def _harvest_outcomes(db: AsyncIOMotorDatabase, uid: str) -> int:
    """Saved postings and application outcomes become training labels automatically."""
    saved = await db[c.CAREER_JOBS].find({"user_id": uid, "saved_job_id": {"$ne": None}}).to_list(2000)
    if not saved:
        return 0
    apps = {a["job_id"]: a["status"] for a in await db[c.APPLICATIONS].find(
        {"user_id": uid, "job_id": {"$in": [d["saved_job_id"] for d in saved]}}, {"job_id": 1, "status": 1}).to_list(2000)}
    have = {s["job_id"]: s for s in await db[c.ML_SAMPLES].find({"user_id": uid, "job_id": {"$in": [d["_id"] for d in saved]}},
                                                                 {"job_id": 1, "source": 1, "label": 1}).to_list(2000)}
    n = 0
    for d in saved:
        st = apps.get(d["saved_job_id"])
        prev = have.get(d["_id"])
        if prev and prev.get("source") == "feedback":
            continue  # the user's own rating wins
        if st in POSITIVE:
            label, weight, src = 1, 2.0, "outcome"
        elif st in NEGATIVE:
            label, weight, src = 0, 1.0, "outcome"
        else:
            label, weight, src = 1, 0.5, "saved"
        if prev and prev.get("source") == src and prev.get("label") == label:
            continue
        await db[c.ML_SAMPLES].update_one({"_id": f"{uid}:{d['_id']}"}, {"$set": {
            "user_id": uid, "job_id": d["_id"], "features": features(d), "text": _text(d), "label": label, "weight": weight,
            "source": src, "updated_at": utcnow()}, "$setOnInsert": {"created_at": utcnow()}}, upsert=True)
        n += 1
    return n


# ------------------------------------------------------------------ training

async def train(db: AsyncIOMotorDatabase, uid: str, *, trigger: str = "manual") -> dict:
    async with agent_run(db, "saige_learning", uid, {"trigger": trigger}) as run:
        harvested = await _harvest_outcomes(db, uid)
        samples = await db[c.ML_SAMPLES].find({"user_id": uid}).to_list(5000)
        rel = [s for s in samples if s.get("label") is not None]
        X, y, sw = [s["features"] for s in rel], [s["label"] for s in rel], [s.get("weight", 1.0) for s in rel]
        out: dict = {"trigger": trigger, "samples": len(rel), "positives": sum(y), "negatives": len(y) - sum(y), "harvested": harvested,
                     "trained_at": utcnow()}
        prev = await db[c.ML_MODELS].find_one({"_id": f"{uid}:relevance"}) or {}
        if len(rel) >= MIN_SAMPLES and 0 < sum(y) < len(y):
            metrics = evaluate(X, y, sw)
            model = LogisticModel().fit(X, y, sw)
            version = (prev.get("version") or 0) + 1
            pos, neg = model.top()
            await db[c.ML_MODELS].replace_one({"_id": f"{uid}:relevance"}, {
                "_id": f"{uid}:relevance", "user_id": uid, "kind": "relevance", "weights": model.w, "version": version, "metrics": metrics,
                "samples": len(rel), "positives": sum(y), "trained_at": out["trained_at"], "labels_since": 0,
                "top_positive": [[label_name(k), v] for k, v in pos], "top_negative": [[label_name(k), v] for k, v in neg]}, upsert=True)
            out.update(status="trained", version=version, metrics=metrics, previous=prev.get("metrics"))
            out["scored"] = await score_all(db, uid)
        else:
            need = max(0, MIN_SAMPLES - len(rel))
            out.update(status="needs_data", message=(f"Rate {need} more job(s)" if need else "Rate at least one job you like and one you don't")
                       + " so Saige can learn what you want.")
            await db[c.ML_MODELS].update_one({"_id": f"{uid}:relevance"}, {"$set": {"user_id": uid, "labels_since": 0}}, upsert=True)
        out["job_type"] = await _train_types(db, uid, samples)
        run.output = {k: out.get(k) for k in ("status", "samples", "version")}
        run.action(f"trained on {len(rel)} labelled job(s)")
    await db[c.ML_RUNS].insert_one({"_id": new_id(), "user_id": uid, **{k: v for k, v in out.items() if k != "previous"}})
    await log_action(db, user_id=uid, action="ml.trained", entity="ml_model",
                     details={"status": out["status"], "samples": out["samples"], "metrics": out.get("metrics"), "trigger": trigger})
    return out


async def _train_types(db: AsyncIOMotorDatabase, uid: str, samples: list[dict]) -> dict:
    typed = [s for s in samples if s.get("category") in TYPES]
    if len(typed) < MIN_TYPE_SAMPLES or len({s["category"] for s in typed}) < 2:
        return {"status": "needs_data", "corrections": len(typed), "needed": MIN_TYPE_SAMPLES}
    nb = NaiveBayes().fit([s["text"] for s in typed], [s["category"] for s in typed])
    await db[c.ML_MODELS].replace_one({"_id": f"{uid}:job_type"}, {"_id": f"{uid}:job_type", "user_id": uid, "kind": "job_type",
                                                                  "state": nb.state(), "samples": len(typed), "trained_at": utcnow()}, upsert=True)
    # Re-label postings whose type came from the rules, when the learned model is confident.
    ops = []
    async for d in db[c.CAREER_JOBS].find({"user_id": uid, "active": True, "category_src": {"$ne": "user"}},
                                          {"title": 1, "description": 1, "snippet": 1, "category": 1}):
        lab, p = nb.predict(_text(d))
        if lab and p >= 0.8 and lab != d.get("category"):
            ops.append(UpdateOne({"_id": d["_id"]}, {"$set": {"category": lab, "category_src": "learned"}}))
    if ops:
        from app.careers.service import _bulk_upsert
        await _bulk_upsert(db, ops)
    return {"status": "trained", "corrections": len(typed), "relabelled": len(ops)}


async def score_all(db: AsyncIOMotorDatabase, uid: str, *, only_missing: bool = False) -> int:
    """Store the learned relevance (0-100) on every active posting so lists can sort by it."""
    m = await db[c.ML_MODELS].find_one({"_id": f"{uid}:relevance", "weights": {"$exists": True}}, {"weights": 1, "version": 1})
    if not m:
        return 0
    model = LogisticModel(m["weights"])
    q: dict = {"user_id": uid, "active": True}
    if only_missing:
        q["$or"] = [{"ai_version": None}, {"ai_version": {"$ne": m["version"]}}]
    ops = []
    async for d in db[c.CAREER_JOBS].find(q, {"description": 0}):
        ops.append(UpdateOne({"_id": d["_id"]}, {"$set": {"ai_score": round(100 * model.predict(features(d))), "ai_version": m["version"]}}))
    from app.careers.service import _bulk_upsert
    if ops:
        await _bulk_upsert(db, ops)
    return len(ops)


# ------------------------------------------------------------------ tasks and status

async def tasks(db: AsyncIOMotorDatabase, uid: str, n: int = 10) -> list[dict]:
    """Postings to rate next: the ones the model is least sure about, or a spread of fits before it exists."""
    rated = {s["job_id"] for s in await db[c.ML_SAMPLES].find({"user_id": uid, "label": {"$ne": None}}, {"job_id": 1}).to_list(5000)}
    base = {"user_id": uid, "active": True, "_id": {"$nin": list(rated)}}
    proj = {"description": 0}
    if await db[c.ML_MODELS].find_one({"_id": f"{uid}:relevance", "weights": {"$exists": True}}, {"_id": 1}):
        pool = await db[c.CAREER_JOBS].find({**base, "ai_score": {"$ne": None}}, proj).limit(800).to_list(800)
        pool.sort(key=lambda d: abs((d.get("ai_score") or 50) - 50))
        picks = pool[:n]
        why = "Saige isn't sure about these"
    else:
        picks = []
        for fit in ("strong", "good", "stretch", "low"):
            picks += await db[c.CAREER_JOBS].find({**base, "fit": fit}, proj).sort("first_seen", DESCENDING).limit(math.ceil(n / 4)).to_list(n)
        picks = picks[:n]
        why = "A mix of fits to learn your taste"
    return [{"id": d["_id"], "title": d["title"], "company": d["company"], "location": d.get("location"), "score": d.get("score"),
             "ai_score": d.get("ai_score"), "category": d.get("category"), "url": d.get("url") or d.get("careers_url"), "why": why} for d in picks]


async def status(db: AsyncIOMotorDatabase, uid: str) -> dict:
    rel = await db[c.ML_MODELS].find_one({"_id": f"{uid}:relevance"}) or {}
    typ = await db[c.ML_MODELS].find_one({"_id": f"{uid}:job_type"}) or {}
    counts = {"total": await db[c.ML_SAMPLES].count_documents({"user_id": uid, "label": {"$ne": None}}),
              "liked": await db[c.ML_SAMPLES].count_documents({"user_id": uid, "label": 1}),
              "disliked": await db[c.ML_SAMPLES].count_documents({"user_id": uid, "label": 0}),
              "type_corrections": await db[c.ML_SAMPLES].count_documents({"user_id": uid, "category": {"$in": list(TYPES)}})}
    runs = await db[c.ML_RUNS].find({"user_id": uid}).sort("trained_at", DESCENDING).limit(12).to_list(12)
    return {
        "relevance": {"trained": "weights" in rel, "version": rel.get("version"), "metrics": rel.get("metrics"), "samples": rel.get("samples"),
                      "trained_at": rel["trained_at"].isoformat() if rel.get("trained_at") else None,
                      "top_positive": rel.get("top_positive", []), "top_negative": rel.get("top_negative", []),
                      "labels_since": rel.get("labels_since", 0), "retrain_every": RETRAIN_EVERY, "min_samples": MIN_SAMPLES},
        "job_type": {"trained": "state" in typ, "samples": typ.get("samples", 0), "min_samples": MIN_TYPE_SAMPLES},
        "labels": counts,
        "history": [{"trained_at": r["trained_at"].isoformat(), "status": r["status"], "samples": r["samples"], "trigger": r.get("trigger"),
                     "version": r.get("version"), "accuracy": (r.get("metrics") or {}).get("accuracy"), "auc": (r.get("metrics") or {}).get("auc")}
                    for r in runs],
    }

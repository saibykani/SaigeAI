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
import re
from datetime import timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING, UpdateOne

from app.database import collections as c
from app.ml.models import LogisticModel, NaiveBayes, beats, evaluate, metric_score, tokens
from app.services.agent_runs import agent_run
from app.services.audit import log_action
from app.utils import as_utc, new_id, utcnow

MIN_SAMPLES = 6          # with both classes present
MIN_TYPE_SAMPLES = 6
RETRAIN_EVERY = 3        # new feedback events (ratings, saves, outcomes) between automatic retrains
HISTORY_KEEP = 25        # model versions kept in the history shown to the user
POSITIVE = {"RECRUITER_REPLIED", "SCREENING", "ASSESSMENT", "INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED", "OFFER"}
STRONG_POSITIVE = {"SCREENING", "ASSESSMENT", "INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED", "OFFER"}  # interviews count more than replies
NEGATIVE = {"REJECTED"}
TYPES = ("manual", "automation", "qa", "other")


_SENIORITY = (("intern", 0), ("trainee", 0), ("junior", 1), ("jr", 1), ("associate", 1), ("senior", 3), ("sr", 3), ("lead", 4),
              ("staff", 4), ("principal", 5), ("architect", 5), ("manager", 5), ("head", 6), ("director", 6))


def seniority_of_title(title: str) -> int | None:
    words = set(re.findall(r"[a-z]+", (title or "").lower()))
    hits = [lvl for w, lvl in _SENIORITY if w in words]
    return max(hits) if hits else None


def seniority_of_years(years: float | None) -> int | None:
    if years is None:
        return None
    return 0 if years < 1 else 1 if years < 3 else 2 if years < 5 else 3 if years < 8 else 4


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


async def context(db: AsyncIOMotorDatabase, uid: str) -> dict:
    """What the extra features compare a posting with: your target roles, locations, experience and how each company has answered you."""
    from app.profiles.service import get_profile

    ctx: dict = {"roles": [], "locations": set(), "years": None, "remote": None, "company_rate": {}}
    try:
        prof = await get_profile(db, uid)
        ctx["roles"] = [set(tokens(r)) for r in [*prof.preferences.target_roles, prof.personal.current_designation or ""] if r]
        ctx["locations"] = {x.lower() for x in prof.preferences.preferred_locations}
        ctx["years"] = prof.personal.total_experience_years
        ctx["remote"] = prof.preferences.remote_preference
    except Exception:  # noqa: BLE001, S110 - a missing profile only means fewer features
        pass
    sent: dict[str, list[int]] = {}
    async for e in db[c.SENT_EMAILS].find({"user_id": uid, "company": {"$ne": None}}, {"company": 1, "status": 1}):
        b = sent.setdefault((e["company"] or "").lower(), [0, 0])
        b[0] += 1
        b[1] += e.get("status") == "replied"
    async for a in db[c.APPLICATIONS].find({"user_id": uid}, {"company": 1, "status": 1}):
        b = sent.setdefault((a.get("company") or "").lower(), [0, 0])
        b[0] += 1
        b[1] += a.get("status") in POSITIVE
    ctx["company_rate"] = {k: (v[1] + 0.5) / (v[0] + 1) for k, v in sent.items() if k and v[0]}  # smoothed past response rate
    return ctx


def extra_features(d: dict, ctx: dict | None) -> dict[str, float]:
    """title similarity, skill overlap ratio, seniority match, location/remote fit, company past-response rate, source."""
    x: dict[str, float] = {}
    got, lack = len(d.get("matched_skills") or []), len(d.get("missing_skills") or [])
    if got + lack:
        x["skill_overlap"] = got / (got + lack)
    if d.get("source") or d.get("provider"):
        x[f"source:{d.get('source') or d.get('provider')}"] = 1.0
    if not ctx:
        return x
    title = set(tokens(d.get("title") or ""))
    if ctx.get("roles"):
        x["title_sim"] = round(max(_jaccard(title, r) for r in ctx["roles"]), 3)
    want, mine = seniority_of_title(d.get("title") or ""), seniority_of_years(ctx.get("years"))
    if want is not None and mine is not None:
        x["seniority_match"] = 1.0 if want == mine else 0.5 if abs(want - mine) == 1 else 0.0
    city = (d.get("city") or d.get("location") or "").lower()
    if d.get("remote") and ctx.get("remote") is not False:
        x["loc_fit"] = 1.0
    elif city and any(loc in city for loc in ctx.get("locations") or ()):
        x["loc_fit"] = 1.0
    elif d.get("scope") == "country":
        x["loc_fit"] = 0.6
    rate = (ctx.get("company_rate") or {}).get((d.get("company") or "").lower())
    if rate is not None:
        x["company_rate"] = round(rate, 3)
    return x


def features(d: dict, ctx: dict | None = None) -> dict[str, float]:
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
    # which of your skills the job wants, which gaps it has, and the words its description uses
    for s in (d.get("matched_skills") or [])[:8]:
        x[f"skill:{s.lower()}"] = 1.0
    for s in (d.get("missing_skills") or [])[:6]:
        x[f"gap:{s.lower()}"] = 1.0
    seen: set[str] = set()
    for w in tokens(d.get("description") or d.get("snippet") or "", 2500):
        if w not in seen and len(seen) < 40:
            seen.add(w)
            x[f"w:{w}"] = 0.3
    x.update(extra_features(d, ctx))
    return x


def _text(d: dict) -> str:
    return f"{d.get('title') or ''} {d.get('title') or ''} {(d.get('description') or d.get('snippet') or '')[:1500]}"


def label_name(k: str) -> str:
    kind, _, v = k.partition(":")
    names = {"match": "Saige match score", "skills_matched": "Skills you match", "skills_missing": "Skills you're missing",
             "pay_listed": "Pay listed", "remote": "Remote", "bias": "Baseline", "title_sim": "Title close to your target roles",
             "skill_overlap": "Share of the job's skills you have", "seniority_match": "Seniority fits your experience",
             "loc_fit": "Location / remote fit", "company_rate": "Company has replied to you before"}
    if not v:
        return names.get(k, k)
    return {"title": f"“{v}” in title", "company": f"Company: {v}", "group": f"Group: {v.replace('_', ' ')}", "type": f"Job type: {v}",
            "fit": f"Fit: {v}", "where": f"Where: {v}", "exp": f"Experience {v} yrs", "city": f"City: {v.title()}",
            "skill": f"Wants your skill: {v}", "gap": f"Needs a skill you lack: {v}", "source": f"Source: {v}",
            "w": f"“{v}” in description"}.get(kind, k)


# Stronger evidence wins: a rating beats an outcome, which beats a resume built, a save, an open, an automatic label.
PRIORITY = {"feedback": 6, "outcome": 5, "resume": 4, "saved": 3, "analyzed": 2, "opened": 1}
IMPLICIT = {"resume": (1, 1.0), "analyzed": (1, 0.6), "opened": (1, 0.3)}


async def record_implicit(db: AsyncIOMotorDatabase, uid: str, job: dict, kind: str) -> None:
    """What you do teaches Saige too: opening a job, analysing it or building a resume for it are positive signals."""
    label, weight = IMPLICIT[kind]
    prev = await db[c.ML_SAMPLES].find_one({"_id": f"{uid}:{job['_id']}"}, {"source": 1})
    if prev and PRIORITY.get(prev.get("source") or "", 0) >= PRIORITY[kind]:
        return
    await record(db, uid, job, label=label, source=kind, weight=weight)


# ------------------------------------------------------------------ labels

async def record(db: AsyncIOMotorDatabase, uid: str, job: dict, *, label: int | None = None, category: str | None = None,
                 source: str = "feedback", weight: float = 1.0) -> dict:
    """Store a training example (a snapshot, so it survives the posting closing)."""
    sid = f"{uid}:{job['_id']}"
    s = {"user_id": uid, "job_id": job["_id"], "features": features(job, await context(db, uid)), "text": _text(job), "updated_at": utcnow()}
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
                                                                 {"job_id": 1, "source": 1, "label": 1, "weight": 1}).to_list(2000)}
    n = 0
    ctx = await context(db, uid)
    for d in saved:
        st = apps.get(d["saved_job_id"])
        prev = have.get(d["_id"])
        if prev and prev.get("source") == "feedback":
            continue  # the user's own rating wins
        if st in POSITIVE:
            label, weight, src = 1, 3.0 if st in STRONG_POSITIVE else 2.0, "outcome"
        elif st in NEGATIVE:
            label, weight, src = 0, 1.0, "outcome"
        else:
            label, weight, src = 1, 0.5, "saved"
        if prev and prev.get("source") == src and prev.get("label") == label and prev.get("weight") == weight:
            continue
        await db[c.ML_SAMPLES].update_one({"_id": f"{uid}:{d['_id']}"}, {"$set": {
            "user_id": uid, "job_id": d["_id"], "features": features(d, ctx), "text": _text(d), "label": label, "weight": weight,
            "source": src, "updated_at": utcnow()}, "$setOnInsert": {"created_at": utcnow()}}, upsert=True)
        n += 1
    return n


# ------------------------------------------------------------------ training

async def train(db: AsyncIOMotorDatabase, uid: str, *, trigger: str = "manual") -> dict:
    async with agent_run(db, "saige_learning", uid, {"trigger": trigger}) as run:
        harvested = await _harvest_outcomes(db, uid)
        samples = await db[c.ML_SAMPLES].find({"user_id": uid}).to_list(5000)
        real = [s for s in samples if s.get("label") is not None]
        auto = await _auto_labels(db, uid, {s["job_id"] for s in real}, len(real))
        rel = real + auto
        X, y, sw = [s["features"] for s in rel], [s["label"] for s in rel], [s.get("weight", 1.0) for s in rel]
        out: dict = {"trigger": trigger, "samples": len(real), "auto_labels": len(auto), "positives": sum(y), "negatives": len(y) - sum(y),
                     "harvested": harvested, "trained_at": utcnow(), "sources": _sources(real)}
        prev = await db[c.ML_MODELS].find_one({"_id": f"{uid}:relevance"}) or {}
        if len(rel) >= MIN_SAMPLES and 0 < sum(y) < len(y):
            # judge the model only on your own signals once there are enough; until then it is bootstrapped from match scores
            ry = [s["label"] for s in real]
            if len(real) >= MIN_SAMPLES and 0 < sum(ry) < len(ry):
                metrics = {**evaluate([s["features"] for s in real], ry, [s.get("weight", 1.0) for s in real]), "bootstrapped": False}
            else:
                metrics = {**evaluate(X, y, sw), "bootstrapped": True}
            model = LogisticModel().fit(X, y, sw)
            model.cal = tuple(metrics.get("calibration") or (1.0, 0.0))
            promote = "weights" not in prev or beats(metrics, prev.get("metrics"))
            entry = {"version": (prev.get("version") or 0) + 1, "trained_at": out["trained_at"], "trigger": trigger, "samples": len(real),
                     "metrics": metrics, "score": metric_score(metrics), "promoted": promote}
            history = [*(prev.get("history") or []), entry][-HISTORY_KEEP:]
            if promote:
                version = entry["version"]
                pos, neg = model.top()
                await db[c.ML_MODELS].replace_one({"_id": f"{uid}:relevance"}, {
                    "_id": f"{uid}:relevance", "user_id": uid, "kind": "relevance", "weights": model.w, "version": version, "metrics": metrics,
                    "calibration": list(model.cal), "history": history,
                    "samples": len(real), "auto_labels": len(auto), "sources": out["sources"], "positives": sum(y),
                    "trained_at": out["trained_at"], "labels_since": 0,
                    "top_positive": [[label_name(k), v] for k, v in pos], "top_negative": [[label_name(k), v] for k, v in neg]}, upsert=True)
                out.update(status="trained", version=version, metrics=metrics, previous=prev.get("metrics"), promoted=True)
                out["scored"] = await score_all(db, uid)
            else:  # the candidate did not beat the current model on k-fold: keep serving the current one
                await db[c.ML_MODELS].update_one({"_id": f"{uid}:relevance"}, {"$set": {"history": history, "labels_since": 0}})
                out.update(status="kept_current", version=prev.get("version"), metrics=prev.get("metrics"), candidate_metrics=metrics,
                           promoted=False, message="A new model trained but didn't beat the current one in cross-validation; kept the current one.")
        else:
            need = max(0, MIN_SAMPLES - len(rel))
            out.update(status="needs_data", message=(f"Rate {need} more job(s)" if need else "Rate at least one job you like and one you don't")
                       + " so Saige can learn what you want.")
            await db[c.ML_MODELS].update_one({"_id": f"{uid}:relevance"}, {"$set": {"user_id": uid, "labels_since": 0}}, upsert=True)
        out["job_type"] = await _train_types(db, uid, samples)
        run.output = {k: out.get(k) for k in ("status", "samples", "version", "promoted")}
        run.action(f"trained on {len(rel)} labelled job(s)")
    await db[c.ML_RUNS].insert_one({"_id": new_id(), "user_id": uid, **{k: v for k, v in out.items() if k != "previous"}})
    await log_action(db, user_id=uid, action="ml.trained", entity="ml_model",
                     details={"status": out["status"], "samples": out["samples"], "metrics": out.get("metrics"), "trigger": trigger})
    return out


AGENT_EVERY = timedelta(hours=2)


async def maybe_retrain(db: AsyncIOMotorDatabase, uid: str) -> dict | None:
    """Learning agent: retrain when there is new data and the last run is a few hours old (called from live watch)."""
    m = await db[c.ML_MODELS].find_one({"_id": f"{uid}:relevance"}, {"trained_at": 1, "labels_since": 1}) or {}
    last = m.get("trained_at")
    new_jobs = await db[c.CAREER_JOBS].count_documents({"user_id": uid, "active": True, "ai_version": None})
    if last and utcnow() - as_utc(last) < AGENT_EVERY:
        return None
    if last and not m.get("labels_since") and not new_jobs:
        return None
    return await train(db, uid, trigger="agent")


AUTO_MAX = 400
AUTO_WEIGHT = 0.15


async def _auto_labels(db: AsyncIOMotorDatabase, uid: str, labelled: set[str], n_real: int) -> list[dict]:
    """Starter data so the model works from day one: very strong matches count as weak likes and very poor ones as
    weak skips. Their weight is small and shrinks as your own signals grow, so your behaviour takes over."""
    weight = round(AUTO_WEIGHT * max(0.2, 1 - n_real / 60), 3)
    out = []
    ctx = await context(db, uid)
    q = {"user_id": uid, "active": True, "$or": [{"score": {"$gte": 85}}, {"score": {"$lte": 40}}]}
    async for d in db[c.CAREER_JOBS].find(q, {"description": 0}).sort("first_seen", DESCENDING).limit(AUTO_MAX):
        if d["_id"] in labelled:
            continue
        out.append({"job_id": d["_id"], "features": features(d, ctx), "label": int(d["score"] >= 85), "weight": weight, "source": "auto"})
    return out


def _sources(real: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for s in real:
        k = s.get("source") or "feedback"
        counts[k] = counts.get(k, 0) + 1
    return counts


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
    m = await db[c.ML_MODELS].find_one({"_id": f"{uid}:relevance", "weights": {"$exists": True}}, {"weights": 1, "version": 1, "calibration": 1})
    if not m:
        return 0
    model = LogisticModel(m["weights"], m.get("calibration"))
    ctx = await context(db, uid)
    q: dict = {"user_id": uid, "active": True}
    if only_missing:
        q["$or"] = [{"ai_version": None}, {"ai_version": {"$ne": m["version"]}}]
    ops = []
    async for d in db[c.CAREER_JOBS].find(q, {"description": 0}):
        ops.append(UpdateOne({"_id": d["_id"]}, {"$set": {"ai_score": round(100 * model.predict(features(d, ctx))), "ai_version": m["version"]}}))
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
                      "labels_since": rel.get("labels_since", 0), "retrain_every": RETRAIN_EVERY, "min_samples": MIN_SAMPLES,
                      "auto_labels": rel.get("auto_labels", 0), "sources": rel.get("sources", {}),
                      "features": len(rel.get("weights") or {}), "calibration": rel.get("calibration"),
                      "history": [{**h, "trained_at": h["trained_at"].isoformat() if h.get("trained_at") else None}
                                  for h in reversed(rel.get("history") or [])],
                      "promotion_rule": "A new model replaces the current one only if its cross-validated score is at least as good."},
        "job_type": {"trained": "state" in typ, "samples": typ.get("samples", 0), "min_samples": MIN_TYPE_SAMPLES},
        "labels": counts,
        "history": [{"trained_at": r["trained_at"].isoformat(), "status": r["status"], "samples": r["samples"], "trigger": r.get("trigger"),
                     "version": r.get("version"), "promoted": r.get("promoted"), "accuracy": (r.get("metrics") or {}).get("accuracy"),
                     "auc": (r.get("metrics") or {}).get("auc")}
                    for r in runs],
    }

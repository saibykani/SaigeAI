"""Career jobs: scan company career portals, store every matching opening, filter it, and explain the fit.

Storage: one `career_jobs` document per (user, posting), keyed `{user_id}:{item_id}`. A scan upserts what it
finds (`first_seen` is kept, `last_seen` moves), and a posting that disappears from a company that answered
is marked `active: false` (closed). Companies that fail are reported in the scan, and their postings are left
alone. Lists are filtered and paginated in MongoDB, so thousands of postings per user stay fast.

Fit and resume advice never invent anything: "add to your resume" only lists skills that are already in the
verified master profile, and skills the role needs that the profile lacks are reported as gaps to close, never
as text to paste.
"""

import asyncio
import logging
import re
from datetime import timedelta

from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, UpdateOne

from app.automation.service import AutomationSettings, get_settings_doc, is_blocked
from app.careers import catalog, classify, providers
from app.careers.catalog import Company
from app.database import collections as c
from app.jobs import discover, feed
from app.jobs.jd_parser import analyze_jd
from app.jobs.matching import _skill_key, candidate_skills, compute_match
from app.jobs.service import get_weights, infer_country
from app.profiles.service import get_profile
from app.schemas.profile import Profile
from app.services.agent_runs import agent_run
from app.services.audit import log_action
from app.services.notify import notify
from app.utils import as_utc, utcnow

logger = logging.getLogger("saige.careers")

CONCURRENCY = 40
COMPANY_TIMEOUT = 25.0
SCAN_BUDGET = 40.0
MAX_PER_COMPANY = 150
DESC_KEEP = 12000
SORTS = {"score": [("score", DESCENDING), ("first_seen", DESCENDING)],
         "recent": [("posted", DESCENDING), ("first_seen", DESCENDING)],
         "new": [("first_seen", DESCENDING), ("score", DESCENDING)],
         "company": [("company", ASCENDING), ("score", DESCENDING)]}
FITS = ("strong", "good", "stretch", "low")
FIT_LABEL = {"strong": "Strong fit: apply", "good": "Good fit: tailor your resume first",
             "stretch": "Stretch: close the gaps first", "low": "Not a fit right now"}
LIST_FIELDS = {"description": 0}


def fit_for(score: int) -> str:
    return "strong" if score >= 80 else "good" if score >= 65 else "stretch" if score >= 50 else "low"


MANUAL_ROLES = ("Manual Tester", "QA Analyst")


def roles_for(profile: Profile, s: AutomationSettings) -> list[str]:
    roles = [r.strip() for r in s.careers.roles if r.strip()][:5] or feed.roles_for(profile)
    # Manual testing track: QA searches also look for manual tester / QA analyst openings.
    if s.careers.manual_testing and any(discover.title_matches("QA Test Engineer", r) for r in roles):
        roles += [m for m in MANUAL_ROLES if m.lower() not in {r.lower() for r in roles}]
    return roles


def city_of(location: str | None) -> str | None:
    first = re.split(r"[,;/|·]| - ", location or "")[0].strip()
    return first[:60] or None


def _custom_boards(sources: list[dict]) -> list[Company]:
    """Boards the user follows in Jobs → Career pages also count as career portals."""
    out = []
    for s in sources:
        if s.get("provider") in ("greenhouse", "lever", "ashby") and s.get("board"):
            name = s.get("company_name") or s["board"].title()
            out.append(Company(f"{s['provider']}:{s['board']}", name, s["provider"], s["board"], ("followed",)))
    return out


async def companies_for(db: AsyncIOMotorDatabase, uid: str, s: AutomationSettings, only: list[str] | None = None) -> list[Company]:
    sources = await db[c.JOB_SOURCES].find({"user_id": uid}, {"provider": 1, "board": 1, "company_name": 1}).to_list(200)
    pool = catalog.select(s.careers.tiers, s.careers.companies, api_only=True)
    known = {(co.provider, co.board) for co in pool}
    pool += [co for co in _custom_boards(sources) if (co.provider, co.board) not in known]
    if only:
        ids, have = set(only), {co.id for co in pool}
        extra = [catalog.BY_ID[i] for i in ids - have if i in catalog.BY_ID and catalog.BY_ID[i].is_api]
        pool = [co for co in pool if co.id in ids] + extra
    return pool


def _doc(uid: str, it: dict, co: Company, country: str | None) -> dict:
    loc = it.get("location")
    return {
        "user_id": uid, "item_id": it["id"], "company_id": co.id, "company": co.name, "tiers": list(co.tiers),
        "provider": co.provider, "source": it.get("source"), "source_job_id": it.get("source_job_id"),
        "title": it["title"][:200], "location": loc, "city": city_of(loc), "country": infer_country(loc),
        "remote": it.get("remote"), "scope": it.get("scope"), "url": it.get("url"), "careers_url": co.careers_url,
        "posted": it.get("posted") or None, "employment_type": it.get("employment_type"), "team": it.get("team"),
        "score": it["score"], "fit": fit_for(it["score"]), "classification": it.get("classification"),
        "matched_skills": it.get("matched_skills", []), "missing_skills": it.get("missing_skills", []),
        "exp_min": it.get("exp_min"), "exp_max": it.get("exp_max"), "seniority": it.get("seniority"),
        "walk_in": it.get("walk_in"), "hr_emails": it.get("hr_emails", []), "snippet": it.get("snippet", ""),
        "description": (it.get("description") or "")[:DESC_KEEP], "has_description": len(it.get("description") or "") > 200,
        "home_country": country,
        "category": classify.category(it["title"], it.get("description") or ""),
        "salary_min": None, "salary_max": None, "salary_currency": None, "salary_lpa": None, "salary_text": None,
        **classify.compensation(it.get("description") or "", it.get("comp_summary")),
    }


async def _bulk_upsert(db: AsyncIOMotorDatabase, ops: list[UpdateOne]) -> None:
    """One round trip per 500 postings on MongoDB; per-document writes where bulk ops aren't supported (mongomock)."""
    coll = db[c.CAREER_JOBS]
    for i in range(0, len(ops), 500):
        chunk = ops[i:i + 500]
        try:
            await coll.bulk_write(chunk, ordered=False)
        except TypeError:
            for op in chunk:
                await coll.update_one(op._filter, op._doc, upsert=True)


async def scan(db: AsyncIOMotorDatabase, uid: str, *, trigger: str = "manual", only: list[str] | None = None,
               budget: float | None = None) -> dict:
    """Fetch every selected career portal, score each matching opening and store it."""
    profile = await get_profile(db, uid)
    weights = await get_weights(db, uid)
    s = await get_settings_doc(db, uid)
    roles, country = roles_for(profile, s), feed.country_for(profile)
    started = utcnow()
    report: dict = {"_id": uid, "user_id": uid, "roles": roles, "country": country, "trigger": trigger, "started_at": started,
                    "status": "running", "companies": [], "found": 0, "new": 0, "closed": 0, "strong_new": 0}
    if not roles:
        report.update(status="needs_profile", error="Add a target role in your profile (or in Career jobs settings) so Saige knows what to look for.",
                      finished_at=utcnow())
        await db[c.CAREER_SCANS].replace_one({"_id": uid}, report, upsert=True)
        return report
    pool = await companies_for(db, uid, s, only)
    watch = trigger == "watch"
    if not watch:
        await db[c.CAREER_SCANS].replace_one({"_id": uid}, report, upsert=True)

    async with agent_run(db, "career_portal_scan", uid, {"roles": roles, "companies": len(pool), "trigger": trigger}) as run:
        sem = asyncio.Semaphore(CONCURRENCY)
        async with providers.http_client() as client:
            async def one(co: Company):
                async with sem:
                    return await asyncio.wait_for(providers.fetch(client, co, roles, country), COMPANY_TIMEOUT)

            # Hard budget so a scan always finishes inside one serverless call; late companies count as timed out.
            tasks = [asyncio.ensure_future(one(co)) for co in pool]
            if tasks:
                await asyncio.wait(tasks, timeout=budget or SCAN_BUDGET)
            results = []
            for t in tasks:
                if not t.done():
                    t.cancel()
                    results.append(TimeoutError())
                else:
                    results.append(t.exception() or t.result())

        ops, ok_ids, strong_new = [], [], []
        existing = {d["_id"] for d in await db[c.CAREER_JOBS].find({"user_id": uid}, {"_id": 1}).to_list(None)}
        for co, res in zip(pool, results, strict=True):
            if isinstance(res, BaseException):
                msg = "timed out" if isinstance(res, TimeoutError) else "unavailable right now"
                report["companies"].append({"id": co.id, "name": co.name, "status": "error", "error": msg, "found": 0})
                run.errors.append(f"{co.id}: {type(res).__name__}")
                continue
            ok_ids.append(co.id)
            kept = 0
            for it in res[:MAX_PER_COMPANY]:
                if not it.get("title") or is_blocked(s, it.get("company")):
                    continue
                scored = discover.score(it, profile, weights)
                if not scored:
                    continue
                feed.annotate(scored, country)
                doc = _doc(uid, scored, co, country)
                key = f"{uid}:{doc['item_id']}"
                is_new = key not in existing
                existing.add(key)
                kept += 1
                if is_new and doc["fit"] == "strong" and doc["scope"] != "abroad":
                    strong_new.append(doc)
                report["new"] += is_new
                ops.append(UpdateOne({"_id": key}, {"$set": {**doc, "active": True, "last_seen": started, "closed_at": None},
                                                    "$setOnInsert": {"first_seen": started, "emailed_at": None, "saved_job_id": None}},
                                     upsert=True))
            report["companies"].append({"id": co.id, "name": co.name, "status": "ok", "found": kept})
            report["found"] += kept
        if ops:
            await _bulk_upsert(db, ops)
        if ok_ids:
            closed = await db[c.CAREER_JOBS].update_many(
                {"user_id": uid, "company_id": {"$in": ok_ids}, "active": True, "last_seen": {"$lt": started}},
                {"$set": {"active": False, "closed_at": started}})
            report["closed"] = closed.modified_count
        report["strong_new"] = len(strong_new)
        report.update(status="partial" if run.errors and ok_ids else "failed" if run.errors else "ok", finished_at=utcnow(),
                      errors=len(run.errors), duration_ms=round((utcnow() - started).total_seconds() * 1000))
        run.output = {k: report[k] for k in ("found", "new", "closed", "strong_new", "errors")}
        run.action(f"scanned {len(pool)} career portals for {', '.join(roles)}")

    if watch:
        await db[c.CAREER_SCANS].update_one({"_id": uid}, {"$set": {"watch": {k: report[k] for k in (
            "found", "new", "closed", "errors", "finished_at", "duration_ms")} | {"companies": len(pool)}}}, upsert=True)
    else:
        prev = await db[c.CAREER_SCANS].find_one({"_id": uid}, {"watch": 1}) or {}
        await db[c.CAREER_SCANS].replace_one({"_id": uid}, report | ({"watch": prev["watch"]} if prev.get("watch") else {}), upsert=True)
    await log_action(db, user_id=uid, action="careers.scanned", entity="career_jobs",
                     details={k: report[k] for k in ("found", "new", "closed", "strong_new", "errors", "trigger")})
    if strong_new:
        strong_new.sort(key=lambda d: -d["score"])
        await notify(db, user_id=uid, kind="career_jobs", title=f"{len(strong_new)} new strong match(es) on company career pages",
                     body=f"For {', '.join(roles)}", link="/careers",
                     details=[{"platform": d["company"], "field": d["title"], "after": f"{d['score']}%"} for d in strong_new[:5]])
    return report


# ------------------------------------------------------------------ query

def _filter(uid: str, f: dict) -> dict:
    q: dict = {"user_id": uid}
    if not f.get("include_closed"):
        q["active"] = True
    if f.get("q"):
        rx = {"$regex": re.escape(f["q"].strip()[:80]), "$options": "i"}
        q["$or"] = [{"title": rx}, {"company": rx}, {"location": rx}, {"matched_skills": rx}]
    if f.get("companies"):
        q["company_id"] = {"$in": f["companies"]}
    if f.get("tiers"):
        q["tiers"] = {"$in": f["tiers"]}
    if f.get("countries"):
        q["country"] = {"$in": f["countries"]}
    if f.get("location"):
        q["location"] = {"$regex": re.escape(f["location"].strip()[:60]), "$options": "i"}
    if f.get("scopes"):
        q["scope"] = {"$in": f["scopes"]}
    if f.get("fits"):
        q["fit"] = {"$in": f["fits"]}
    if f.get("min_score"):
        q["score"] = {"$gte": int(f["min_score"])}
    if f.get("remote"):
        q["$and"] = [{"$or": [{"remote": True}, {"scope": "remote"}]}]
    if f.get("posted_days"):
        q["posted"] = {"$gte": (utcnow() - timedelta(days=int(f["posted_days"]))).date().isoformat()}
    if f.get("new_days"):
        q["first_seen"] = {"$gte": utcnow() - timedelta(days=int(f["new_days"]))}
    if f.get("categories"):
        q["category"] = {"$in": f["categories"]}
    if f.get("posted_hours"):
        since = utcnow() - timedelta(hours=int(f["posted_hours"]))
        q.setdefault("$and", []).append({"$or": [{"posted": {"$gte": since.date().isoformat()}},
                                                 {"posted": None, "first_seen": {"$gte": since}}]})
    if f.get("min_lpa"):
        q["salary_lpa"] = {"$ne": None, "$gte": float(f["min_lpa"])}
    elif f.get("salary_listed"):
        q["salary_lpa"] = {"$ne": None}
    if f.get("min_exp") is not None:
        q["exp_min"] = {"$ne": None, "$gte": float(f["min_exp"])}
    if f.get("employment_types"):
        q["employment_type"] = {"$in": f["employment_types"]}
    if f.get("max_exp") is not None:
        q.setdefault("$and", []).append({"$or": [{"exp_min": None}, {"exp_min": {"$lte": float(f["max_exp"])}}]})
    return q


async def _facet(db: AsyncIOMotorDatabase, base: dict, field: str, label: str | None = None) -> list[dict]:
    group = {"_id": f"${field}", "count": {"$sum": 1}}
    if label:
        group["label"] = {"$first": f"${label}"}
    rows = await db[c.CAREER_JOBS].aggregate([{"$match": base}, {"$group": group}, {"$sort": {"count": -1}}, {"$limit": 100}]).to_list(None)
    return [{"value": r["_id"], "label": r.get("label") or r["_id"], "count": r["count"]} for r in rows if r["_id"]]


async def backfill(db: AsyncIOMotorDatabase, uid: str, limit: int = 2000) -> int:
    """Postings stored before job types and pay existed get them from their saved title and description."""
    docs = await db[c.CAREER_JOBS].find({"user_id": uid, "category": None}, {"title": 1, "description": 1}).to_list(limit)
    ops = [UpdateOne({"_id": d["_id"]}, {"$set": {
        "category": classify.category(d.get("title") or "", d.get("description") or ""),
        "salary_min": None, "salary_max": None, "salary_currency": None, "salary_lpa": None, "salary_text": None,
        **classify.compensation(d.get("description") or "")}}) for d in docs]
    if ops:
        await _bulk_upsert(db, ops)
    return len(ops)


async def query(db: AsyncIOMotorDatabase, uid: str, f: dict) -> dict:
    await backfill(db, uid)
    page, size = max(1, int(f.get("page") or 1)), min(100, max(5, int(f.get("page_size") or 25)))
    q = _filter(uid, f)
    sort = SORTS.get(f.get("sort") or "score", SORTS["score"])
    total = await db[c.CAREER_JOBS].count_documents(q)
    # Postings from the last 24 hours always come first, then the chosen order.
    day = utcnow() - timedelta(hours=24)
    fresh = _fresh_q(day)
    if f.get("fresh_first", True) and (f.get("sort") or "score") != "company":
        n_fresh = await db[c.CAREER_JOBS].count_documents({"$and": [q, fresh]})
        skip, items = (page - 1) * size, []
        if skip < n_fresh:
            items = await db[c.CAREER_JOBS].find({"$and": [q, fresh]}, LIST_FIELDS).sort(sort).skip(skip).limit(size).to_list(size)
        if len(items) < size:
            items += await db[c.CAREER_JOBS].find({"$and": [q, {"$nor": [fresh]}]}, LIST_FIELDS).sort(sort).skip(
                max(0, skip - n_fresh)).limit(size - len(items)).to_list(size)
    else:
        items = await db[c.CAREER_JOBS].find(q, LIST_FIELDS).sort(sort).skip((page - 1) * size).limit(size).to_list(size)
    for d in items:
        d["fresh"] = _is_fresh(d, day)
    base = {"user_id": uid, "active": True}
    companies, countries, fits, scopes, categories, types = await asyncio.gather(
        _facet(db, base, "company_id", "company"), _facet(db, base, "country"), _facet(db, base, "fit"), _facet(db, base, "scope"),
        _facet(db, base, "category"), _facet(db, base, "employment_type"))
    for row in categories:
        row["label"] = classify.CATEGORIES.get(row["value"], row["value"])
    fresh_count = await db[c.CAREER_JOBS].count_documents({"$and": [base, fresh]})
    salary_count = await db[c.CAREER_JOBS].count_documents({**base, "salary_lpa": {"$ne": None}})
    scan_doc = await db[c.CAREER_SCANS].find_one({"_id": uid}, {"companies": 0})
    return {"items": [public(d) for d in items], "total": total, "page": page, "page_size": size,
            "facets": {"companies": companies, "countries": countries, "fits": fits, "scopes": scopes, "categories": categories,
                       "employment_types": types},
            "counts": {"last_24h": fresh_count, "salary_listed": salary_count},
            "scan": scan_out(scan_doc)}


def _fresh_q(day) -> dict:
    return {"$or": [{"posted": {"$gte": day.date().isoformat()}}, {"posted": None, "first_seen": {"$gte": day}}]}


def _is_fresh(d: dict, day) -> bool:
    if d.get("posted"):
        return d["posted"] >= day.date().isoformat()
    return bool(d.get("first_seen")) and as_utc(d["first_seen"]) >= day


def public(d: dict) -> dict:
    out = {k: v for k, v in d.items() if k not in ("description", "user_id", "home_country")}
    out["id"] = out.pop("_id")
    for k in ("first_seen", "last_seen", "closed_at", "emailed_at"):
        if out.get(k):
            out[k] = out[k].isoformat()
    out["fit_label"] = FIT_LABEL.get(d.get("fit", ""), "")
    return out


def scan_out(doc: dict | None) -> dict | None:
    if not doc:
        return None
    out = {k: v for k, v in doc.items() if k not in ("_id", "user_id")}
    # A serverless call killed mid-scan leaves "running" behind; after 2 minutes call it what it is.
    if out.get("status") == "running" and out.get("started_at") and utcnow() - as_utc(out["started_at"]) > timedelta(minutes=2):
        out.update(status="interrupted", error="The last scan was cut off before it finished. Scan again.")
    for k in ("started_at", "finished_at"):
        if out.get(k):
            out[k] = out[k].isoformat()
    if isinstance(out.get("watch"), dict) and out["watch"].get("finished_at"):
        out["watch"] = {**out["watch"], "finished_at": as_utc(out["watch"]["finished_at"]).isoformat()}
    return out


async def get_owned(db: AsyncIOMotorDatabase, uid: str, job_id: str) -> dict:
    d = await db[c.CAREER_JOBS].find_one({"_id": job_id, "user_id": uid})
    if not d:
        raise HTTPException(404, "Career job not found")
    return d


# ------------------------------------------------------------------ fit + resume advice

async def _best_resume(db: AsyncIOMotorDatabase, uid: str, wanted: set[str]) -> dict | None:
    best = None
    for r in await db[c.RESUMES].find({"user_id": uid, "status": "active"}).to_list(50):
        v = await db[c.RESUME_VERSIONS].find_one({"_id": r.get("current_version_id")})
        if not v:
            continue
        parsed = v.get("parsed") or {}
        keys = {_skill_key(x) for x in [*parsed.get("skills", []), *parsed.get("tools", [])]}
        overlap = len(keys & wanted)
        if best is None or overlap > best["overlap"]:
            best = {"id": r["_id"], "name": r.get("name"), "overlap": overlap, "keys": keys, "text": str(parsed).lower()}
    return best


def advice(profile: Profile, job: dict, jd, match, resume: dict | None) -> list[dict]:
    """Ordered, truthful resume changes for this posting."""
    have = candidate_skills(profile)
    changes: list[dict] = []
    wanted = list(dict.fromkeys([*jd.required_skills, *jd.preferred_skills]))
    add = []
    for sk in wanted:
        k = _skill_key(sk)
        if k in have and resume is not None and k not in resume["keys"] and sk.lower() not in resume["text"]:
            add.append(sk)
    if add:
        changes.append({"kind": "add", "title": "Add these verified skills to your resume",
                        "text": f"They're in your verified profile but not on '{resume['name']}': {', '.join(add[:10])}. "
                                "Put them in Skills and in the bullet where you used them.", "items": add[:10]})
    if match.missing_required_skills:
        changes.append({"kind": "gap", "title": "Required skills you don't have on record",
                        "text": "Don't add these unless you've really used them. If you have, add them to your profile first "
                                "(with where you used them); otherwise learn them or point to the closest experience you have.",
                        "items": match.missing_required_skills[:10]})
    if match.missing_preferred_skills:
        changes.append({"kind": "nice", "title": "Nice-to-have skills", "text": "Optional; they lift the match if you have them.",
                        "items": match.missing_preferred_skills[:8]})
    if match.experience_gap:
        changes.append({"kind": "experience", "title": "Experience", "text": match.experience_gap.capitalize()
                        + ". Lead with your most relevant projects and quantify impact you can verify."})
    if match.breakdown.role is not None and match.breakdown.role < 60:
        changes.append({"kind": "title", "title": "Headline and summary",
                        "text": f"Your target role differs from '{job['title']}'. Open the summary with the work you've done "
                                "that maps to this role, using your real titles."})
    for issue in match.issues:
        if issue.lower().startswith(("location", "salary", "notice", "on-site", "role does not sponsor")):
            changes.append({"kind": "info", "title": "Check before applying", "text": issue})
    if resume is None:
        changes.append({"kind": "info", "title": "No resume uploaded",
                        "text": "Upload a resume in Resumes so Saige can check it against each posting."})
    elif not changes or (len(changes) == 1 and changes[0]["kind"] == "nice"):
        changes.insert(0, {"kind": "ok", "title": "Your resume already covers this role",
                           "text": "Save the job and generate a tailored version to reorder bullets for this posting."})
    return changes


async def detail(db: AsyncIOMotorDatabase, uid: str, job_id: str) -> dict:
    d = await get_owned(db, uid, job_id)
    profile, weights = await get_profile(db, uid), await get_weights(db, uid)
    jd = analyze_jd(d["title"], d.get("description") or d["title"])
    match = compute_match(profile, {"title": d["title"], "company": d["company"], "location": d.get("location"),
                                    "remote": d.get("remote"), "skills": jd.skills}, jd, weights)
    resume = await _best_resume(db, uid, {_skill_key(x) for x in jd.skills})
    return {**public(d), "description": d.get("description") or "", "score": match.overall, "fit": fit_for(match.overall),
            "fit_label": FIT_LABEL[fit_for(match.overall)], "breakdown": match.breakdown.model_dump(),
            "matched_skills": match.matched_skills, "missing_skills": match.missing_required_skills, "issues": match.issues,
            "required_skills": jd.required_skills, "preferred_skills": jd.preferred_skills,
            "resume": {"id": resume["id"], "name": resume["name"], "overlap": resume["overlap"], "of": len(jd.skills)} if resume else None,
            "resume_changes": advice(profile, d, jd, match, resume)}


async def save(db: AsyncIOMotorDatabase, uid: str, job_id: str) -> dict:
    """Track the posting in Jobs (tailoring, applications, interviews all work from there)."""
    from app.jobs.service import ingest

    d = await get_owned(db, uid, job_id)
    if d.get("saved_job_id") and await db[c.JOBS].find_one({"_id": d["saved_job_id"], "user_id": uid}, {"_id": 1}):
        return {"job_id": d["saved_job_id"], "duplicate": True}
    item = {**d, "description": d.get("description") or ""}
    try:
        job, is_new = await ingest(db, uid, discover.to_job_in(item))
    except ValueError as exc:
        raise HTTPException(422, "This posting is missing details needed to track it.") from exc
    await db[c.CAREER_JOBS].update_one({"_id": job_id}, {"$set": {"saved_job_id": job["_id"]}})
    await log_action(db, user_id=uid, action="careers.saved", entity="job", entity_id=job["_id"],
                     details={"company": d["company"], "title": d["title"]})
    return {"job_id": job["_id"], "duplicate": not is_new}


async def portals(db: AsyncIOMotorDatabase, uid: str) -> dict:
    """Catalogue with selection state, plus deep links for the companies that have no public API."""
    profile, s = await get_profile(db, uid), await get_settings_doc(db, uid)
    roles = roles_for(profile, s)
    loc = profile.personal.current_location or feed.country_for(profile) or ""
    selected = {co.id for co in await companies_for(db, uid, s)}
    counts = {r["_id"]: r["n"] for r in await db[c.CAREER_JOBS].aggregate(
        [{"$match": {"user_id": uid, "active": True}}, {"$group": {"_id": "$company_id", "n": {"$sum": 1}}}]).to_list(None)}
    rows = []
    for co in catalog.COMPANIES:
        row = catalog.public(co, roles[0] if roles else "", loc)
        row.update(selected=co.id in selected, open_jobs=counts.get(co.id, 0),
                   role_links=[{"role": r, "url": catalog.portal_link(co, r, loc)} for r in roles] if not co.is_api else [])
        rows.append(row)
    return {"tiers": catalog.TIERS, "companies": rows, "roles": roles, "location": loc, "settings": s.careers.model_dump()}

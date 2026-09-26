"""Profile synchronisation: platform snapshots, change control and consistency (spec 27-32, 49-51)."""

import re
from typing import Any

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from app.database import collections as c
from app.profiles import optimizer as opt
from app.profiles.service import get_profile
from app.schemas.platform import LinkedInProfile, NaukriProfile
from app.schemas.profile import Profile
from app.schemas.resume import ParsedResume
from app.services.audit import log_action
from app.services.skills_vocab import canonical, normalize_key
from app.services.truth_guard import GeneratedClaims, validate_claims
from app.utils import new_id, utcnow

PENDING = "USER_APPROVAL_REQUIRED"
COLLECTION = {"linkedin": c.LINKEDIN_PROFILES, "naukri": c.NAUKRI_PROFILES}
MODEL = {"linkedin": LinkedInProfile, "naukri": NaukriProfile}
ACTION = {"linkedin": "COPY_TO_LINKEDIN", "naukri": "COPY_TO_NAUKRI", "resume": "UPDATE_MASTER_RESUME"}
TEXT_FIELDS = {"headline", "about", "summary"}
SKILL_FIELDS = {"skills", "key_skills"}


# ------------------------------------------------------------------ snapshots

async def get_snapshot(db: AsyncIOMotorDatabase, user_id: str, platform: str):
    doc = await db[COLLECTION[platform]].find_one({"user_id": user_id})
    model = MODEL[platform]
    if not doc:
        return model()
    return model.model_validate({k: v for k, v in doc.items() if k in model.model_fields})


async def save_snapshot(db: AsyncIOMotorDatabase, user_id: str, platform: str, data) -> Any:
    now = utcnow()
    await db[COLLECTION[platform]].update_one(
        {"user_id": user_id},
        {"$set": {**data.model_dump(mode="json"), "updated_at": now},
         "$setOnInsert": {"_id": new_id(), "user_id": user_id, "created_at": now}},
        upsert=True,
    )
    await log_action(db, user_id=user_id, action=f"{platform}_profile.saved", entity=f"{platform}_profile")
    return await get_snapshot(db, user_id, platform)


# ------------------------------------------------------------------ change control

PLATFORM_NAME = {"linkedin": "LinkedIn", "naukri": "Naukri", "resume": "Master resume"}
FIELD_NAME = {
    "headline": "Headline", "about": "About", "summary": "Profile summary", "skills": "Skills",
    "key_skills": "Key skills", "open_to_work.titles": "Open-to-work titles", "current_title": "Current title",
    "preferred_locations": "Preferred locations", "preferred_roles": "Preferred roles",
    "notice_period_days": "Notice period (days)", "expected_salary": "Expected salary",
    "total_experience_years": "Total experience", "resume_updated_on": "Resume refresh date",
}


def _short(v: Any, limit: int = 140) -> str:
    text = ", ".join(map(str, v)) if isinstance(v, list) else ("" if v is None else str(v))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def change_detail(d: dict) -> dict:
    """A notification row: which field on which platform, and its value before and after."""
    return {"platform": PLATFORM_NAME.get(d["platform"], d["platform"]),
            "field": FIELD_NAME.get(d["field"], d["field"]),
            "before": _short(d.get("before")) or "(empty)", "after": _short(d.get("after"))}

def validate_change(platform: str, field: str, after: Any, profile: Profile) -> dict:
    """Truth-guard every proposed value. Text is scanned for unverified skills, metrics and
    experience claims; skill lists must contain only verified skills."""
    if field in TEXT_FIELDS and isinstance(after, str):
        titles = [profile.personal.current_designation] if profile.personal.current_designation else []
        result = validate_claims(GeneratedClaims(text=after, titles=titles), profile)
    elif field in SKILL_FIELDS and isinstance(after, list):
        result = validate_claims(GeneratedClaims(skills=[str(s) for s in after]), profile)
    else:
        return {"status": "PASSED", "violations": []}
    return {"status": result.status, "violations": [v.model_dump() for v in result.violations]}


def change_out(d: dict) -> dict:
    return {
        "id": d["_id"], "platform": d["platform"], "field": d["field"], "before": d.get("before"),
        "after": d.get("after"), "reason": d.get("reason"), "source_jobs": d.get("source_jobs", []),
        "ai_confidence": d.get("ai_confidence"), "approval_status": d["approval_status"],
        "action": d.get("action"), "validation": d.get("validation"),
        "applied_at": d["applied_at"].isoformat() if d.get("applied_at") else None,
        "created_at": d["created_at"].isoformat(), "updated_at": d["updated_at"].isoformat(),
    }


async def upsert_changes(db: AsyncIOMotorDatabase, user_id: str, platform: str, proposals: list[dict],
                         profile: Profile, source_jobs: list[str]) -> int:
    created = 0
    for p in proposals:
        validation = validate_change(platform, p["field"], p["after"], profile)
        if validation["status"] != "PASSED":
            # Never surface a proposal that fails truth validation; keep an audit trail.
            await log_action(db, user_id=user_id, action="profile_change.blocked", entity="profile_change",
                             details={"platform": platform, "field": p["field"],
                                      "violations": validation["violations"]})
            continue
        # Respect a previous rejection of the exact same value.
        if await db[c.PROFILE_CHANGES].find_one({"user_id": user_id, "platform": platform, "field": p["field"],
                                                 "after": p["after"], "approval_status": "USER_REJECTED"}):
            continue
        now = utcnow()
        existing = await db[c.PROFILE_CHANGES].find_one(
            {"user_id": user_id, "platform": platform, "field": p["field"], "approval_status": PENDING})
        fields = {"before": p["before"], "after": p["after"], "reason": p["reason"],
                  "ai_confidence": p["confidence"], "source_jobs": source_jobs[:10],
                  "validation": validation, "updated_at": now}
        if existing:
            await db[c.PROFILE_CHANGES].update_one({"_id": existing["_id"]}, {"$set": fields})
        else:
            await db[c.PROFILE_CHANGES].insert_one({
                "_id": new_id(), "user_id": user_id, "platform": platform, "field": p["field"],
                "approval_status": PENDING, "action": ACTION[platform], "created_at": now,
                "applied_at": None, **fields,
            })
            created += 1
    return created


async def get_change(db: AsyncIOMotorDatabase, user_id: str, change_id: str) -> dict:
    doc = await db[c.PROFILE_CHANGES].find_one({"_id": change_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Change not found")
    return doc


async def decide(db: AsyncIOMotorDatabase, user_id: str, change_id: str, decision: str) -> dict:
    doc = await get_change(db, user_id, change_id)
    await db[c.PROFILE_CHANGES].update_one({"_id": change_id}, {"$set": {
        "approval_status": decision, "decided_at": utcnow(), "updated_at": utcnow()}})
    await log_action(db, user_id=user_id, action=f"profile_change.{decision.lower()}", entity="profile_change",
                     entity_id=change_id, details={"platform": doc["platform"], "field": doc["field"],
                                                   "before": doc.get("before"), "after": doc.get("after")})
    return change_out(await get_change(db, user_id, change_id))


async def edit_change(db: AsyncIOMotorDatabase, user_id: str, change_id: str, after: Any) -> dict:
    doc = await get_change(db, user_id, change_id)
    profile = await get_profile(db, user_id)
    validation = validate_change(doc["platform"], doc["field"], after, profile)
    if validation["status"] != "PASSED":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            {"status": "VALIDATION FAILED", "violations": validation["violations"]})
    await db[c.PROFILE_CHANGES].update_one({"_id": change_id}, {"$set": {
        "after": after, "validation": validation, "edited_by_user": True, "updated_at": utcnow()}})
    return change_out(await get_change(db, user_id, change_id))


def _set_path(data: dict, dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    for part in parts[:-1]:
        data = data.setdefault(part, {})
    data[parts[-1]] = value


async def master_resume(db: AsyncIOMotorDatabase, user_id: str) -> dict | None:
    q = {"user_id": user_id, "status": "active"}
    return (await db[c.RESUMES].find_one({**q, "kind": "Master Resume"}, sort=[("updated_at", DESCENDING)])
            or await db[c.RESUMES].find_one(q, sort=[("updated_at", DESCENDING)]))


async def mark_applied(db: AsyncIOMotorDatabase, user_id: str, change_id: str) -> dict:
    """The user copied the change to the platform (or approved a resume update): record it and
    update Saige's snapshot so later analyses see the new value."""
    from app.resumes import service as resumes  # local import avoids a cycle

    doc = await get_change(db, user_id, change_id)
    if doc["approval_status"] == "USER_REJECTED":
        raise HTTPException(status.HTTP_409_CONFLICT, "This change was rejected")
    platform = doc["platform"]
    if platform in COLLECTION:
        snap = (await get_snapshot(db, user_id, platform)).model_dump(mode="json")
        _set_path(snap, doc["field"], doc["after"])
        await save_snapshot(db, user_id, platform, MODEL[platform].model_validate(snap))
    else:  # master resume: write a new version, never overwrite in place
        resume = await master_resume(db, user_id)
        if not resume:
            raise HTTPException(status.HTTP_409_CONFLICT, "Upload a resume first")
        cur = await resumes.current_version(db, resume)
        parsed = ParsedResume.model_validate(cur["parsed"]) if cur else ParsedResume()
        updated = parsed.model_copy(update={doc["field"]: doc["after"]})
        await resumes.add_version(db, resume, parsed=updated, raw_text=cur.get("raw_text", "") if cur else "",
                                  source="optimization", changes=[doc["reason"]])
    await db[c.PROFILE_CHANGES].update_one({"_id": change_id}, {"$set": {
        "approval_status": "USER_APPROVED", "applied_at": utcnow(), "updated_at": utcnow()}})
    await log_action(db, user_id=user_id, action="profile_change.applied", entity="profile_change",
                     entity_id=change_id, details={"platform": platform, "field": doc["field"]})
    from app.services.notify import notify  # local import keeps module load light

    row = change_detail(doc)
    await notify(db, user_id=user_id, kind="profile_change_applied",
                 title=f"{row['platform']} updated · {row['field']}", body=f"Now: {row['after']}",
                 link="/profiles", details=[row])
    return change_out(await get_change(db, user_id, change_id))


# ------------------------------------------------------------------ analysis

async def analyze(db: AsyncIOMotorDatabase, user_id: str, platforms: tuple[str, ...] = ("linkedin", "naukri", "resume"),
                  ) -> dict:
    profile = await get_profile(db, user_id)
    trends, jobs = await opt.skill_trends(db, user_id, profile)
    source = [j["_id"] for j in jobs]
    today = utcnow().date()
    result: dict[str, Any] = {"jobs_analyzed": len(jobs), "trends": [t.model_dump() for t in trends]}

    if "linkedin" in platforms:
        li = await get_snapshot(db, user_id, "linkedin")
        snap = li.model_dump()
        comp, missing = opt.completeness(snap, opt.LINKEDIN_FIELDS)
        align, kw_missing = opt.keyword_alignment(f"{li.headline or ''} {li.about or ''}", li.skills, trends)
        created = await upsert_changes(db, user_id, "linkedin", opt.linkedin_suggestions(profile, li, trends),
                                       profile, source)
        result["linkedin"] = {"platform": "linkedin", "completeness": comp, "keyword_alignment": align,
                              "missing_fields": missing, "skills_to_add": kw_missing,
                              "skills_in_demand_you_lack": [t.skill for t in trends if not t.candidate_has][:10],
                              "changes_created": created}
    if "naukri" in platforms:
        nk = await get_snapshot(db, user_id, "naukri")
        snap = nk.model_dump()
        comp, missing = opt.completeness(snap, opt.NAUKRI_FIELDS)
        align, kw_missing = opt.keyword_alignment(f"{nk.headline or ''} {nk.summary or ''}", nk.key_skills, trends)
        created = await upsert_changes(db, user_id, "naukri", opt.naukri_suggestions(profile, nk, trends, today),
                                       profile, source)
        result["naukri"] = {"platform": "naukri", "completeness": comp, "keyword_alignment": align,
                            "missing_fields": missing, "skills_to_add": kw_missing,
                            "skills_in_demand_you_lack": [t.skill for t in trends if not t.candidate_has][:10],
                            "changes_created": created}
    if "resume" in platforms:
        resume = await master_resume(db, user_id)
        created = 0
        if resume:
            v = await db[c.RESUME_VERSIONS].find_one({"_id": resume.get("current_version_id")})
            skills = (v or {}).get("parsed", {}).get("skills", [])
            created = await upsert_changes(db, user_id, "resume", opt.resume_suggestions(profile, skills, trends),
                                           profile, source)
        result["resume"] = {"resume_id": resume["_id"] if resume else None, "changes_created": created}
    return result


# ------------------------------------------------------------------ consistency

def _norm(v: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(v).lower()).strip()


def _skill_coverage(master: list[str], other: list[str]) -> float | None:
    if not master or not other:
        return None
    o = {normalize_key(canonical(s)) for s in other}
    return sum(normalize_key(canonical(s)) in o for s in master) / len(master)


async def consistency(db: AsyncIOMotorDatabase, user_id: str) -> dict:
    profile = await get_profile(db, user_id)
    li = await get_snapshot(db, user_id, "linkedin")
    nk = await get_snapshot(db, user_id, "naukri")
    resume = await master_resume(db, user_id)
    parsed: dict = {}
    if resume:
        v = await db[c.RESUME_VERSIONS].find_one({"_id": resume.get("current_version_id")})
        parsed = (v or {}).get("parsed", {})
    p, kb = profile.personal, profile.knowledge
    r_exp = (parsed.get("experience") or [{}])[0] if parsed.get("experience") else {}

    checks: list[dict] = []

    def compare(field: str, master: Any, others: dict[str, Any]) -> None:
        present = {k: v for k, v in others.items() if v not in (None, "", [])}
        if master in (None, "", []) or not present:
            return
        mismatched = [k for k, v in present.items() if _norm(v) != _norm(master)]
        checks.append({"field": field, "master": master, "values": present, "consistent": not mismatched,
                       "mismatched": mismatched})

    compare("Name", p.name, {"resume": parsed.get("name")})
    compare("Designation", p.current_designation,
            {"linkedin": li.current_title, "naukri": nk.current_designation, "resume": r_exp.get("title")})
    compare("Current company", p.current_company,
            {"naukri": nk.current_company, "linkedin": li.experience[0].company if li.experience else None,
             "resume": r_exp.get("company")})
    compare("Total experience", p.total_experience_years, {"naukri": nk.total_experience_years})
    compare("Notice period (days)", p.notice_period_days, {"naukri": nk.notice_period_days})
    compare("Preferred locations", ", ".join(sorted(map(str.lower, profile.preferences.preferred_locations))),
            {"naukri": ", ".join(sorted(map(str.lower, nk.preferred_locations))) or None})

    master_skills = profile.skills.all()[:15]
    for name, other in (("linkedin", li.skills), ("naukri", nk.key_skills), ("resume", parsed.get("skills", []))):
        cov = _skill_coverage(master_skills, other)
        if cov is not None:
            checks.append({"field": f"Skills on {name}", "master": f"{len(master_skills)} top skills",
                           "values": {name: f"{round(cov * 100)}% present"}, "consistent": cov >= 0.7,
                           "mismatched": [] if cov >= 0.7 else [name]})

    degrees = [e.degree for e in kb.education]
    if degrees and li.education:
        joined = _norm(" ".join(li.education))
        missing = [d for d in degrees if _norm(d) not in joined]
        checks.append({"field": "Education", "master": ", ".join(degrees), "values": {"linkedin": ", ".join(li.education)},
                       "consistent": not missing, "mismatched": ["linkedin"] if missing else []})
    certs = [x.name for x in kb.certifications]
    if certs and li.certifications:
        joined = _norm(" ".join(li.certifications))
        missing = [x for x in certs if _norm(x) not in joined]
        checks.append({"field": "Certifications", "master": ", ".join(certs),
                       "values": {"linkedin": ", ".join(li.certifications)},
                       "consistent": not missing, "mismatched": ["linkedin"] if missing else []})

    score = round(100 * sum(ch["consistent"] for ch in checks) / len(checks)) if checks else None
    return {"score": score, "checks": checks,
            "discrepancies": [ch for ch in checks if not ch["consistent"]]}

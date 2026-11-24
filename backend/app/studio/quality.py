"""Resume quality tools for the Resume & ATS tab (/api/studio):

* bullet strength checker: weak verb, no outcome, too long, passive voice, with a rewrite built only from the bullet's own words.
  A missing metric is never invented: the checker asks the user for the real number.
* recruiter 6-second view: what sits in the top third, JD must-have keyword heatmap by section, one-page fit.
* resume versions: every generated resume per job, side-by-side diff and the reply rate of each version.
* keyword coverage chips: add-to-resume only for skills already in the verified profile.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from pymongo import DESCENDING

from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.email.tracking import INTERVIEW_CATEGORIES
from app.jobs.jd_parser import analyze_jd
from app.jobs.matching import _skill_key, candidate_skills
from app.profiles.service import get_profile
from app.resumes import craft, tailor
from app.resumes import service as resumes
from app.schemas.resume import ParsedResume
from app.services.audit import log_action
from app.studio import render
from app.utils import utcnow

router = APIRouter(tags=["studio-quality"])
KIND = "ATS Resume"
INTERVIEW_STATUSES = {"INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED", "SCREENING", "ASSESSMENT", "OFFER"}

_PASSIVE = re.compile(r"\b(?:was|were|is|are|been|being|be)\s+(?:\w+ly\s+)?(?:\w+ed|built|made|done|run|written|given|taken|seen|shown)\b", re.I)
_OUTCOME = re.compile(r"\b(?:reduc|improv|increas|cut|sav|faster|speed|boost|grew|growth|eliminat|prevent|catch|caught|achiev|deliver|enabl|"
                      r"lower|raise|accelerat|stabili|minimi|maximi|decreas)\w*", re.I)
_WEAK = re.compile(r"^(?:responsible|worked|involved|participated|helped|assisted|handled|did|was|were|part of|utili[sz]ed|used|"
                   r"duties|tasked|exposure)\b", re.I)
MAX_WORDS = 30
MIN_WORDS = 5


# ------------------------------------------------------------------ bullet strength

def check_bullet(text: str, metric: str | None = None) -> dict:
    """Flags + a rewrite. The rewrite re-opens the bullet with an action verb, trims it at a clause boundary and, only if the user
    typed a real metric, appends it. It never adds a number, tool or claim of its own."""
    b = re.sub(r"\s+", " ", re.sub(r"^[\s•\-–*·]+", "", text or "")).strip()
    words = len(b.split())
    flags: list[dict] = []
    if _WEAK.match(b) or (b and not craft.starts_with_action_verb(b)):
        flags.append({"code": "weak_verb", "message": "Starts with a weak or missing action verb."})
    if b and not craft.has_number(b) and not _OUTCOME.search(b):
        flags.append({"code": "no_outcome", "message": "No result or number: what changed because of your work?"})
    if words > MAX_WORDS:
        flags.append({"code": "too_long", "message": f"{words} words; aim for {MAX_WORDS} or fewer."})
    if words and words < MIN_WORDS:
        flags.append({"code": "too_short", "message": "Too short to show what you did."})
    if _PASSIVE.search(b):
        flags.append({"code": "passive", "message": "Passive voice: say what you did, not what was done."})
    rewrite = craft.strengthen(b)
    if words > MAX_WORDS:
        rewrite = craft.condense(rewrite)
    ask = None
    if any(f["code"] == "no_outcome" for f in flags):
        metric = (metric or "").strip()
        if metric:
            rewrite = f"{rewrite.rstrip('.')}, {metric.rstrip('.')}."
        else:
            ask = {"field": "metric", "prompt": "Add the real result (a number, %, time saved or volume). Saige won't make one up."}
    score = max(0, 100 - 25 * len(flags))
    return {"original": b, "flags": flags, "score": score, "rewrite": rewrite if rewrite != b else None, "ask": ask}


def bullets_of(r: ParsedResume) -> list[dict]:
    out = []
    for e in r.experience:
        for b in e.achievements + e.responsibilities:
            out.append({"where": f"{e.title or ''} @ {e.company or ''}".strip(" @"), "text": b})
    for pr in r.projects:
        out += [{"where": f"Project: {pr.name}", "text": h} for h in pr.highlights]
    return out


def check_resume(r: ParsedResume) -> dict:
    items = [{**b, **check_bullet(b["text"])} for b in bullets_of(r)]
    weak = [i for i in items if i["flags"]]
    return {"items": items, "weak": len(weak), "total": len(items),
            "score": round(sum(i["score"] for i in items) / len(items)) if items else None}


# ------------------------------------------------------------------ recruiter 6-second view

LINES_PER_PAGE = 54
CHARS_PER_LINE = 100


def _row_lines(kind: str, text: str) -> int:
    width = CHARS_PER_LINE - (6 if kind == "b" else 0)
    return max(1, -(-len(text) // width))


def six_second_view(r: ParsedResume, jd, template: str = "modern", order: list[str] | None = None, headline: str | None = None) -> dict:
    t = render.with_order(render.TEMPLATES.get(template, render.TEMPLATES["modern"]), order)
    secs = render.sections(r, t)
    top_budget = LINES_PER_PAGE // 3 - 4  # name, headline and contact take the first lines
    used, top_text, top_sections = 0, [], []
    for head, rows in secs:
        if used >= top_budget:
            break
        top_sections.append(head)
        used += 2
        for kind, text, _right in rows:
            if used >= top_budget:
                break
            used += _row_lines(kind, text)
            top_text.append(text)
    top_blob = " ".join([r.name or "", headline or "", *top_text]).lower()
    total = 4 + sum(2 + sum(_row_lines(k, x) for k, x, _ in rows) for _h, rows in secs)
    # heatmap: how often each must-have appears in each section
    must = list(dict.fromkeys(jd.required_skills))[:15]
    parts = {"summary": r.summary or "", "skills": " ".join(r.skills),
             "experience": " ".join(x for e in r.experience for x in e.achievements + e.responsibilities + e.technologies),
             "projects": " ".join(x for p in r.projects for x in [*p.highlights, *p.technologies])}
    from app.services.skills_vocab import find_skills

    found = {k: {_skill_key(s) for s in find_skills(v)} | {_skill_key(s) for s in re.findall(r"[\w+#./-]+", v)} for k, v in parts.items()}
    heat = []
    for s in must:
        k = _skill_key(s)
        counts = {}
        for sec, txt in parts.items():
            n = len(re.findall(rf"(?<![a-z0-9]){re.escape(s.lower())}(?![a-z0-9])", txt.lower()))
            counts[sec] = n or int(k in found[sec])  # a JD spelling variant of the same skill still counts once
        heat.append({"keyword": s, "counts": counts, "total": sum(counts.values()), "in_top_third": s.lower() in top_blob or any(
            _skill_key(x) == k for x in find_skills(top_blob))})
    seen = {"name": r.name, "headline": headline, "contact": render._contact(r)[:3],
            "summary_start": (r.summary or "")[:160] or None,
            "latest_role": (f"{r.experience[0].title or ''} @ {r.experience[0].company or ''}".strip(" @") if r.experience else None),
            "top_skills": r.skills[:8]}
    pages = round(total / LINES_PER_PAGE, 2)
    return {"seen_first": seen, "top_third_sections": top_sections, "heatmap": heat,
            "top_third_coverage": round(100 * sum(h["in_top_third"] for h in heat) / len(heat)) if heat else None,
            "one_page": {"estimated_lines": total, "pages": pages, "fits": pages <= 1.0,
                         "hint": None if pages <= 1.0 else (f"About {round((pages - 1) * LINES_PER_PAGE)} line(s) over one page: "
                                                         "trim the oldest role's bullets or pick the Compact template.")}}


# ------------------------------------------------------------------ versions

def diff_resumes(a: ParsedResume, b: ParsedResume) -> dict:
    def bl(r: ParsedResume) -> list[str]:
        return [x["text"] for x in bullets_of(r)]
    ba, bb = bl(a), bl(b)
    ska, skb = {_skill_key(s): s for s in a.skills}, {_skill_key(s): s for s in b.skills}
    return {"summary": {"a": a.summary, "b": b.summary, "changed": (a.summary or "") != (b.summary or "")},
            "skills_added": [v for k, v in skb.items() if k not in ska], "skills_removed": [v for k, v in ska.items() if k not in skb],
            "skills_order_changed": [k for k in ska if k in skb] != [k for k in skb if k in ska],
            "bullets_added": [x for x in bb if x not in ba], "bullets_removed": [x for x in ba if x not in bb],
            "bullets_reordered": ba != bb and sorted(ba) == sorted(bb),
            "projects": {"a": [p.name for p in a.projects], "b": [p.name for p in b.projects]}}


async def _version_stats(db: AsyncIOMotorDatabase, uid: str, resume_ids: list[str]) -> dict[str, dict]:
    stats = {rid: {"sent": 0, "replies": 0, "interviews": 0} for rid in resume_ids}
    apps = {a["_id"]: a async for a in db[c.APPLICATIONS].find({"user_id": uid, "resume_id": {"$in": resume_ids}}, {"resume_id": 1, "status": 1})}
    seen_apps: set[str] = set()
    async for e in db[c.SENT_EMAILS].find({"user_id": uid, "$or": [{"resume_id": {"$in": resume_ids}}, {"application_id": {"$in": list(apps)}}]}):
        rid = e.get("resume_id") or apps.get(e.get("application_id"), {}).get("resume_id")
        if rid not in stats or e["status"] == "bounced":
            continue
        s = stats[rid]
        s["sent"] += 1
        s["replies"] += e["status"] == "replied"
        s["interviews"] += e["status"] == "replied" and e.get("reply_category") in INTERVIEW_CATEGORIES
        if e.get("application_id"):
            seen_apps.add(e["application_id"])
    for a in apps.values():  # interviews that came through an application status even if the email wasn't tracked
        if a.get("status") in INTERVIEW_STATUSES and not stats[a["resume_id"]]["interviews"]:
            stats[a["resume_id"]]["interviews"] += 1
    for s in stats.values():
        s["reply_rate"] = round(100 * s["replies"] / s["sent"], 1) if s["sent"] else None
    return stats


@router.get("/versions")
async def versions(job: str | None = None, company: str | None = None, user: dict = Depends(get_current_user),
                   db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Every ATS resume generated, newest first (filter by job or company), with sends, replies and interviews per version."""
    q: dict = {"user_id": user["_id"], "kind": KIND, "status": {"$ne": "deleted"}}
    if job:
        q["$or"] = [{"job_id": job}, {"career_job_id": job}]
    if company:
        q["company"] = company
    rows = await db[c.RESUMES].find(q).sort("created_at", DESCENDING).to_list(200)
    stats = await _version_stats(db, user["_id"], [d["_id"] for d in rows])
    return {"items": [{"id": d["_id"], "name": d["name"], "company": d.get("company"), "title": d.get("target_title"), "template": d.get("template"),
                       "job_id": d.get("job_id") or d.get("career_job_id"), "created_at": d["created_at"].isoformat(),
                       "ats_score": (d.get("ats") or {}).get("score"), "ats_before": (d.get("ats_before_after") or {}).get("before"),
                       **stats[d["_id"]]} for d in rows]}


async def _parsed(db: AsyncIOMotorDatabase, uid: str, resume_id: str) -> tuple[dict, ParsedResume]:
    d = await resumes.get_owned(db, uid, resume_id)
    cur = await resumes.current_version(db, d)
    if not cur:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume has no content")
    return d, ParsedResume.model_validate(cur["parsed"])


@router.get("/versions/compare")
async def compare(a: str, b: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    da, pa = await _parsed(db, user["_id"], a)
    dbb, pb = await _parsed(db, user["_id"], b)
    stats = await _version_stats(db, user["_id"], [a, b])
    return {"a": {"id": a, "name": da["name"], "ats_score": (da.get("ats") or {}).get("score"), **stats[a]},
            "b": {"id": b, "name": dbb["name"], "ats_score": (dbb.get("ats") or {}).get("score"), **stats[b]}, "diff": diff_resumes(pa, pb)}


# ------------------------------------------------------------------ per-resume tools

class BulletIn(BaseModel):
    text: str = Field(min_length=1, max_length=600)
    metric: str | None = Field(default=None, max_length=120)


@router.post("/bullets/check")
async def bullet_check(body: BulletIn, user: dict = Depends(get_current_user)):
    """Check one bullet; pass `metric` (your own real number) to get a rewrite that includes it."""
    return check_bullet(body.text, body.metric)


@router.get("/resumes/{resume_id}/bullets")
async def resume_bullets(resume_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    _d, parsed = await _parsed(db, user["_id"], resume_id)
    return check_resume(parsed)


async def _jd_of(d: dict):
    return analyze_jd(d.get("target_title") or "", d.get("jd_text") or "")


@router.get("/resumes/{resume_id}/recruiter-view")
async def recruiter_view(resume_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    d, parsed = await _parsed(db, user["_id"], resume_id)
    headline = (d.get("headline") or "").split(" · ")[0] or None
    return six_second_view(parsed, await _jd_of(d), d.get("template") or "modern", d.get("section_order"), headline)


@router.get("/resumes/{resume_id}/coverage")
async def coverage(resume_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """One chip per JD keyword: on the resume / verified but not on it (add in one click) / not verified (confirm first)."""
    d, parsed = await _parsed(db, user["_id"], resume_id)
    jd = await _jd_of(d)
    have = candidate_skills(await get_profile(db, user["_id"]))
    on = {_skill_key(s) for s in parsed.skills} | {_skill_key(s) for s in tailor.resume_text(parsed).split()}
    chips = []
    for kw in dict.fromkeys(jd.required_skills + jd.preferred_skills):
        k = _skill_key(kw)
        state = "on_resume" if k in on else "can_add" if k in have else "needs_confirmation"
        chips.append({"keyword": kw, "required": kw in jd.required_skills, "state": state})
    return {"chips": chips, "covered": sum(x["state"] == "on_resume" for x in chips), "total": len(chips)}


class AddSkillIn(BaseModel):
    skill: str = Field(min_length=1, max_length=60)


@router.post("/resumes/{resume_id}/add-skill")
async def add_skill(resume_id: str, body: AddSkillIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Put a skill on this resume only if it is already in your verified profile. Others go through /skills/confirm first."""
    uid = user["_id"]
    d, parsed = await _parsed(db, uid, resume_id)
    if _skill_key(body.skill) not in candidate_skills(await get_profile(db, uid)):
        raise HTTPException(status.HTTP_409_CONFLICT, {"status": "CONFIRMATION_REQUIRED",
                                                       "message": f"{body.skill} isn't in your verified profile. Confirm you really have it first."})
    if any(_skill_key(s) == _skill_key(body.skill) for s in parsed.skills):
        return {"added": False, "ats": d.get("ats")}
    new = parsed.model_copy(update={"skills": [body.skill.strip(), *parsed.skills]})
    await resumes.add_version(db, d, parsed=new, raw_text=tailor.resume_text(new), source="studio", changes=[f"Added verified skill: {body.skill}"],
                              base_resume_id=d.get("base_resume_id"), job_id=d.get("job_id"))
    report = tailor.ats_report(new, await _jd_of(d))
    await db[c.RESUMES].update_one({"_id": resume_id}, {"$set": {"ats": report, "updated_at": utcnow()}})
    await log_action(db, user_id=uid, action="studio.skill_added_to_resume", entity="resume", entity_id=resume_id, details={"skill": body.skill})
    return {"added": True, "ats": report}

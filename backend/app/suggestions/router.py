"""Resume & profile coach agent (/api/suggestions): concrete, ranked improvements read from the user's own records.

It never writes a claim for the user: every suggestion points at data the user adds or confirms themselves
(skills the jobs they track keep asking for, missing links, bullets without results, a stale resume)."""

import re
from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.profiles.service import get_profile
from app.services.agent_runs import agent_run
from app.services.audit import log_action
from app.services.notify import notify
from app.utils import utcnow

router = APIRouter(prefix="/suggestions", tags=["suggestions"])
_NUM = re.compile(r"\d")


def _s(area: str, priority: int, title: str, why: str, link: str, items: list[str] | None = None) -> dict:
    return {"id": re.sub(r"[^a-z0-9]+", "-", title.lower())[:60], "area": area, "priority": priority, "title": title,
            "why": why, "link": link, "items": items or []}


async def suggest(db: AsyncIOMotorDatabase, uid: str) -> list[dict]:
    p = await get_profile(db, uid)
    k, per = p.knowledge, p.personal
    have = {s.lower() for group in p.skills.model_dump().values() for s in group}
    out: list[dict] = []

    # Skills the user's own tracked jobs keep asking for (the user confirms only the ones they really have).
    asked: Counter[str] = Counter()
    async for j in db[c.JOBS].find({"user_id": uid}, {"match.missing_required_skills": 1}).sort("_id", -1).limit(200):
        asked.update(s for s in ((j.get("match") or {}).get("missing_required_skills") or []) if s.lower() not in have)
    top = [s for s, n in asked.most_common(6) if n >= 2]
    if top:
        out.append(_s("profile", 1, "Skills your target jobs keep asking for",
                      f"These appear as missing in {sum(asked[s] for s in top)} job matches. Add the ones you really have.", "/profile", top))
    if not k.professional_summary:
        out.append(_s("resume", 1, "Add a professional summary", "Recruiters and ATS read the summary first.", "/profile"))
    if len(k.projects) < 2:
        out.append(_s("resume", 2, "Add more projects", "Projects show hands-on work; 2–4 is ideal. Upload a resume that lists them.", "/resumes"))
    bare = [f"{e.title} · {e.company}" for e in k.experience if (e.responsibilities or e.achievements)
            and not any(_NUM.search(b) for b in e.responsibilities + e.achievements)]
    if bare:
        out.append(_s("resume", 2, "Add results you can verify to your bullets",
                      "No bullet in these roles has a number (%, time saved, defects, users). Add only figures you know.", "/profile", bare))
    from app.studio.quality import check_bullet

    all_b = [b for e in k.experience for b in e.responsibilities + e.achievements]
    weak = [b for b in all_b if check_bullet(b)["flags"]]
    if all_b and len(weak) >= 2:
        out.append(_s("resume", 2, "Rewrite weak bullets", f"{len(weak)} of {len(all_b)} bullets have a weak verb, no result, or are too long.",
                      "/studio", [b[:90] for b in weak[:4]]))
    missing = [lbl for lbl, v in (("LinkedIn URL", per.linkedin_url), ("Phone", per.phone), ("Location", per.current_location),
                                  ("Notice period", per.notice_period_days), ("Expected CTC", per.expected_ctc)) if v in (None, "")]
    if missing:
        out.append(_s("profile", 2, "Fill the details recruiters ask for", "Applications and email drafts use these.", "/profile", missing))
    if not per.github_url and not per.portfolio_url:
        out.append(_s("profile", 3, "Link GitHub or a portfolio", "Shows real work behind your skills.", "/profile"))
    if not k.certifications:
        out.append(_s("profile", 3, "Add certifications you hold", "Many JDs filter on them (ISTQB, AWS, Azure…).", "/profile"))
    latest = await db[c.RESUMES].find_one({"user_id": uid}, sort=[("updated_at", -1)])
    if not latest:
        out.append(_s("resume", 1, "Upload your resume", "Saige builds tailored resumes from it.", "/resumes"))
    elif latest.get("updated_at") and utcnow().replace(tzinfo=None) - latest["updated_at"].replace(tzinfo=None) > timedelta(days=30):
        out.append(_s("resume", 3, "Refresh your resume", "Your newest resume is over 30 days old.", "/studio"))
    await rank(db, uid, out)
    return sorted(out, key=lambda s: (-s["impact"], s["priority"]))


# Expected effect on replies when this is fixed (0-100) before the evidence below adjusts it.
BASE_IMPACT = {"skills-your-target-jobs-keep-asking-for": 70, "add-a-professional-summary": 60, "add-results-you-can-verify-to-your-bullets": 65,
               "rewrite-weak-bullets": 62, "upload-your-resume": 95, "add-more-projects": 40, "fill-the-details-recruiters-ask-for": 45,
               "link-github-or-a-portfolio": 25, "add-certifications-you-hold": 22, "refresh-your-resume": 30}


async def rank(db: AsyncIOMotorDatabase, uid: str, items: list[dict]) -> None:
    """Score each suggestion by expected impact on replies and explain it in one line. Evidence used: your real reply rate
    (sent emails), the learned relevance model's weights (what actually led to likes and interviews) and your application outcomes."""
    sent = await db[c.SENT_EMAILS].find({"user_id": uid, "status": {"$in": ["sent", "replied"]}}, {"status": 1}).to_list(2000)
    replies = sum(e["status"] == "replied" for e in sent)
    rate = replies / len(sent) if len(sent) >= 5 else None
    model = await db[c.ML_MODELS].find_one({"_id": f"{uid}:relevance", "weights": {"$exists": True}}, {"weights": 1}) or {}
    w = model.get("weights") or {}
    gap_pull = -min(0.0, w.get("skills_missing", 0.0))     # the model learned that jobs you lack skills for don't work out
    overlap = max(0.0, w.get("skill_overlap", 0.0))        # ...and that a high share of matching skills does
    done = ["SCREENING", "INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED", "OFFER"]
    interviews = await db[c.APPLICATIONS].count_documents({"user_id": uid, "status": {"$in": done}})
    for s in items:
        impact, why = BASE_IMPACT.get(s["id"], 40), None
        if s["id"].startswith("skills-your-target"):
            boost = round(min(25, 10 * gap_pull + 10 * overlap))
            impact += boost
            why = (f"Your learned model weighs skill gaps against jobs you pursue (+{boost} impact)." if boost
                   else "Jobs you track keep listing these; confirming real ones lifts your match scores.")
        elif rate is not None and rate < 0.1 and s["area"] == "resume":
            impact += 15
            why = f"Only {round(rate * 100)}% of your {len(sent)} sent emails got a reply, so resume quality is the likely bottleneck."
        elif rate is not None and rate >= 0.25 and s["area"] == "resume":
            impact -= 15
            why = f"Your resume already gets {round(rate * 100)}% replies; this matters less than finding more roles."
        elif s["id"] == "fill-the-details-recruiters-ask-for" and interviews:
            impact += 10
            why = "You have interview traffic: complete details speed up the next steps."
        s["impact"] = max(1, min(100, impact))
        s["explain"] = why or {"upload-your-resume": "Nothing else works until Saige has a resume to tailor.",
                               "add-a-professional-summary": "Recruiters and ATS read the summary first, and it's the top of every tailored resume.",
                               "add-results-you-can-verify-to-your-bullets": "Recruiters remember numbers; add only ones you know.",
                               "rewrite-weak-bullets": "Strong verbs and outcomes are the quickest way to a better first impression.",
                               "add-more-projects": "Projects give the tailoring engine more relevant proof to pick from.",
                               "fill-the-details-recruiters-ask-for": "Applications and email drafts leave these out when they're missing.",
                               "link-github-or-a-portfolio": "Gives recruiters real work to check.",
                               "add-certifications-you-hold": "Some JDs filter on certifications.",
                               "refresh-your-resume": "Older resumes miss recent work and keywords."}.get(s["id"], s["why"])


@router.get("")
async def list_suggestions(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await suggest(db, user["_id"])


@router.post("/run")
async def run(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    async with agent_run(db, "profile_coach", uid, {}) as r:
        items = await suggest(db, uid)
        r.output = {"count": len(items)}
        r.action(f"{len(items)} suggestions")
    await log_action(db, user_id=uid, action="profile.coach_run", entity="suggestions", details={"count": len(items)})
    if items:
        await notify(db, user_id=uid, kind="profile_coach", title=f"{len(items)} ways to strengthen your resume & profile",
                     body=items[0]["title"], link="/")
    return items

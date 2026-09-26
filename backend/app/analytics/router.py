"""Dashboard / command-center metrics (spec sections 33-35, 52).

All numbers are plain counts from stored records - descriptive only, never inferred.
"""

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.deps import db_dep, get_current_user
from app.automation.service import get_settings_doc
from app.database import collections as c
from app.profiles.service import get_profile_doc, to_out
from app.utils import start_of_today

router = APIRouter(prefix="/analytics", tags=["analytics"])

FUNNEL_STAGES: list[tuple[str, list[str]]] = [
    ("Shortlisted", ["SHORTLISTED", "READY_TO_APPLY", "APPROVAL_REQUIRED"]),
    ("Applied", ["APPLIED"]),
    ("Recruiter Response", ["RECRUITER_REPLIED"]),
    ("Screening", ["SCREENING", "ASSESSMENT"]),
    ("Interview", ["INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED"]),
    ("Offer", ["OFFER"]),
]


@router.get("/dashboard")
async def dashboard(user: dict = Depends(get_current_user),
                    db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    today = start_of_today()

    async def count(coll: str, extra: dict | None = None, since_today: bool = False) -> int:
        q = {"user_id": uid, **(extra or {})}
        if since_today:
            q["created_at"] = {"$gte": today}
        return await db[coll].count_documents(q)

    apps = c.APPLICATIONS
    statuses = await db[apps].aggregate([
        {"$match": {"user_id": uid}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}},
    ]).to_list(length=50)
    by_status = {s["_id"]: s["n"] for s in statuses}

    # A job reaching a later stage has passed through the earlier ones.
    funnel = [{"stage": "Jobs Found", "count": await count(c.JOBS)},
              {"stage": "Relevant", "count": await count(c.JOBS, {"match.overall": {"$gte": 70}})}]
    running = 0
    stage_counts = []
    for stage, keys in reversed(FUNNEL_STAGES):
        running += sum(by_status.get(k, 0) for k in keys)
        stage_counts.append({"stage": stage, "count": running})
    funnel += list(reversed(stage_counts))

    profile = to_out(await get_profile_doc(db, uid))
    automation = await get_settings_doc(db, uid)
    return {
        "today": {
            "jobs_found": await count(c.JOBS, since_today=True),
            "relevant_jobs": await count(c.JOBS, {"match.overall": {"$gte": 70}}, since_today=True),
            "applications_ready": by_status.get("READY_TO_APPLY", 0),
            "applications_submitted": await count(apps, {"status": "APPLIED"}, since_today=True),
            "recruiters_contacted": await count(c.OUTREACH, since_today=True),
            "replies": await count(c.EMAILS, {"classification": "Recruiter Reply"}, since_today=True),
            "interviews": await count(c.INTERVIEWS, since_today=True),
            "rejections": by_status.get("REJECTED", 0),
            "offers": by_status.get("OFFER", 0),
        },
        "totals": {
            "jobs": await count(c.JOBS),
            "applications": sum(by_status.values()),
            "interviews": await count(c.INTERVIEWS),
            "resumes": await count(c.RESUMES, {"status": "active"}),
        },
        "high_match_jobs": [
            {"id": j["_id"], "title": j.get("title"), "company": j.get("company"),
             "score": j.get("match", {}).get("overall")}
            for j in await db[c.JOBS].find({"user_id": uid, "match.overall": {"$gte": 85}})
            .sort("match.overall", -1).to_list(length=5)
        ],
        "action_required": {
            "applications_need_approval": by_status.get("APPROVAL_REQUIRED", 0),
            "followups_due": await count(c.FOLLOWUPS, {"status": "due"}),
            "upcoming_interviews": await count(c.INTERVIEWS, {"status": "upcoming"}),
            "profile_changes_pending": await count(c.PROFILE_CHANGES,
                                                   {"approval_status": "USER_APPROVAL_REQUIRED"}),
            "unknown_profile_fields": len(profile["unknown_fields"]),
        },
        "funnel": funnel,
        "profile": {"completeness": profile["completeness"],
                    "unknown_fields": profile["unknown_fields"]},
        "automation": {"mode": automation.mode, "paused_all": automation.paused_all},
    }

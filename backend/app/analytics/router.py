"""Dashboard / command-center metrics (spec sections 33-35, 52).

All numbers are plain counts from stored records - descriptive only, never inferred.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.deps import db_dep, get_current_user
from app.automation.service import get_settings_doc
from app.database import collections as c
from app.profiles.service import get_profile_doc, to_out
from app.utils import start_of_today, utcnow

ACTIVITY_LABELS = {
    "job.discovered": "New job added", "job.duplicate_merged": "Duplicate job merged",
    "resume.uploaded": "Resume uploaded", "resume.generated": "Tailored resume generated",
    "cover_letter.generated": "Cover letter written", "application.prepared": "Application prepared",
    "application.status_changed": "Application status updated", "profile.updated": "Profile updated",
    "profile_change.applied": "Profile change applied", "matching.weights_updated": "Match weights changed",
    "automation.paused_all": "All automation paused", "automation.resumed_all": "Automation resumed",
}

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

    # --- 7-day daily series (oldest -> today) for sparklines and day-over-day deltas
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]

    async def series(coll: str, field: str, extra: dict | None = None) -> list[int]:
        out = []
        for d in days:
            q = {"user_id": uid, field: {"$gte": d, "$lt": d + timedelta(days=1)}, **(extra or {})}
            out.append(await db[coll].count_documents(q))
        return out

    trend = {
        "jobs_found": await series(c.JOBS, "created_at"),
        "relevant_jobs": await series(c.JOBS, "created_at", {"match.overall": {"$gte": 70}}),
        "applications_submitted": await series(apps, "applied_at"),
        "interviews": await series(c.INTERVIEWS, "created_at"),
        "documents": await series(c.RESUMES, "created_at", {"job_id": {"$ne": None}}),
        "profile_changes": await series(c.PROFILE_CHANGES, "created_at"),
    }

    # --- pipeline health (all-time, descriptive)
    applied_like = ["APPLIED", "RECRUITER_CONTACTED", "RECRUITER_REPLIED", "SCREENING", "ASSESSMENT",
                    "INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED", "OFFER", "REJECTED"]
    responded = ["RECRUITER_REPLIED", "SCREENING", "ASSESSMENT", "INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED",
                 "OFFER", "REJECTED"]
    interviewed = ["INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED", "OFFER"]
    n_applied = sum(by_status.get(k, 0) for k in applied_like)

    def pct(n: int) -> int | None:
        return round(100 * n / n_applied) if n_applied else None

    match_avg = await db[c.JOBS].aggregate([
        {"$match": {"user_id": uid, "match.overall": {"$ne": None}}},
        {"$group": {"_id": None, "avg": {"$avg": "$match.overall"}}}]).to_list(1)
    ats_avg = await db[c.RESUMES].aggregate([
        {"$match": {"user_id": uid, "ats.score": {"$ne": None}}},
        {"$group": {"_id": None, "avg": {"$avg": "$ats.score"}}}]).to_list(1)
    active = sum(by_status.get(k, 0) for k in
                 ("SHORTLISTED", "READY_TO_APPLY", "APPROVAL_REQUIRED", "APPLYING", "APPLIED", "RECRUITER_CONTACTED",
                  "RECRUITER_REPLIED", "SCREENING", "ASSESSMENT", "INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED"))
    followups_due = await db[c.FOLLOWUPS].count_documents(
        {"user_id": uid, "status": {"$in": ["scheduled", "due"]}, "due_at": {"$lte": utcnow()}})

    upcoming = await db[c.INTERVIEWS].find(
        {"user_id": uid, "status": {"$in": ["upcoming", "rescheduled"]}, "scheduled_at": {"$gte": utcnow() - timedelta(hours=2)}}
    ).sort("scheduled_at", 1).to_list(3)
    activity = await db[c.AUDIT_LOGS].find(
        {"user_id": uid, "action": {"$in": list(ACTIVITY_LABELS)}}).sort("timestamp", -1).to_list(7)

    from app.profiles.optimizer import skill_trends
    from app.profiles.service import get_profile
    trends, _ = await skill_trends(db, uid, await get_profile(db, uid))

    return {
        "trend": trend,
        "health": {
            "active_applications": active,
            "response_rate": pct(sum(by_status.get(k, 0) for k in responded)),
            "interview_rate": pct(sum(by_status.get(k, 0) for k in interviewed)),
            "offer_rate": pct(by_status.get("OFFER", 0)),
            "avg_match": round(match_avg[0]["avg"]) if match_avg and match_avg[0].get("avg") is not None else None,
            "avg_ats": round(ats_avg[0]["avg"]) if ats_avg and ats_avg[0].get("avg") is not None else None,
            "followups_due": followups_due,
            "tailored_resumes": await count(c.RESUMES, {"job_id": {"$ne": None}}),
            "cover_letters": await count(c.COVER_LETTERS),
        },
        "upcoming_interviews": [
            {"id": i["_id"], "company": i.get("company"), "role": i.get("role"), "round": i.get("round"),
             "scheduled_at": i["scheduled_at"].isoformat(), "meeting_url": i.get("meeting_url")} for i in upcoming],
        "activity": [
            {"id": a["_id"], "label": ACTIVITY_LABELS[a["action"]], "action": a["action"],
             "at": a["timestamp"].isoformat()} for a in activity],
        "skills_in_demand": [t.model_dump() for t in trends[:8]],
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

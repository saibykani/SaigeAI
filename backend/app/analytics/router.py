"""Dashboard / command-center metrics (spec sections 33-35, 52).

All numbers are plain counts from stored records - descriptive only, never inferred.
"""

import asyncio
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
    """Every query is independent, so they all run concurrently: one database round trip of
    latency instead of ~80 sequential ones."""
    from app.profiles.optimizer import skill_trends
    from app.profiles.service import get_profile

    uid = user["_id"]
    today = start_of_today()
    now = utcnow()
    apps = c.APPLICATIONS

    def count(coll: str, extra: dict | None = None, since_today: bool = False):
        q = {"user_id": uid, **(extra or {})}
        if since_today:
            q["created_at"] = {"$gte": today}
        return db[coll].count_documents(q)

    # --- 7-day daily series (oldest -> today) for sparklines and day-over-day deltas
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]

    async def series(coll: str, field: str, extra: dict | None = None) -> list[int]:
        return list(await asyncio.gather(*[
            db[coll].count_documents({"user_id": uid, field: {"$gte": d, "$lt": d + timedelta(days=1)}, **(extra or {})})
            for d in days]))

    async def trends_for_user():
        trends, _ = await skill_trends(db, uid, await get_profile(db, uid))
        return trends

    jobs = {
        "statuses": db[apps].aggregate([{"$match": {"user_id": uid}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}]).to_list(50),
        "jobs_total": count(c.JOBS),
        "jobs_relevant": count(c.JOBS, {"match.overall": {"$gte": 70}}),
        "profile_doc": get_profile_doc(db, uid),
        "automation": get_settings_doc(db, uid),
        "t_jobs": series(c.JOBS, "created_at"),
        "t_relevant": series(c.JOBS, "created_at", {"match.overall": {"$gte": 70}}),
        "t_applied": series(apps, "applied_at"),
        "t_interviews": series(c.INTERVIEWS, "created_at"),
        "t_documents": series(c.RESUMES, "created_at", {"job_id": {"$ne": None}}),
        "t_profile": series(c.PROFILE_CHANGES, "created_at"),
        "match_avg": db[c.JOBS].aggregate([
            {"$match": {"user_id": uid, "match.overall": {"$ne": None}}},
            {"$group": {"_id": None, "avg": {"$avg": "$match.overall"}}}]).to_list(1),
        "ats_avg": db[c.RESUMES].aggregate([
            {"$match": {"user_id": uid, "ats.score": {"$ne": None}}},
            {"$group": {"_id": None, "avg": {"$avg": "$ats.score"}}}]).to_list(1),
        "followups_due": db[c.FOLLOWUPS].count_documents(
            {"user_id": uid, "status": {"$in": ["scheduled", "due"]}, "due_at": {"$lte": now}}),
        "upcoming": db[c.INTERVIEWS].find(
            {"user_id": uid, "status": {"$in": ["upcoming", "rescheduled"]}, "scheduled_at": {"$gte": now - timedelta(hours=2)}}
        ).sort("scheduled_at", 1).to_list(3),
        "activity": db[c.AUDIT_LOGS].find(
            {"user_id": uid, "action": {"$in": list(ACTIVITY_LABELS)}}).sort("timestamp", -1).to_list(7),
        "trends": trends_for_user(),
        "tailored": count(c.RESUMES, {"job_id": {"$ne": None}}),
        "letters": count(c.COVER_LETTERS),
        "today_jobs": count(c.JOBS, since_today=True),
        "today_relevant": count(c.JOBS, {"match.overall": {"$gte": 70}}, since_today=True),
        "today_applied": count(apps, {"status": "APPLIED"}, since_today=True),
        "today_outreach": count(c.OUTREACH, since_today=True),
        "today_replies": count(c.EMAILS, {"classification": "Recruiter Reply"}, since_today=True),
        "today_interviews": count(c.INTERVIEWS, since_today=True),
        "interviews_total": count(c.INTERVIEWS),
        "resumes_total": count(c.RESUMES, {"status": "active"}),
        "high_match": db[c.JOBS].find({"user_id": uid, "match.overall": {"$gte": 85}}).sort("match.overall", -1).to_list(5),
        "due_followups": count(c.FOLLOWUPS, {"status": "due"}),
        "upcoming_count": count(c.INTERVIEWS, {"status": "upcoming"}),
        "pending_changes": count(c.PROFILE_CHANGES, {"approval_status": "USER_APPROVAL_REQUIRED"}),
    }
    r = dict(zip(jobs, await asyncio.gather(*jobs.values()), strict=True))

    by_status = {s["_id"]: s["n"] for s in r["statuses"]}
    profile = to_out(r["profile_doc"])
    automation = r["automation"]

    # A job reaching a later stage has passed through the earlier ones.
    funnel = [{"stage": "Jobs Found", "count": r["jobs_total"]}, {"stage": "Relevant", "count": r["jobs_relevant"]}]
    running = 0
    stage_counts = []
    for stage, keys in reversed(FUNNEL_STAGES):
        running += sum(by_status.get(k, 0) for k in keys)
        stage_counts.append({"stage": stage, "count": running})
    funnel += list(reversed(stage_counts))

    # --- pipeline health (all-time, descriptive)
    applied_like = ["APPLIED", "RECRUITER_CONTACTED", "RECRUITER_REPLIED", "SCREENING", "ASSESSMENT",
                    "INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED", "OFFER", "REJECTED"]
    responded = ["RECRUITER_REPLIED", "SCREENING", "ASSESSMENT", "INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED",
                 "OFFER", "REJECTED"]
    interviewed = ["INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED", "OFFER"]
    n_applied = sum(by_status.get(k, 0) for k in applied_like)

    def pct(n: int) -> int | None:
        return round(100 * n / n_applied) if n_applied else None

    def avg(rows: list[dict]) -> int | None:
        return round(rows[0]["avg"]) if rows and rows[0].get("avg") is not None else None

    active = sum(by_status.get(k, 0) for k in
                 ("SHORTLISTED", "READY_TO_APPLY", "APPROVAL_REQUIRED", "APPLYING", "APPLIED", "RECRUITER_CONTACTED",
                  "RECRUITER_REPLIED", "SCREENING", "ASSESSMENT", "INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED"))

    return {
        "trend": {
            "jobs_found": r["t_jobs"], "relevant_jobs": r["t_relevant"], "applications_submitted": r["t_applied"],
            "interviews": r["t_interviews"], "documents": r["t_documents"], "profile_changes": r["t_profile"],
        },
        "health": {
            "active_applications": active,
            "response_rate": pct(sum(by_status.get(k, 0) for k in responded)),
            "interview_rate": pct(sum(by_status.get(k, 0) for k in interviewed)),
            "offer_rate": pct(by_status.get("OFFER", 0)),
            "avg_match": avg(r["match_avg"]),
            "avg_ats": avg(r["ats_avg"]),
            "followups_due": r["followups_due"],
            "tailored_resumes": r["tailored"],
            "cover_letters": r["letters"],
        },
        "upcoming_interviews": [
            {"id": i["_id"], "company": i.get("company"), "role": i.get("role"), "round": i.get("round"),
             "scheduled_at": i["scheduled_at"].isoformat(), "meeting_url": i.get("meeting_url")} for i in r["upcoming"]],
        "activity": [
            {"id": a["_id"], "label": ACTIVITY_LABELS[a["action"]], "action": a["action"],
             "at": a["timestamp"].isoformat()} for a in r["activity"]],
        "skills_in_demand": [t.model_dump() for t in r["trends"][:8]],
        "today": {
            "jobs_found": r["today_jobs"],
            "relevant_jobs": r["today_relevant"],
            "applications_ready": by_status.get("READY_TO_APPLY", 0),
            "applications_submitted": r["today_applied"],
            "recruiters_contacted": r["today_outreach"],
            "replies": r["today_replies"],
            "interviews": r["today_interviews"],
            "rejections": by_status.get("REJECTED", 0),
            "offers": by_status.get("OFFER", 0),
        },
        "totals": {
            "jobs": r["jobs_total"],
            "applications": sum(by_status.values()),
            "interviews": r["interviews_total"],
            "resumes": r["resumes_total"],
        },
        "high_match_jobs": [
            {"id": j["_id"], "title": j.get("title"), "company": j.get("company"),
             "score": j.get("match", {}).get("overall")} for j in r["high_match"]],
        "action_required": {
            "applications_need_approval": by_status.get("APPROVAL_REQUIRED", 0),
            "followups_due": r["due_followups"],
            "upcoming_interviews": r["upcoming_count"],
            "profile_changes_pending": r["pending_changes"],
            "unknown_profile_fields": len(profile["unknown_fields"]),
        },
        "funnel": funnel,
        "profile": {"completeness": profile["completeness"],
                    "unknown_fields": profile["unknown_fields"]},
        "automation": {"mode": automation.mode, "paused_all": automation.paused_all},
    }


@router.get("/breakdowns")
async def breakdowns(weeks: int = 8, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    from app.analytics.service import breakdowns as compute

    return await compute(db, user["_id"], max(4, min(weeks, 26)))

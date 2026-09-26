"""My Activity: everything Saige did for you (applications, emails, replies, referrals, profile updates,
job discovery), plus a referral-run table grouped by job, built from your own records."""

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from app.auth.deps import db_dep, get_current_user
from app.database import collections as c

router = APIRouter(prefix="/activity", tags=["activity"])

# action prefix -> (group, label template)
LABELS: list[tuple[str, str, str]] = [
    ("auto_apply.run", "applications", "Auto-applier ran"),
    ("application.", "applications", "Application"),
    ("jobs.feed_saved", "jobs", "Saved jobs from Jobs for you"),
    ("jobs.discover_saved", "jobs", "Saved jobs from search"),
    ("job.", "jobs", "Job"),
    ("outreach.reply_drafted", "emails", "Reply drafted"),
    ("outreach.sent", "outreach", "Email sent"),
    ("outreach.", "outreach", "Outreach"),
    ("recruiter.", "outreach", "Recruiter"),
    ("email.", "emails", "Email received"),
    ("profile", "profile", "Profile"),
    ("linkedin", "profile", "LinkedIn"),
    ("naukri", "profile", "Naukri"),
    ("resume", "resumes", "Resume"),
    ("automation", "settings", "Settings changed"),
    ("auth.", "account", "Account"),
]


def describe(a: dict) -> dict:
    action, d = a.get("action", ""), a.get("details") or {}
    group, label = next(((g, lbl) for pre, g, lbl in LABELS if action.startswith(pre)), ("other", action))
    bits = [str(d[k]) for k in ("company", "role", "category", "kind", "status", "saved", "prepared") if d.get(k) not in (None, "", [])]
    return {"id": a["_id"], "at": a["timestamp"].isoformat() if a.get("timestamp") else None, "group": group,
            "action": action, "title": label if label != action else action.replace(".", " ").replace("_", " ").capitalize(),
            "detail": " · ".join(bits[:4]), "entity": a.get("entity"), "entity_id": a.get("entity_id")}


@router.get("")
async def activity(group: str | None = None, limit: int = Query(100, ge=1, le=300),
                   user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    rows = [describe(a) async for a in db[c.AUDIT_LOGS].find({"user_id": user["_id"]}).sort("timestamp", DESCENDING).limit(limit * 2)]
    if group:
        rows = [r for r in rows if r["group"] == group]
    groups: dict[str, int] = {}
    for r in rows:
        groups[r["group"]] = groups.get(r["group"], 0) + 1
    return {"items": rows[:limit], "groups": groups}


@router.get("/referrals")
async def referral_runs(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """One row per job (or company) you reached out about: who was contacted and where it stands."""
    uid = user["_id"]
    runs: dict[str, dict] = {}
    async for o in db[c.OUTREACH].find({"user_id": uid, "kind": {"$ne": "reply"}}).sort("created_at", DESCENDING).limit(500):
        key = o.get("job_id") or f"company:{o.get('company_key') or o.get('company')}"
        r = runs.setdefault(key, {"key": key, "job_id": o.get("job_id"), "company": o.get("company"), "role": None, "url": None,
                                  "people": [], "sent": 0, "replied": 0, "drafts": 0, "last_activity": None})
        r["people"].append(o.get("contact_name"))
        r["sent"] += o["status"] in ("sent", "replied", "no_response")
        r["replied"] += o["status"] == "replied"
        r["drafts"] += o["status"] in ("draft", "approved")
        at = o.get("updated_at") or o.get("created_at")
        if at and (not r["last_activity"] or at > r["last_activity"]):
            r["last_activity"] = at
    job_ids = [r["job_id"] for r in runs.values() if r["job_id"]]
    async for j in db[c.JOBS].find({"_id": {"$in": job_ids}}, {"title": 1, "application_url": 1}):
        for r in runs.values():
            if r["job_id"] == j["_id"]:
                r["role"], r["url"] = j.get("title"), j.get("application_url")
    out = []
    for r in runs.values():
        r["people"] = list(dict.fromkeys(p for p in r["people"] if p))
        r["status"] = "replied" if r["replied"] else "completed" if r["sent"] and not r["drafts"] else "in_progress" if r["sent"] else "draft"
        r["last_activity"] = r["last_activity"].isoformat() if r["last_activity"] else None
        out.append(r)
    out.sort(key=lambda r: r["last_activity"] or "", reverse=True)
    return out

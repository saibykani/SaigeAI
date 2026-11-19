# ruff: noqa: E501
"""Super admin console (/api/superadmin/*). Only super admins (require_super_admin). Never returns resume contents,
tokens, password hashes, audit details or the values of environment settings. Every action is audit-logged.
Analytics live in analytics.py, the user CRM in crm.py, metric definitions in metrics.py."""

import csv
import io
import re
import time
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.auth.deps import db_dep, get_current_user, require_csrf_header
from app.auth.roles import effective_role, require_super_admin
from app.config import get_settings
from app.database import collections as c
from app.recruiters.service import HARD_DAILY_CAP
from app.services.audit import log_action
from app.superadmin import analytics, crm
from app.superadmin import metrics as m
from app.utils import as_utc, new_id, start_of_today, utcnow

router = APIRouter(prefix="/superadmin", tags=["superadmin"], dependencies=[Depends(require_super_admin)])
announcements_router = APIRouter(prefix="/announcements", tags=["announcements"])
router.include_router(analytics.router)
router.include_router(crm.router)


def _iso(v) -> str | None:
    return as_utc(v).isoformat() if v else None


# ---------------------------------------------------------------- activity & audit

def _audit_query(user: str, user_id: str, action: str, feature: str, date_from: str, date_to: str, days: int | None) -> dict:
    query: dict = {}
    if user_id.strip():
        query["user_id"] = user_id.strip()
    if action.strip():
        query["action"] = {"$regex": re.escape(action.strip()), "$options": "i"}
    elif feature.strip():
        query["action"] = {"$regex": "^" + re.escape(feature.strip()) + "\\."}
    if date_from or date_to or days:
        start, end = m.parse_range(days or 30, date_from, date_to) if (date_from or date_to or days) else (None, None)
        query["timestamp"] = {"$gte": start, "$lt": end}
    return query


async def _resolve_user(db, query: dict, user: str) -> dict:
    if user.strip():
        rx = {"$regex": re.escape(user.strip()), "$options": "i"}
        ids = [u["_id"] for u in await db[c.USERS].find({"$or": [{"email": rx}, {"name": rx}]}, {"_id": 1}).to_list(length=None)]
        query["user_id"] = {"$in": ids} if "user_id" not in query else query["user_id"]
    return query


async def _audit_rows(db, query: dict, limit: int, skip: int = 0) -> tuple[list[dict], int]:
    total = await db[c.AUDIT_LOGS].count_documents(query)
    rows = await db[c.AUDIT_LOGS].find(query, {"user_id": 1, "action": 1, "entity": 1, "entity_id": 1, "timestamp": 1, "details.platform": 1}) \
        .sort("timestamp", -1).skip(skip).limit(limit).to_list(length=None)
    uids = list({r["user_id"] for r in rows if r.get("user_id")})
    emails = {u["_id"]: u["email"] for u in await db[c.USERS].find({"_id": {"$in": uids}}, {"email": 1}).to_list(length=None)}
    return [{"id": r["_id"], "at": _iso(r.get("timestamp")), "user_id": r.get("user_id"),
             "email": emails.get(r.get("user_id")) or ("system" if not r.get("user_id") else "deleted user"), "action": r["action"],
             "feature": m.feature_of(r["action"]), "entity": r.get("entity"), "entity_id": r.get("entity_id"),
             "platform": (r.get("details") or {}).get("platform")} for r in rows], total


def _audit_params(user: str = "", user_id: str = "", action: str = "", feature: str = "", date_from: str = "", date_to: str = "",
                  days: int | None = Query(None, ge=1, le=366)) -> tuple:
    return user, user_id, action, feature, date_from, date_to, days


@router.get("/audit")
async def audit(p: tuple = Depends(_audit_params), page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
                db: AsyncIOMotorDatabase = Depends(db_dep)):
    user, user_id, action, feature, df, dt, days = p
    query = await _resolve_user(db, _audit_query(user, user_id, action, feature, df, dt, days), user)
    items, total = await _audit_rows(db, query, page_size, (page - 1) * page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/audit/summary")
async def audit_summary(p: tuple = Depends(_audit_params), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Grouped counts for the same filters as /audit: by event type, feature, user and day."""
    user, user_id, action, feature, df, dt, days = p
    query = await _resolve_user(db, _audit_query(user, user_id, action, feature, df, dt, days), user)
    rows = await db[c.AUDIT_LOGS].aggregate([
        {"$match": query},
        {"$group": {"_id": {"a": "$action", "u": "$user_id", "d": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}}}, "n": {"$sum": 1}}},
    ]).to_list(length=None)
    by_action: dict[str, int] = {}
    by_feature: dict[str, int] = {}
    by_user: dict[str, int] = {}
    by_day: dict[str, int] = {}
    for r in rows:
        k = r["_id"]
        by_action[k["a"]] = by_action.get(k["a"], 0) + r["n"]
        f = m.feature_of(k["a"])
        by_feature[f] = by_feature.get(f, 0) + r["n"]
        if k["u"]:
            by_user[k["u"]] = by_user.get(k["u"], 0) + r["n"]
        by_day[k["d"]] = by_day.get(k["d"], 0) + r["n"]
    top_users = sorted(by_user.items(), key=lambda kv: -kv[1])[:10]
    emails = {u["_id"]: u["email"] for u in await db[c.USERS].find({"_id": {"$in": [u for u, _ in top_users]}}, {"email": 1}).to_list(length=None)}

    def top(d: dict, n: int = 30) -> list[dict]:
        return [{"name": k, "count": v} for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:n]]

    return {"total": sum(by_day.values()), "by_action": top(by_action, 60), "by_feature": top(by_feature),
            "by_user": [{"id": u, "name": emails.get(u, "deleted user"), "count": n} for u, n in top_users],
            "by_day": [{"date": d, "count": by_day[d]} for d in sorted(by_day)]}


@router.get("/audit/export.csv")
async def audit_csv(p: tuple = Depends(_audit_params), me: dict = Depends(require_super_admin), db: AsyncIOMotorDatabase = Depends(db_dep)):
    user, user_id, action, feature, df, dt, days = p
    query = await _resolve_user(db, _audit_query(user, user_id, action, feature, df, dt, days), user)
    items, _ = await _audit_rows(db, query, 5000)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["time", "user", "feature", "action", "entity", "entity_id", "platform"])
    for r in items:
        w.writerow([crm._cell(x) for x in (r["at"], r["email"], r["feature"], r["action"], r["entity"], r["entity_id"], r["platform"])])
    await log_action(db, user_id=me["_id"], action="superadmin.audit_exported", entity="audit", details={"rows": len(items)})
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=saige-audit.csv"})


# ---------------------------------------------------------------- system health

@router.get("/health")
async def health(db: AsyncIOMotorDatabase = Depends(db_dep)):
    t0 = time.perf_counter()
    try:
        await db.command("ping")
        ok = True
    except Exception:  # noqa: BLE001
        ok = False
    latency = round((time.perf_counter() - t0) * 1000, 1)
    t1 = time.perf_counter()
    await db[c.USERS].count_documents({"is_active": False})
    await db[c.AUDIT_LOGS].count_documents({"timestamp": {"$gte": utcnow() - timedelta(hours=24)}})
    query_ms = round((time.perf_counter() - t1) * 1000, 1)
    s = get_settings()
    flags = {  # configured yes/no only, never the values
        "Gmail": bool(s.google_client_id and s.google_client_secret), "Google sign-in": bool(s.google_oauth_enabled),
        "WhatsApp": bool(s.whatsapp_phone_number_id), "Web push (VAPID)": bool(s.vapid_public_key and s.vapid_private_key),
        "Telegram": bool(s.telegram_bot_token), "Jooble": bool(s.jooble_api_key), "Anthropic": bool(s.llm_enabled),
        "Cron secret": bool(s.cron_secret), "LinkedIn app": bool(s.linkedin_client_id),
    }
    counts = {}
    for coll in (c.USERS, c.RESUMES, c.APPLICATIONS, c.OUTREACH, c.EMAILS, c.AUDIT_LOGS, c.AGENT_RUNS, c.JOB_FEED, c.CAREER_JOBS, c.ANNOUNCEMENTS,
                 c.ADMIN_NOTES, c.REFRESH_TOKENS):
        try:
            counts[coll] = await db[coll].count_documents({})
        except Exception:  # noqa: BLE001
            counts[coll] = None
    d7, today = utcnow() - timedelta(days=7), start_of_today()
    jobs = []
    for name in await db[c.SCHEDULER_JOBS].distinct("job"):
        last = await db[c.SCHEDULER_JOBS].find({"job": name}).sort("started_at", -1).limit(1).to_list(length=1)
        if last:
            jobs.append({"job": name, "status": last[0].get("status"), "last_run": _iso(last[0].get("started_at")),
                         "failed_7d": await db[c.SCHEDULER_JOBS].count_documents({"job": name, "status": "failed", "started_at": {"$gte": d7}}),
                         "runs_7d": await db[c.SCHEDULER_JOBS].count_documents({"job": name, "started_at": {"$gte": d7}})})
    fails = await db[c.AGENT_RUNS].find({"status": "failed", "start_time": {"$gte": d7}}, {"agent_name": 1, "errors": 1, "start_time": 1}) \
        .sort("start_time", -1).limit(25).to_list(length=None)
    per_user = await db[c.OUTREACH].aggregate([{"$match": {"sent_at": {"$gte": today}}}, {"$group": {"_id": "$user_id", "n": {"$sum": 1}}}]).to_list(length=None)
    queued = await db[c.OUTREACH].count_documents({"status": "approved", "queued": True})
    return {"database": {"ok": ok, "latency_ms": latency, "query_ms": query_ms}, "collections": counts, "scheduler": jobs, "feature_flags": flags,
            "email_queue": {"sent_today": sum(r["n"] for r in per_user), "senders_today": len(per_user), "cap_per_user": HARD_DAILY_CAP,
                            "users_at_cap": sum(1 for r in per_user if r["n"] >= HARD_DAILY_CAP), "queued": queued},
            "agent_runs_24h": {"total": await db[c.AGENT_RUNS].count_documents({"start_time": {"$gte": utcnow() - timedelta(hours=24)}}),
                               "failed": await db[c.AGENT_RUNS].count_documents({"status": "failed", "start_time": {"$gte": utcnow() - timedelta(hours=24)}})},
            "failures": [{"at": _iso(f.get("start_time")), "agent": f.get("agent_name"),
                          "error": "; ".join(f.get("errors") or [])[:300]} for f in fails]}


# ---------------------------------------------------------------- announcements

class AnnouncementIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=1000)
    level: Literal["info", "warning", "success"] = "info"
    audience: Literal["all", "jobseeker", "recruiter"] = "all"
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


def _ann_status(d: dict, now) -> str:
    if d.get("starts_at") and as_utc(d["starts_at"]) > now:
        return "scheduled"
    if d.get("expires_at") and as_utc(d["expires_at"]) <= now:
        return "expired"
    return "live"


def _ann(d: dict) -> dict:
    return {"id": d["_id"], "title": d["title"], "message": d["message"], "level": d.get("level", "info"), "audience": d.get("audience", "all"),
            "created_at": _iso(d.get("created_at")), "starts_at": _iso(d.get("starts_at")), "expires_at": _iso(d.get("expires_at")),
            "status": _ann_status(d, utcnow())}


@router.get("/announcements")
async def list_announcements(db: AsyncIOMotorDatabase = Depends(db_dep)):
    return [_ann(d) for d in await db[c.ANNOUNCEMENTS].find({}).sort("created_at", -1).to_list(length=200)]


@router.post("/announcements", status_code=201, dependencies=[Depends(require_csrf_header)])
async def create_announcement(body: AnnouncementIn, me: dict = Depends(require_super_admin), db: AsyncIOMotorDatabase = Depends(db_dep)):
    now = utcnow()
    starts = as_utc(body.starts_at) if body.starts_at else None
    ends = as_utc(body.ends_at) if body.ends_at else (now + timedelta(days=body.expires_in_days) if body.expires_in_days else None)
    if ends and ends <= (starts or now):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The end must be after the start")
    doc = {"_id": new_id(), "title": body.title.strip(), "message": body.message.strip(), "level": body.level, "audience": body.audience,
           "created_at": now, "starts_at": starts, "expires_at": ends, "created_by": me["_id"]}
    await db[c.ANNOUNCEMENTS].insert_one(doc)
    await log_action(db, user_id=me["_id"], action="superadmin.announcement_created", entity="announcement", entity_id=doc["_id"],
                     details={"title": doc["title"], "audience": body.audience})
    return _ann(doc)


@router.delete("/announcements/{ann_id}", status_code=204, dependencies=[Depends(require_csrf_header)])
async def delete_announcement(ann_id: str, me: dict = Depends(require_super_admin), db: AsyncIOMotorDatabase = Depends(db_dep)):
    res = await db[c.ANNOUNCEMENTS].delete_one({"_id": ann_id})
    if not res.deleted_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Announcement not found")
    await log_action(db, user_id=me["_id"], action="superadmin.announcement_deleted", entity="announcement", entity_id=ann_id)
    return Response(status_code=204)


@announcements_router.get("")
async def active_announcements(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    now, role = utcnow(), effective_role(user)
    rows = await db[c.ANNOUNCEMENTS].find({"$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}]}).sort("created_at", -1).limit(30).to_list(length=30)
    live = [d for d in rows if _ann_status(d, now) == "live" and d.get("audience", "all") in ("all", role)]
    return [_ann(d) for d in live[:5]]

"""Super admin console (/api/superadmin/*). Only super admins (require_super_admin). Never returns resume contents,
tokens, password hashes, audit details or the values of environment settings. Every action is audit-logged."""

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
from app.auth.roles import effective_role, is_super_admin, require_super_admin
from app.config import get_settings
from app.database import collections as c
from app.services.audit import log_action
from app.utils import as_utc, new_id, start_of_today, utcnow

router = APIRouter(prefix="/superadmin", tags=["superadmin"], dependencies=[Depends(require_super_admin)])
announcements_router = APIRouter(prefix="/announcements", tags=["announcements"])


def _iso(v) -> str | None:
    return as_utc(v).isoformat() if v else None


async def _active_ids(db, since) -> set[str]:
    ids = {u["_id"] for u in await db[c.USERS].find({"last_active_at": {"$gte": since}}, {"_id": 1}).to_list(length=None)}
    ids |= {u for u in await db[c.AGENT_RUNS].distinct("user_id", {"start_time": {"$gte": since}}) if u}
    return ids


async def _group(db, coll: str, field: str, match: dict, limit: int = 30) -> list[dict]:
    rows = await db[coll].aggregate([{"$match": match}, {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
                                     {"$sort": {"count": -1}}, {"$limit": limit}]).to_list(length=None)
    return [{"name": r["_id"] or "unknown", "count": r["count"]} for r in rows]


# ---------------------------------------------------------------- overview + growth + features

@router.get("/overview")
async def overview(db: AsyncIOMotorDatabase = Depends(db_dep)):
    now, today = utcnow(), start_of_today()
    d7, d30 = now - timedelta(days=7), now - timedelta(days=30)
    users = await db[c.USERS].find({}, {"email": 1, "role": 1, "created_at": 1, "is_active": 1}).to_list(length=None)
    roles = {"jobseeker": 0, "recruiter": 0, "admin": 0}
    for u in users:
        roles[effective_role(u)] += 1

    def joined(t) -> int:
        return sum(1 for u in users if u.get("created_at") and as_utc(u["created_at"]) >= t)

    sent = {"status": "sent"}
    kpis = {
        "total_users": len(users), "jobseekers": roles["jobseeker"], "recruiters": roles["recruiter"], "admins": roles["admin"],
        "disabled": sum(1 for u in users if u.get("is_active", True) is False),
        "active_24h": len(await _active_ids(db, now - timedelta(hours=24))), "active_7d": len(await _active_ids(db, d7)),
        "active_30d": len(await _active_ids(db, d30)),
        "new_today": joined(today), "new_7d": joined(d7), "new_30d": joined(d30),
        "resumes": await db[c.RESUMES].count_documents({}),
        "applications": await db[c.APPLICATIONS].count_documents({}),
        "applications_sent": await db[c.APPLICATIONS].count_documents({"status": {"$in": ["APPLIED", "INTERVIEW", "OFFER", "OFFERED", "HIRED"]}}),
        "emails_sent_today": await db[c.OUTREACH].count_documents({**sent, "sent_at": {"$gte": today}}),
        "emails_sent_7d": await db[c.OUTREACH].count_documents({**sent, "sent_at": {"$gte": d7}}),
        "agent_runs_30d": await db[c.AGENT_RUNS].count_documents({"start_time": {"$gte": d30}}),
        "errors_24h": await db[c.AGENT_RUNS].count_documents({"status": "failed", "start_time": {"$gte": now - timedelta(hours=24)}}),
    }
    return {"kpis": kpis, "agent_runs_by_type": await _group(db, c.AGENT_RUNS, "agent_name", {"start_time": {"$gte": d30}})}


@router.get("/growth")
async def growth(db: AsyncIOMotorDatabase = Depends(db_dep)):
    today = start_of_today()
    days = [(today - timedelta(days=i)).date() for i in range(89, -1, -1)]
    since = today - timedelta(days=89)
    series = {d: {"date": d.isoformat(), "signups": 0, "active": 0, "applications": 0} for d in days}

    def bump(ts, key, who=None, seen=None):
        if not ts:
            return
        d = as_utc(ts).date()
        if d in series:
            if seen is not None:
                if (d, who) in seen:
                    return
                seen.add((d, who))
            series[d][key] += 1

    async for u in db[c.USERS].find({"created_at": {"$gte": since}}, {"created_at": 1}):
        bump(u["created_at"], "signups")
    seen: set = set()
    async for r in db[c.AGENT_RUNS].find({"start_time": {"$gte": since}}, {"start_time": 1, "user_id": 1}):
        bump(r["start_time"], "active", r.get("user_id"), seen)
    async for a in db[c.APPLICATIONS].find({"created_at": {"$gte": since}}, {"created_at": 1}):
        bump(a["created_at"], "applications")
    return {"series": list(series.values())}


@router.get("/features")
async def features(days: int = Query(30, ge=1, le=365), db: AsyncIOMotorDatabase = Depends(db_dep)):
    since = utcnow() - timedelta(days=days)
    actions = await _group(db, c.AUDIT_LOGS, "action", {"timestamp": {"$gte": since}}, limit=500)
    by_feature: dict[str, int] = {}
    for a in actions:
        f = a["name"].split(".")[0]
        by_feature[f] = by_feature.get(f, 0) + a["count"]
    feats = sorted(({"name": k, "count": v} for k, v in by_feature.items()), key=lambda x: -x["count"])
    return {"days": days, "features": feats, "top_features": feats[:5], "actions": actions[:40],
            "agents": await _group(db, c.AGENT_RUNS, "agent_name", {"start_time": {"$gte": since}})}


# ---------------------------------------------------------------- users

@router.get("/users")
async def users(q: str = Query("", max_length=120), role: str = Query("", max_length=20), state: Literal["", "active", "disabled"] = "",
                sort: Literal["created_at", "last_active_at", "email", "role"] = "created_at", order: Literal["asc", "desc"] = "desc",
                page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), db: AsyncIOMotorDatabase = Depends(db_dep)):
    query: dict = {}
    if q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"email": rx}, {"name": rx}]
    if state:
        query["is_active"] = False if state == "disabled" else {"$ne": False}
    proj = {"email": 1, "name": 1, "role": 1, "is_active": 1, "created_at": 1, "last_active_at": 1}
    docs = await db[c.USERS].find(query, proj).to_list(length=None)
    if role:
        docs = [d for d in docs if effective_role(d) == role]

    def keyf(d):
        if sort == "role":
            return effective_role(d)
        v = d.get(sort)
        if isinstance(v, datetime):
            return (1, as_utc(v).timestamp())
        return (1, (v or "").lower()) if v else (0, 0)

    docs.sort(key=keyf, reverse=order == "desc")
    total = len(docs)
    docs = docs[(page - 1) * page_size: page * page_size]
    ids = [d["_id"] for d in docs]

    async def counts(coll: str, match: dict | None = None) -> dict:
        rows = await db[coll].aggregate([{"$match": {"user_id": {"$in": ids}, **(match or {})}}, {"$group": {"_id": "$user_id", "n": {"$sum": 1}}}]) \
            .to_list(length=None)
        return {r["_id"]: r["n"] for r in rows}

    res, apps, sent = await counts(c.RESUMES), await counts(c.APPLICATIONS), await counts(c.OUTREACH, {"status": "sent"})
    items = [{"id": d["_id"], "email": d["email"], "name": d.get("name", ""), "role": effective_role(d), "is_super_admin": is_super_admin(d),
              "is_active": d.get("is_active", True), "created_at": _iso(d.get("created_at")), "last_active_at": _iso(d.get("last_active_at")),
              "resumes": res.get(d["_id"], 0), "applications": apps.get(d["_id"], 0), "emails_sent": sent.get(d["_id"], 0), "plan": "none"}
             for d in docs]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def _target(db, user_id: str) -> dict:
    t = await db[c.USERS].find_one({"_id": user_id})
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return t


@router.get("/users/{user_id}")
async def user_detail(user_id: str, db: AsyncIOMotorDatabase = Depends(db_dep)):
    u = await _target(db, user_id)
    counts = {}
    for key, coll in (("resumes", c.RESUMES), ("applications", c.APPLICATIONS), ("emails", c.EMAILS), ("outreach", c.OUTREACH),
                      ("interviews", c.INTERVIEWS), ("agent_runs", c.AGENT_RUNS)):
        counts[key] = await db[coll].count_documents({"user_id": user_id})
    counts["emails_sent"] = await db[c.OUTREACH].count_documents({"user_id": user_id, "status": "sent"})
    audit = await db[c.AUDIT_LOGS].find({"user_id": user_id}, {"action": 1, "entity": 1, "timestamp": 1}).sort("timestamp", -1).limit(20) \
        .to_list(length=None)
    runs = await db[c.AGENT_RUNS].find({"user_id": user_id}, {"agent_name": 1, "status": 1, "start_time": 1}).sort("start_time", -1).limit(15) \
        .to_list(length=None)
    return {"id": user_id, "email": u["email"], "name": u.get("name", ""), "role": effective_role(u), "is_super_admin": is_super_admin(u),
            "is_active": u.get("is_active", True), "created_at": _iso(u.get("created_at")), "last_active_at": _iso(u.get("last_active_at")),
            "plan": "none", "sessions": await db[c.REFRESH_TOKENS].count_documents({"user_id": user_id, "revoked": {"$ne": True}}),
            "counts": counts,
            "recent_audit": [{"at": _iso(a.get("timestamp")), "action": a["action"], "entity": a.get("entity")} for a in audit],
            "recent_runs": [{"at": _iso(r.get("start_time")), "agent": r.get("agent_name"), "status": r.get("status")} for r in runs]}


class UserPatch(BaseModel):
    role: Literal["jobseeker", "recruiter", "admin"] | None = None
    is_active: bool | None = None


@router.patch("/users/{user_id}", dependencies=[Depends(require_csrf_header)])
async def patch_user(user_id: str, body: UserPatch, me: dict = Depends(require_super_admin), db: AsyncIOMotorDatabase = Depends(db_dep)):
    t = await _target(db, user_id)
    if is_super_admin(t):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "A super admin account can't be changed here")
    patch: dict = {}
    if body.role is not None and body.role != effective_role(t):
        patch["role"] = body.role
    if body.is_active is not None and body.is_active != t.get("is_active", True):
        patch["is_active"] = body.is_active
    if patch:
        await db[c.USERS].update_one({"_id": user_id}, {"$set": {**patch, "updated_at": utcnow()}})
        if patch.get("is_active") is False:
            await db[c.REFRESH_TOKENS].update_many({"user_id": user_id}, {"$set": {"revoked": True, "family_revoked": True}})
        await log_action(db, user_id=me["_id"], action="superadmin.user_updated", entity="user", entity_id=user_id,
                         details={"target_email": t["email"], **patch})
    u = await _target(db, user_id)
    return {"id": user_id, "role": effective_role(u), "is_active": u.get("is_active", True)}


@router.post("/users/{user_id}/sign-out", dependencies=[Depends(require_csrf_header)])
async def force_sign_out(user_id: str, me: dict = Depends(require_super_admin), db: AsyncIOMotorDatabase = Depends(db_dep)):
    t = await _target(db, user_id)
    res = await db[c.REFRESH_TOKENS].update_many({"user_id": user_id}, {"$set": {"revoked": True, "family_revoked": True}})
    await log_action(db, user_id=me["_id"], action="superadmin.force_sign_out", entity="user", entity_id=user_id,
                     details={"target_email": t["email"]})
    return {"revoked": res.modified_count}


class DeleteBody(BaseModel):
    confirm_email: str


@router.post("/users/{user_id}/delete", dependencies=[Depends(require_csrf_header)])
async def delete_user(user_id: str, body: DeleteBody, me: dict = Depends(require_super_admin), db: AsyncIOMotorDatabase = Depends(db_dep)):
    t = await _target(db, user_id)
    if is_super_admin(t):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "A super admin account can't be deleted here")
    if body.confirm_email.strip().lower() != t["email"].lower():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Type the user's email exactly to confirm")
    for coll in c.USER_SCOPED:  # same cascade as the user's own account deletion (privacy router)
        await db[coll].delete_many({"user_id": user_id})
    await db[c.TALENT_REQUESTS].delete_many({"candidate_id": user_id})
    await db[c.USERS].delete_one({"_id": user_id})
    await log_action(db, user_id=me["_id"], action="superadmin.user_deleted", entity="user", entity_id=user_id, details={"target_email": t["email"]})
    return {"deleted": True}


# ---------------------------------------------------------------- audit log

async def _audit_rows(db, user: str, action: str, date_from: str, date_to: str, limit: int, skip: int = 0) -> tuple[list[dict], int]:
    query: dict = {}
    if user.strip():
        rx = {"$regex": re.escape(user.strip()), "$options": "i"}
        ids = [u["_id"] for u in await db[c.USERS].find({"email": rx}, {"_id": 1}).to_list(length=None)]
        query["user_id"] = {"$in": ids}
    if action.strip():
        query["action"] = {"$regex": re.escape(action.strip()), "$options": "i"}
    rng: dict = {}
    try:
        if date_from:
            rng["$gte"] = as_utc(datetime.fromisoformat(date_from))
        if date_to:
            rng["$lt"] = as_utc(datetime.fromisoformat(date_to)) + timedelta(days=1)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Dates must be YYYY-MM-DD") from None
    if rng:
        query["timestamp"] = rng
    total = await db[c.AUDIT_LOGS].count_documents(query)
    rows = await db[c.AUDIT_LOGS].find(query, {"user_id": 1, "action": 1, "entity": 1, "entity_id": 1, "timestamp": 1}).sort("timestamp", -1) \
        .skip(skip).limit(limit).to_list(length=None)
    uids = list({r["user_id"] for r in rows if r.get("user_id")})
    emails = {u["_id"]: u["email"] for u in await db[c.USERS].find({"_id": {"$in": uids}}, {"email": 1}).to_list(length=None)}
    who = {r["_id"]: emails.get(r.get("user_id")) or ("system" if not r.get("user_id") else "deleted user") for r in rows}
    return [{"id": r["_id"], "at": _iso(r.get("timestamp")), "email": who[r["_id"]],
             "action": r["action"], "entity": r.get("entity"), "entity_id": r.get("entity_id")} for r in rows], total


@router.get("/audit")
async def audit(user: str = "", action: str = "", date_from: str = "", date_to: str = "", page: int = Query(1, ge=1),
                page_size: int = Query(50, ge=1, le=100), db: AsyncIOMotorDatabase = Depends(db_dep)):
    items, total = await _audit_rows(db, user, action, date_from, date_to, page_size, (page - 1) * page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/audit/export.csv")
async def audit_csv(user: str = "", action: str = "", date_from: str = "", date_to: str = "", me: dict = Depends(require_super_admin),
                    db: AsyncIOMotorDatabase = Depends(db_dep)):
    items, _ = await _audit_rows(db, user, action, date_from, date_to, 5000)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["time", "user", "action", "entity", "entity_id"])
    for r in items:
        w.writerow([r["at"], r["email"], r["action"], r["entity"] or "", r["entity_id"] or ""])
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
    s = get_settings()
    flags = {  # configured yes/no only, never the values
        "Gmail": bool(s.google_client_id and s.google_client_secret), "Google sign-in": bool(s.google_oauth_enabled),
        "WhatsApp": bool(s.whatsapp_phone_number_id), "Web push (VAPID)": bool(s.vapid_public_key and s.vapid_private_key),
        "Telegram": bool(s.telegram_bot_token), "Jooble": bool(s.jooble_api_key), "Anthropic": bool(s.llm_enabled),
        "Cron secret": bool(s.cron_secret), "LinkedIn app": bool(s.linkedin_client_id),
    }
    counts = {}
    for coll in (c.USERS, c.RESUMES, c.APPLICATIONS, c.OUTREACH, c.EMAILS, c.AUDIT_LOGS, c.AGENT_RUNS, c.JOB_FEED, c.CAREER_JOBS, c.ANNOUNCEMENTS):
        try:
            counts[coll] = await db[coll].count_documents({})
        except Exception:  # noqa: BLE001
            counts[coll] = None
    jobs = []
    for name in await db[c.SCHEDULER_JOBS].distinct("job"):
        last = await db[c.SCHEDULER_JOBS].find({"job": name}).sort("started_at", -1).limit(1).to_list(length=1)
        if last:
            jobs.append({"job": name, "status": last[0].get("status"), "last_run": _iso(last[0].get("started_at"))})
    fails = await db[c.AGENT_RUNS].find({"status": "failed", "start_time": {"$gte": utcnow() - timedelta(days=7)}},
                                        {"agent_name": 1, "errors": 1, "start_time": 1}).sort("start_time", -1).limit(25).to_list(length=None)
    return {"database": {"ok": ok, "latency_ms": latency}, "collections": counts, "scheduler": jobs, "feature_flags": flags,
            "failures": [{"at": _iso(f.get("start_time")), "agent": f.get("agent_name"),
                          "error": "; ".join(f.get("errors") or [])[:300]} for f in fails]}


# ---------------------------------------------------------------- announcements

class AnnouncementIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=1000)
    level: Literal["info", "warning", "success"] = "info"
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


def _ann(d: dict) -> dict:
    return {"id": d["_id"], "title": d["title"], "message": d["message"], "level": d.get("level", "info"),
            "created_at": _iso(d.get("created_at")), "expires_at": _iso(d.get("expires_at"))}


@router.get("/announcements")
async def list_announcements(db: AsyncIOMotorDatabase = Depends(db_dep)):
    return [_ann(d) for d in await db[c.ANNOUNCEMENTS].find({}).sort("created_at", -1).to_list(length=200)]


@router.post("/announcements", status_code=201, dependencies=[Depends(require_csrf_header)])
async def create_announcement(body: AnnouncementIn, me: dict = Depends(require_super_admin), db: AsyncIOMotorDatabase = Depends(db_dep)):
    now = utcnow()
    doc = {"_id": new_id(), "title": body.title.strip(), "message": body.message.strip(), "level": body.level, "created_at": now,
           "expires_at": now + timedelta(days=body.expires_in_days) if body.expires_in_days else None, "created_by": me["_id"]}
    await db[c.ANNOUNCEMENTS].insert_one(doc)
    await log_action(db, user_id=me["_id"], action="superadmin.announcement_created", entity="announcement", entity_id=doc["_id"],
                     details={"title": doc["title"]})
    return _ann(doc)


@router.delete("/announcements/{ann_id}", status_code=204, dependencies=[Depends(require_csrf_header)])
async def delete_announcement(ann_id: str, me: dict = Depends(require_super_admin), db: AsyncIOMotorDatabase = Depends(db_dep)):
    res = await db[c.ANNOUNCEMENTS].delete_one({"_id": ann_id})
    if not res.deleted_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Announcement not found")
    await log_action(db, user_id=me["_id"], action="superadmin.announcement_deleted", entity="announcement", entity_id=ann_id)
    return Response(status_code=204)


@announcements_router.get("")
async def active_announcements(_: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    now = utcnow()
    rows = await db[c.ANNOUNCEMENTS].find({"$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}]}).sort("created_at", -1).limit(5) \
        .to_list(length=5)
    return [_ann(d) for d in rows]

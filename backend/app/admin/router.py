"""Admin dashboard (/api/admin/*): platform KPIs, signups, feature usage, user management and an
activity feed. Admins only (require_admin); granting or revoking admin is reserved to the super admin.
Never returns resume contents, tokens, password hashes or audit details."""

import re
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.auth.deps import db_dep
from app.auth.roles import effective_role, is_super_admin, require_admin
from app.database import collections as c
from app.services.audit import log_action
from app.utils import as_utc, start_of_today, utcnow

router = APIRouter(prefix="/admin", tags=["admin"])


async def _count_by(db: AsyncIOMotorDatabase, coll: str, field: str, match: dict, limit: int = 20) -> list[dict]:
    rows = await db[coll].aggregate([
        {"$match": match}, {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}, {"$limit": limit},
    ]).to_list(length=None)
    return [{"name": r["_id"] or "unknown", "count": r["count"]} for r in rows]


async def _active_ids(db: AsyncIOMotorDatabase, since) -> set[str]:
    ids = {u["_id"] for u in await db[c.USERS].find({"last_active_at": {"$gte": since}}, {"_id": 1}).to_list(length=None)}
    ids |= {u for u in await db[c.AGENT_RUNS].distinct("user_id", {"start_time": {"$gte": since}}) if u}
    return ids


def _iso(v) -> str | None:
    return as_utc(v).isoformat() if v else None


@router.get("/overview")
async def overview(_: dict = Depends(require_admin), db: AsyncIOMotorDatabase = Depends(db_dep)):
    now, today = utcnow(), start_of_today()
    d7, d30 = now - timedelta(days=7), now - timedelta(days=30)
    users = await db[c.USERS].find({}, {"email": 1, "role": 1, "created_at": 1}).to_list(length=None)
    roles = {"jobseeker": 0, "recruiter": 0, "admin": 0}
    for u in users:
        roles[effective_role(u)] += 1

    def joined_since(t) -> int:
        return sum(1 for u in users if u.get("created_at") and as_utc(u["created_at"]) >= t)

    days = [(today - timedelta(days=i)).date() for i in range(29, -1, -1)]
    per_day = dict.fromkeys(days, 0)
    for u in users:
        if u.get("created_at"):
            d = as_utc(u["created_at"]).date()
            if d in per_day:
                per_day[d] += 1
    kpis = {
        "total_users": len(users), "jobseekers": roles["jobseeker"], "recruiters": roles["recruiter"], "admins": roles["admin"],
        "new_today": joined_since(today), "new_7d": joined_since(d7), "new_30d": joined_since(d30),
        "active_24h": len(await _active_ids(db, now - timedelta(hours=24))), "active_7d": len(await _active_ids(db, d7)),
        "resumes": await db[c.RESUMES].count_documents({}), "applications": await db[c.APPLICATIONS].count_documents({}),
        "portfolios_published": await db[c.PORTFOLIOS].count_documents({"published": True}),
        "agent_runs": await db[c.AGENT_RUNS].count_documents({}),
        "agent_runs_30d": await db[c.AGENT_RUNS].count_documents({"start_time": {"$gte": d30}}),
        "recruiter_jobs": await db[c.RECRUITER_JOBS].count_documents({}),
    }
    return {
        "kpis": kpis,
        "signups": [{"date": d.isoformat(), "count": per_day[d]} for d in days],
        "agent_usage": await _count_by(db, c.AGENT_RUNS, "agent_name", {"start_time": {"$gte": d30}}),
        "action_usage": await _count_by(db, c.AUDIT_LOGS, "action", {"timestamp": {"$gte": d30}}),
    }


@router.get("/users")
async def users(q: str = Query("", max_length=120), role: str = Query("", max_length=20), limit: int = Query(100, ge=1, le=500),
                _: dict = Depends(require_admin), db: AsyncIOMotorDatabase = Depends(db_dep)):
    query: dict = {}
    if q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"email": rx}, {"name": rx}]
    docs = await db[c.USERS].find(query, {"email": 1, "name": 1, "role": 1, "is_active": 1, "created_at": 1, "last_active_at": 1}) \
        .sort("created_at", -1).to_list(length=None)
    if role:
        docs = [d for d in docs if effective_role(d) == role]
    docs = docs[:limit]
    ids = [d["_id"] for d in docs]

    async def counts(coll: str) -> dict:
        rows = await db[coll].aggregate([{"$match": {"user_id": {"$in": ids}}}, {"$group": {"_id": "$user_id", "n": {"$sum": 1}}}]) \
            .to_list(length=None)
        return {r["_id"]: r["n"] for r in rows}

    res, apps = await counts(c.RESUMES), await counts(c.APPLICATIONS)
    return [{"id": d["_id"], "email": d["email"], "name": d.get("name", ""), "role": effective_role(d), "is_super_admin": is_super_admin(d),
             "is_active": d.get("is_active", True), "created_at": _iso(d.get("created_at")), "last_active_at": _iso(d.get("last_active_at")),
             "resumes": res.get(d["_id"], 0), "applications": apps.get(d["_id"], 0)} for d in docs]


class UserPatch(BaseModel):
    role: Literal["jobseeker", "recruiter", "admin"] | None = None
    is_active: bool | None = None


@router.patch("/users/{user_id}")
async def update_user(user_id: str, body: UserPatch, admin: dict = Depends(require_admin), db: AsyncIOMotorDatabase = Depends(db_dep)):
    target = await db[c.USERS].find_one({"_id": user_id})
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if is_super_admin(target):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The super admin account can't be changed here")
    current = effective_role(target)
    patch: dict = {}
    if body.role is not None and body.role != current:
        if "admin" in (body.role, current) and not is_super_admin(admin):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the super admin can grant or revoke admin")
        patch["role"] = body.role
    if body.is_active is not None and body.is_active != target.get("is_active", True):
        if target["_id"] == admin["_id"]:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't disable your own account")
        if current == "admin" and not is_super_admin(admin):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the super admin can disable an admin")
        patch["is_active"] = body.is_active
    if patch:
        await db[c.USERS].update_one({"_id": user_id}, {"$set": {**patch, "updated_at": utcnow()}})
        if patch.get("is_active") is False:  # end every session at once
            await db[c.REFRESH_TOKENS].update_many({"user_id": user_id}, {"$set": {"revoked": True, "family_revoked": True}})
        await log_action(db, user_id=admin["_id"], action="admin.user_updated", entity="user", entity_id=user_id,
                         details={"target_email": target["email"], **patch})
    updated = await db[c.USERS].find_one({"_id": user_id})
    return {"id": user_id, "role": effective_role(updated), "is_active": updated.get("is_active", True)}


@router.get("/activity")
async def activity(limit: int = Query(50, ge=1, le=200), _: dict = Depends(require_admin), db: AsyncIOMotorDatabase = Depends(db_dep)):
    rows = await db[c.AUDIT_LOGS].find({}, {"user_id": 1, "action": 1, "entity": 1, "timestamp": 1}).sort("timestamp", -1) \
        .limit(limit).to_list(length=None)
    ids = list({r["user_id"] for r in rows if r.get("user_id")})
    emails = {u["_id"]: u["email"] for u in await db[c.USERS].find({"_id": {"$in": ids}}, {"email": 1}).to_list(length=None)}
    return [{"id": r["_id"], "at": _iso(r.get("timestamp")),
             "email": emails.get(r.get("user_id")) or ("system" if not r.get("user_id") else "deleted user"),
             "action": r["action"], "entity": r.get("entity")} for r in rows]

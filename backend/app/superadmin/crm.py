# ruff: noqa: E501
"""Super admin CRM (/api/superadmin/users*): user table with lifecycle + health, bulk actions, CSV export, User 360, notes and tags.
Never returns resume contents, tokens, password hashes or audit details. Every change is audit-logged."""

import csv
import io
import re
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.auth.deps import db_dep, require_csrf_header
from app.auth.roles import effective_role, is_super_admin, require_super_admin
from app.database import collections as c
from app.services.audit import log_action
from app.superadmin import metrics as m
from app.utils import as_utc, new_id, utcnow

router = APIRouter()
SORTS = ("created_at", "last_active_at", "email", "role", "health", "applications", "emails_sent", "resumes", "replies")


def _iso(v) -> str | None:
    return as_utc(v).isoformat() if v else None


def _cell(v) -> str:
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s  # spreadsheet formula injection guard


async def _tags_by_user(db) -> dict[str, list[str]]:
    return {t["_id"]: t.get("tags", []) for t in await db[c.USER_TAGS].find({}).to_list(length=None)}


async def _locations(db) -> dict[str, str]:
    out = {}
    async for p in db[c.CANDIDATE_PROFILES].find({}, {"user_id": 1, "personal.current_location": 1}):
        loc = (p.get("personal") or {}).get("current_location")
        if loc:
            out[p["user_id"]] = str(loc)[:80]
    return out


def _source(u: dict) -> str:
    return u.get("signup_source") or ("google" if u.get("google_sub") else "email")


async def _rows(db, *, q="", role="", state="", lifecycle="", tag="", health="", sort="created_at", order="desc") -> list[dict]:
    now = utcnow()
    query: dict = {}
    if q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"email": rx}, {"name": rx}]
    if state:
        query["is_active"] = False if state == "disabled" else {"$ne": False}
    docs = await db[c.USERS].find(query, {"email": 1, "name": 1, "role": 1, "is_active": 1, "created_at": 1, "last_active_at": 1, "google_sub": 1,
                                          "signup_source": 1}).to_list(length=None)
    roll, tags, locs = await m.user_rollup(db, now), await _tags_by_user(db), await _locations(db)
    rows = []
    for d in docs:
        if role and effective_role(d) != role:
            continue
        r = roll.get(d["_id"], {})
        sig = m.user_signals(d, r, now)
        t = tags.get(d["_id"], [])
        if (lifecycle and sig["lifecycle"] != lifecycle) or (tag and tag not in t) or (health and sig["health_label"] != health):
            continue
        rows.append({"id": d["_id"], "email": d["email"], "name": d.get("name", ""), "role": effective_role(d), "is_super_admin": is_super_admin(d),
                     "is_active": d.get("is_active", True), "created_at": _iso(d.get("created_at")), "last_active_at": _iso(sig["last_active"]),
                     "lifecycle": sig["lifecycle"], "health": sig["health"], "health_label": sig["health_label"], "source": _source(d),
                     "location": locs.get(d["_id"], ""), "tags": t, "resumes": r.get("resumes", 0), "applications": r.get("applications", 0),
                     "emails_sent": r.get("emails_sent", 0), "replies": r.get("replies", 0)})

    def key(x):
        v = x.get("last_active_at" if sort == "last_active_at" else sort)
        return (1, v.lower() if isinstance(v, str) else v) if v not in (None, "") else (0, 0)

    rows.sort(key=key, reverse=order == "desc")
    return rows


Filters = dict[str, str]


def _filters(q: str = "", role: str = "", state: Literal["", "active", "disabled"] = "", lifecycle: Literal["", "new", "activated", "engaged", "at_risk", "churned"] = "",
             tag: str = "", health: Literal["", "healthy", "fair", "low"] = "", sort: Literal[SORTS] = "created_at",  # type: ignore[valid-type]
             order: Literal["asc", "desc"] = "desc") -> dict:
    return {"q": q[:120], "role": role[:20], "state": state, "lifecycle": lifecycle, "tag": tag[:24], "health": health, "sort": sort, "order": order}


@router.get("/users")
async def users(f: dict = Depends(_filters), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), db=Depends(db_dep)):
    rows = await _rows(db, **f)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["lifecycle"]] = counts.get(r["lifecycle"], 0) + 1
    return {"items": rows[(page - 1) * page_size: page * page_size], "total": len(rows), "page": page, "page_size": page_size, "lifecycle_counts": counts}


@router.get("/users-export.csv")
async def users_csv(f: dict = Depends(_filters), me: dict = Depends(require_super_admin), db=Depends(db_dep)):
    rows = await _rows(db, **f)
    buf = io.StringIO()
    w = csv.writer(buf)
    cols = ["email", "name", "role", "is_active", "lifecycle", "health", "source", "location", "resumes", "applications", "emails_sent", "replies",
            "last_active_at", "created_at", "tags"]
    w.writerow(cols)
    for r in rows:
        w.writerow([_cell(", ".join(r[k]) if k == "tags" else r[k]) for k in cols])
    await log_action(db, user_id=me["_id"], action="superadmin.users_exported", entity="user", details={"rows": len(rows)})
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=saige-users.csv"})


class BulkBody(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=200)
    action: Literal["disable", "enable", "role"]
    role: Literal["jobseeker", "recruiter", "admin"] | None = None


@router.post("/users-bulk", dependencies=[Depends(require_csrf_header)])
async def users_bulk(body: BulkBody, me: dict = Depends(require_super_admin), db=Depends(db_dep)):
    if body.action == "role" and not body.role:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Pick a role")
    done, skipped = 0, 0
    for u in await db[c.USERS].find({"_id": {"$in": body.ids}}).to_list(length=None):
        if is_super_admin(u):
            skipped += 1
            continue
        patch = {"role": body.role} if body.action == "role" else {"is_active": body.action == "enable"}
        await db[c.USERS].update_one({"_id": u["_id"]}, {"$set": {**patch, "updated_at": utcnow()}})
        if body.action == "disable":
            await db[c.REFRESH_TOKENS].update_many({"user_id": u["_id"]}, {"$set": {"revoked": True, "family_revoked": True}})
        done += 1
    await log_action(db, user_id=me["_id"], action="superadmin.users_bulk", entity="user", details={"action": body.action, "role": body.role, "updated": done, "skipped": skipped})
    return {"updated": done, "skipped": skipped}


# ---------------------------------------------------------------- tags

@router.get("/tags")
async def all_tags(db=Depends(db_dep)):
    counts: dict[str, int] = {}
    for t in await db[c.USER_TAGS].find({}).to_list(length=None):
        for x in t.get("tags", []):
            counts[x] = counts.get(x, 0) + 1
    return {"tags": [{"name": k, "count": v} for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]}


class TagsBody(BaseModel):
    tags: list[str] = Field(max_length=10)


def clean_tags(tags: list[str]) -> list[str]:
    out: list[str] = []
    for t in tags:
        t = re.sub(r"[^\w\- ]", "", t.strip().lower())[:24].strip()
        if t and t not in out:
            out.append(t)
    return out


async def _target(db, user_id: str) -> dict:
    t = await db[c.USERS].find_one({"_id": user_id})
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return t


@router.put("/users/{user_id}/tags", dependencies=[Depends(require_csrf_header)])
async def set_tags(user_id: str, body: TagsBody, me: dict = Depends(require_super_admin), db=Depends(db_dep)):
    t = await _target(db, user_id)
    tags = clean_tags(body.tags)
    await db[c.USER_TAGS].update_one({"_id": user_id}, {"$set": {"user_id": user_id, "tags": tags, "updated_at": utcnow()}}, upsert=True)
    await log_action(db, user_id=me["_id"], action="superadmin.tags_set", entity="user", entity_id=user_id, details={"target_email": t["email"], "tags": tags})
    return {"tags": tags}


# ---------------------------------------------------------------- notes

class NoteBody(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


def _note(n: dict, authors: dict) -> dict:
    return {"id": n["_id"], "text": n["text"], "created_at": _iso(n.get("created_at")), "author": authors.get(n.get("author_id"), "former admin")}


@router.get("/users/{user_id}/notes")
async def list_notes(user_id: str, db=Depends(db_dep)):
    await _target(db, user_id)
    rows = await db[c.ADMIN_NOTES].find({"user_id": user_id}).sort("created_at", -1).limit(200).to_list(length=None)
    authors = {u["_id"]: u["email"] for u in await db[c.USERS].find({"_id": {"$in": list({n["author_id"] for n in rows})}}, {"email": 1}).to_list(length=None)}
    return {"items": [_note(n, authors) for n in rows]}


@router.post("/users/{user_id}/notes", status_code=201, dependencies=[Depends(require_csrf_header)])
async def add_note(user_id: str, body: NoteBody, me: dict = Depends(require_super_admin), db=Depends(db_dep)):
    t = await _target(db, user_id)
    doc = {"_id": new_id(), "user_id": user_id, "author_id": me["_id"], "text": body.text.strip(), "created_at": utcnow()}
    await db[c.ADMIN_NOTES].insert_one(doc)
    await log_action(db, user_id=me["_id"], action="superadmin.note_added", entity="user", entity_id=user_id, details={"target_email": t["email"]})
    return _note(doc, {me["_id"]: me["email"]})


@router.delete("/users/{user_id}/notes/{note_id}", status_code=204, dependencies=[Depends(require_csrf_header)])
async def delete_note(user_id: str, note_id: str, me: dict = Depends(require_super_admin), db=Depends(db_dep)):
    res = await db[c.ADMIN_NOTES].delete_one({"_id": note_id, "user_id": user_id})
    if not res.deleted_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    await log_action(db, user_id=me["_id"], action="superadmin.note_deleted", entity="user", entity_id=user_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- User 360

@router.get("/users/{user_id}")
async def user_detail(user_id: str, db=Depends(db_dep)):
    u = await _target(db, user_id)
    now = utcnow()
    roll = (await m.user_rollup(db, now)).get(user_id, {})
    sig = m.user_signals(u, roll, now)
    prof = await db[c.CANDIDATE_PROFILES].find_one({"user_id": user_id}, {"personal.current_designation": 1, "personal.current_location": 1,
                                                                         "personal.total_experience_years": 1, "personal.target_role": 1})
    per = (prof or {}).get("personal") or {}
    kinds = await db[c.RESUMES].aggregate([{"$match": {"user_id": user_id}}, {"$group": {"_id": "$kind", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}]).to_list(length=None)
    counts = {k: await db[coll].count_documents({"user_id": user_id}) for k, coll in (
        ("jobs_saved", c.JOBS), ("interviews", c.INTERVIEWS), ("agent_runs", c.AGENT_RUNS))}
    counts["agent_failures"] = await db[c.AGENT_RUNS].count_documents({"user_id": user_id, "status": "failed"})
    toks = await db[c.REFRESH_TOKENS].find({"user_id": user_id}, {"family_id": 1, "created_at": 1, "revoked": 1, "expires_at": 1, "platform": 1, "os": 1}) \
        .sort("created_at", -1).limit(300).to_list(length=None)
    fam: dict[str, dict] = {}
    for t in toks:
        f = fam.setdefault(t["family_id"], {"first_seen": t["created_at"], "last_seen": t["created_at"], "platform": t.get("platform") or "unknown",
                                            "os": t.get("os") or "unknown", "active": False})
        f["first_seen"] = min(as_utc(f["first_seen"]), as_utc(t["created_at"]))
        f["last_seen"] = max(as_utc(f["last_seen"]), as_utc(t["created_at"]))
        f["active"] = f["active"] or (not t.get("revoked") and as_utc(t["expires_at"]) > now)
    sessions = sorted(fam.values(), key=lambda x: x["last_seen"], reverse=True)[:12]
    return {
        "id": user_id, "email": u["email"], "name": u.get("name", ""), "role": effective_role(u), "is_super_admin": is_super_admin(u),
        "is_active": u.get("is_active", True), "created_at": _iso(u.get("created_at")), "last_active_at": _iso(sig["last_active"]),
        "source": _source(u), "lifecycle": sig["lifecycle"], "health": sig["health"], "health_label": sig["health_label"],
        "health_parts": {"idle_days": sig["idle_days"], "events_30d": sig["events_30d"], "features_30d": sig["features_30d"]},
        "profile": {"designation": per.get("current_designation"), "location": per.get("current_location"),
                    "experience_years": per.get("total_experience_years"), "target_role": per.get("target_role")},
        "kpis": {"resumes": roll.get("resumes", 0), "applications": roll.get("applications", 0), "emails_sent": roll.get("emails_sent", 0),
                 "replies": roll.get("replies", 0), **counts},
        "resumes_by_kind": [{"kind": k["_id"] or "unknown", "count": k["n"]} for k in kinds],
        "sessions": [{"first_seen": _iso(s["first_seen"]), "last_seen": _iso(s["last_seen"]), "platform": s["platform"], "os": s["os"], "active": s["active"]}
                     for s in sessions],
        "tags": (await db[c.USER_TAGS].find_one({"_id": user_id}) or {}).get("tags", []),
        "notes_count": await db[c.ADMIN_NOTES].count_documents({"user_id": user_id}),
    }


@router.get("/users/{user_id}/timeline")
async def user_timeline(user_id: str, kind: Literal["all", "audit", "login", "run"] = "all", days: int = Query(90, ge=1, le=366),
                        limit: int = Query(100, ge=1, le=300), db=Depends(db_dep)):
    await _target(db, user_id)
    since = utcnow() - timedelta(days=days)
    items = []
    if kind in ("all", "audit", "login"):
        q: dict = {"user_id": user_id, "timestamp": {"$gte": since}}
        if kind == "login":
            q["action"] = {"$regex": "^auth\\.login"}
        elif kind == "audit":
            q["action"] = {"$not": re.compile(r"^auth\.login")}
        for a in await db[c.AUDIT_LOGS].find(q, {"action": 1, "entity": 1, "timestamp": 1, "details.platform": 1}).sort("timestamp", -1).limit(limit).to_list(length=None):
            items.append({"at": _iso(a["timestamp"]), "kind": "login" if a["action"].startswith("auth.login") else "audit", "label": a["action"],
                          "entity": a.get("entity"), "platform": (a.get("details") or {}).get("platform")})
    if kind in ("all", "run"):
        for r in await db[c.AGENT_RUNS].find({"user_id": user_id, "start_time": {"$gte": since}}, {"agent_name": 1, "status": 1, "start_time": 1}) \
                .sort("start_time", -1).limit(limit).to_list(length=None):
            items.append({"at": _iso(r["start_time"]), "kind": "run", "label": r.get("agent_name") or "agent", "entity": r.get("status"), "platform": None})
    items.sort(key=lambda x: x["at"] or "", reverse=True)
    return {"items": items[:limit]}


@router.get("/users/{user_id}/applications")
async def user_applications(user_id: str, db=Depends(db_dep)):
    await _target(db, user_id)
    rows = await db[c.APPLICATIONS].find({"user_id": user_id}, {"company": 1, "role": 1, "status": 1, "source": 1, "match_score": 1, "applied_at": 1, "created_at": 1}) \
        .sort("created_at", -1).limit(100).to_list(length=None)
    return {"items": [{"id": a["_id"], "company": a.get("company"), "role": a.get("role"), "status": a.get("status"), "source": a.get("source"),
                       "match_score": a.get("match_score"), "applied_at": _iso(a.get("applied_at")), "created_at": _iso(a.get("created_at"))} for a in rows]}


@router.get("/users/{user_id}/emails")
async def user_emails(user_id: str, db=Depends(db_dep)):
    await _target(db, user_id)
    rows = await db[c.OUTREACH].find({"user_id": user_id, "status": {"$in": list(m.SENT_STATUSES)}}, {"subject": 1, "status": 1, "kind": 1, "sent_at": 1, "replied_at": 1}) \
        .sort("sent_at", -1).limit(100).to_list(length=None)
    return {"items": [{"id": o["_id"], "subject": o.get("subject"), "status": o.get("status"), "kind": o.get("kind"), "sent_at": _iso(o.get("sent_at")),
                       "replied_at": _iso(o.get("replied_at"))} for o in rows]}


# ---------------------------------------------------------------- account actions

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
    await log_action(db, user_id=me["_id"], action="superadmin.force_sign_out", entity="user", entity_id=user_id, details={"target_email": t["email"]})
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
    for coll in c.USER_SCOPED:  # same cascade as the user's own account deletion (includes admin notes and tags)
        await db[coll].delete_many({"user_id": user_id})
    await db[c.TALENT_REQUESTS].delete_many({"candidate_id": user_id})
    await db[c.USERS].delete_one({"_id": user_id})
    await log_action(db, user_id=me["_id"], action="superadmin.user_deleted", entity="user", entity_id=user_id, details={"target_email": t["email"]})
    return {"deleted": True}

"""Skill-gap learning path (/api/learning): skills your target roles and strong-match jobs ask for that your verified
profile lacks, ranked by how often they appear, each with free resources, estimated hours and a weekly plan. A skill only
enters the profile when the user explicitly confirms they have really learned or used it."""

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from pymongo import DESCENDING

from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.learning.catalog import ROLE_SKILLS, key_of, resources_for
from app.profiles.service import get_profile
from app.services.agent_runs import agent_run
from app.services.audit import log_action
from app.services.notify import notify
from app.utils import utcnow

router = APIRouter(prefix="/learning", tags=["learning"])
Status = Literal["todo", "in_progress", "done"]
MAX_SKILLS = 12


async def _doc(db: AsyncIOMotorDatabase, uid: str) -> dict:
    return await db[c.LEARNING_PATHS].find_one({"_id": uid}) or {"_id": uid, "user_id": uid, "skills": [], "hours_per_week": 6}


async def _save(db: AsyncIOMotorDatabase, doc: dict) -> None:
    doc["updated_at"] = utcnow()
    await db[c.LEARNING_PATHS].replace_one({"_id": doc["_id"]}, doc, upsert=True)


def _progress_entry(doc: dict, key: str) -> dict:
    hit = next((s for s in doc["skills"] if s["key"] == key), None)
    if not hit:
        hit = {"key": key, "status": "todo", "done": [], "confirmed": False}
        doc["skills"].append(hit)
    return hit


async def compute_gaps(db: AsyncIOMotorDatabase, uid: str) -> list[dict]:
    profile = await get_profile(db, uid)
    have = {key_of(s) for s in profile.skills.all()}
    score: dict[str, dict] = {}

    def add(skill: str, weight: int, job: bool) -> None:
        k = key_of(skill)
        if not k or k in have:
            return
        row = score.setdefault(k, {"key": k, "name": skill.strip(), "score": 0, "jobs": 0, "from_roles": False})
        row["score"] += weight
        if job:
            row["jobs"] += 1
        else:
            row["from_roles"] = True

    jobs = await db[c.JOBS].find({"user_id": uid, "match.overall": {"$gte": 50}},
                                 {"match.missing_required_skills": 1, "match.missing_preferred_skills": 1}).sort("created_at", DESCENDING).to_list(80)
    for j in jobs:
        m = j.get("match") or {}
        for s in m.get("missing_required_skills") or []:
            add(s, 2, True)
        for s in m.get("missing_preferred_skills") or []:
            add(s, 1, True)
    roles = " ".join(getattr(profile.preferences, "target_roles", None) or []).lower()
    for needle, skills in ROLE_SKILLS.items():
        if needle in roles:
            for s in skills:
                add(s, 1, False)
    return sorted(score.values(), key=lambda r: (-r["score"], r["name"].lower()))[:MAX_SKILLS]


def weekly_plan(skills: list[dict], hours_per_week: int) -> list[dict]:
    week_start = utcnow() - timedelta(days=utcnow().weekday())
    weeks: list[dict] = []
    week, left = 0, hours_per_week
    for s in skills:
        if s["status"] == "done":
            continue
        remaining = max(1, round(s["hours"] * (100 - s["progress"]) / 100))
        while remaining > 0:
            if left == 0:
                week, left = week + 1, hours_per_week
            take = min(left, remaining)
            while len(weeks) <= week:
                weeks.append({"week": len(weeks) + 1, "start": (week_start + timedelta(weeks=len(weeks))).date().isoformat(), "items": []})
            items = weeks[week]["items"]
            if items and items[-1]["key"] == s["key"]:
                items[-1]["hours"] += take
            else:
                items.append({"key": s["key"], "skill": s["name"], "hours": take})
            remaining -= take
            left -= take
        if len(weeks) >= 16:
            break
    return weeks[:16]


async def view(db: AsyncIOMotorDatabase, uid: str) -> dict:
    doc = await _doc(db, uid)
    gaps = await compute_gaps(db, uid)
    keys = {g["key"] for g in gaps}
    # keep skills the user is already working on even if a job disappeared
    for p in doc["skills"]:
        if p["key"] not in keys and (p["status"] != "todo" or p["done"]) and not p.get("confirmed"):
            gaps.append({"key": p["key"], "name": p.get("name") or p["key"], "score": 0, "jobs": 0, "from_roles": False})
    out = []
    for g in gaps:
        p = next((x for x in doc["skills"] if x["key"] == g["key"]), {"status": "todo", "done": []})
        res, hours = resources_for(g["name"])
        done_ids = set(p.get("done") or [])
        pct = 100 if p["status"] == "done" else round(100 * len(done_ids & {r["id"] for r in res}) / len(res)) if res else 0
        out.append({**g, "hours": hours, "status": p["status"], "progress": pct, "confirmed": bool(p.get("confirmed")),
                    "resources": [{**r, "done": r["id"] in done_ids} for r in res]})
    hpw = int(doc.get("hours_per_week") or 6)
    return {"skills": out, "hours_per_week": hpw, "plan": weekly_plan(out, hpw),
            "summary": {"total": len(out), "in_progress": sum(s["status"] == "in_progress" for s in out),
                        "done": sum(s["status"] == "done" for s in out),
                        "hours_left": sum(round(s["hours"] * (100 - s["progress"]) / 100) for s in out)}}


async def summary(db: AsyncIOMotorDatabase, uid: str) -> dict:
    """Small summary for Goals (from stored progress only; no gap computation)."""
    doc = await db[c.LEARNING_PATHS].find_one({"_id": uid}) or {}
    rows = doc.get("skills") or []
    return {"in_progress": sum(r["status"] == "in_progress" for r in rows), "done": sum(r["status"] == "done" for r in rows),
            "confirmed": sum(bool(r.get("confirmed")) for r in rows)}


@router.get("")
async def get_path(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await view(db, user["_id"])


@router.post("/refresh")
async def refresh(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    async with agent_run(db, "learning_path", uid, {}) as run:
        out = await view(db, uid)
        run.output = {"skills": len(out["skills"])}
    await log_action(db, user_id=uid, action="learning.refreshed", entity="learning_path", details={"skills": len(out["skills"])})
    return out


class SkillStatusIn(BaseModel):
    status: Status
    name: str | None = Field(None, max_length=60)


@router.put("/skills/{key}")
async def set_skill(key: str, body: SkillStatusIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    doc = await _doc(db, uid)
    p = _progress_entry(doc, key_of(key))
    p["status"] = body.status
    if body.name:
        p["name"] = body.name
    await _save(db, doc)
    await log_action(db, user_id=uid, action="learning.skill_status", entity="learning_path", details={"skill": key, "status": body.status})
    if body.status == "done":
        await notify(db, user_id=uid, kind="learning", title=f"Skill finished: {body.name or key}",
                     body="If you have really learned or used it, confirm it to add it to your profile.", link="/learning")
    return await view(db, uid)


class ResourceIn(BaseModel):
    skill: str = Field(min_length=1, max_length=60)
    resource_id: str = Field(min_length=1, max_length=8)
    done: bool
    name: str | None = Field(None, max_length=60)


@router.put("/resources")
async def set_resource(body: ResourceIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    doc = await _doc(db, uid)
    p = _progress_entry(doc, key_of(body.skill))
    done = set(p["done"])
    done.add(body.resource_id) if body.done else done.discard(body.resource_id)
    p["done"] = sorted(done)
    if body.name:
        p["name"] = body.name
    if p["status"] == "todo" and done:
        p["status"] = "in_progress"
    await _save(db, doc)
    await log_action(db, user_id=uid, action="learning.resource", entity="learning_path",
                     details={"skill": body.skill, "resource": body.resource_id, "done": body.done})
    return await view(db, uid)


class SettingsIn(BaseModel):
    hours_per_week: int = Field(ge=1, le=40)


@router.put("/settings")
async def set_settings(body: SettingsIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    doc = await _doc(db, user["_id"])
    doc["hours_per_week"] = body.hours_per_week
    await _save(db, doc)
    return await view(db, user["_id"])


class ConfirmIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    confirmed: bool  # "I have really learned/used it" must be ticked


@router.post("/skills/{key}/confirm")
async def confirm_skill(key: str, body: ConfirmIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Adds the skill to the verified profile only after the user's explicit confirmation (same path as studio SkillConfirm)."""
    if not body.confirmed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tick 'I have really learned or used it' to add this skill to your profile.")
    from app.profiles.service import update_profile
    from app.schemas.profile import ProfileUpdate

    uid = user["_id"]
    profile = await get_profile(db, uid)
    name = body.name.strip()
    added = []
    if key_of(name) not in {key_of(s) for s in profile.skills.all()}:
        await update_profile(db, uid, ProfileUpdate.model_validate({"skills": {"secondary": profile.skills.secondary + [name]}}), source="user")
        added = [name]
    doc = await _doc(db, uid)
    p = _progress_entry(doc, key_of(key))
    p.update(status="done", confirmed=True, name=name)
    await _save(db, doc)
    await log_action(db, user_id=uid, action="learning.skill_confirmed", entity="profile", details={"skill": name, "added": bool(added)})
    await notify(db, user_id=uid, kind="learning", title=f"{name} added to your profile", body="Confirmed by you after your learning path.",
                 link="/profile")
    return {"added": added}

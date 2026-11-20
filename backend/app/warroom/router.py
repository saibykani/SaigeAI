"""Interview War Room (/api/war-room): one calm page to prep right before an interview.

Reuses the interview brief (applications/brief.py): JD requirements, generated questions and the stories matched from the
verified profile. Adds the user's question bank, a per-interview persisted checklist and links. Stories come only from the
verified master profile and pass the truth guard; when nothing matches the story is the literal string UNKNOWN."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.applications.brief import CHECKLIST, build_brief
from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.profiles.service import get_profile
from app.services.agent_runs import agent_run
from app.services.audit import log_action
from app.services.skills_vocab import normalize_key
from app.services.truth_guard import GeneratedClaims, validate_claims
from app.utils import new_id, utcnow

router = APIRouter(prefix="/war-room", tags=["war-room"])

UNKNOWN = "UNKNOWN"
PREP_WINDOW_DAYS = 14


class ChecklistPatch(BaseModel):
    item_id: str | None = None
    done: bool | None = None
    add: str | None = Field(default=None, max_length=200)
    remove: str | None = None


def _default_items() -> list[dict]:
    return [{"id": f"c{n + 1}", "text": t, "done": False, "custom": False} for n, t in enumerate(CHECKLIST)]


async def _interview(db: AsyncIOMotorDatabase, uid: str, interview_id: str) -> dict:
    i = await db[c.INTERVIEWS].find_one({"_id": interview_id, "user_id": uid})
    if not i:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    return i


async def _room(db: AsyncIOMotorDatabase, uid: str, interview_id: str) -> dict:
    room = await db[c.WAR_ROOMS].find_one({"user_id": uid, "interview_id": interview_id})
    if not room:
        room = {"_id": new_id(), "user_id": uid, "interview_id": interview_id, "items": _default_items(), "created_at": utcnow()}
        await db[c.WAR_ROOMS].insert_one(room)
    return room


def _truthful(stories: list[dict], profile) -> list[dict]:
    """Keep only stories whose declared skills/projects the truth guard accepts."""
    ok = []
    for s in stories:
        claims = GeneratedClaims(text=s.get("line") or "", skills=s.get("skills") or [],
                                 projects=[s["name"]] if s["kind"] == "project" else [])
        if validate_claims(claims, profile).passed:
            ok.append(s)
    return ok


def _story_for(q: dict, stories: list[dict]) -> dict:
    skill = normalize_key(q.get("skill") or "")
    hit = next((s for s in stories if skill and skill in {normalize_key(x) for x in s["skills"]}), None)
    if not hit and q.get("kind") in ("behavioural", "hr") and stories:
        hit = stories[0]
    if not hit:
        return {"name": None, "line": UNKNOWN}
    return {"name": hit["name"], "line": hit["line"] or UNKNOWN}


async def _bank_questions(db: AsyncIOMotorDatabase, uid: str, company: str | None, skills: list[str]) -> list[dict]:
    want = {normalize_key(s) for s in skills}
    out = []
    async for b in db[c.QUESTION_BANK].find({"user_id": uid}).sort("updated_at", -1).limit(200):
        same_co = bool(company) and company.lower() in [x.lower() for x in b.get("companies", [])]
        overlap = [s for s in b.get("skills", []) if normalize_key(s) in want]
        if same_co or overlap:
            out.append({"text": b["text"], "kind": "question_bank", "skill": (overlap or [None])[0]})
    return out[:6]


def _out_room(room: dict) -> dict:
    items = room["items"]
    return {"items": items, "done": sum(1 for x in items if x["done"]), "total": len(items)}


@router.get("")
async def list_war_rooms(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Upcoming interviews (next 14 days plus anything that started in the last 3 hours) with checklist progress."""
    uid = user["_id"]
    now = utcnow()
    docs = await db[c.INTERVIEWS].find({"user_id": uid, "status": {"$in": ["upcoming", "rescheduled"]},
                                        "scheduled_at": {"$gte": now - timedelta(hours=3), "$lte": now + timedelta(days=PREP_WINDOW_DAYS)}}
                                       ).sort("scheduled_at", 1).to_list(50)
    out = []
    for i in docs:
        room = await db[c.WAR_ROOMS].find_one({"user_id": uid, "interview_id": i["_id"]})
        items = room["items"] if room else _default_items()
        out.append({"interview_id": i["_id"], "company": i.get("company"), "role": i.get("role"), "round": i.get("round"),
                    "scheduled_at": i["scheduled_at"].isoformat(), "meeting_url": i.get("meeting_url"),
                    "checklist_done": sum(1 for x in items if x["done"]), "checklist_total": len(items)})
    return {"interviews": out}


@router.get("/{interview_id}")
async def war_room(interview_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    i = await _interview(db, uid, interview_id)
    app_doc = await db[c.APPLICATIONS].find_one({"_id": i["application_id"], "user_id": uid}) if i.get("application_id") else None
    async with agent_run(db, "war_room", uid, {"interview_id": interview_id}) as run:
        profile = await get_profile(db, uid)
        brief = await build_brief(db, uid, company=i.get("company"), role=i.get("role"), scheduled_at=i["scheduled_at"].isoformat(),
                                  meeting_url=i.get("meeting_url"), round_=i.get("round"), app_doc=app_doc, source={})
        stories = _truthful(brief["matching"], profile)
        bank = await _bank_questions(db, uid, i.get("company"), brief["skills"])
        seen: set[str] = set()
        questions = []
        for q in [*brief["questions"], *bank]:
            if q["text"] in seen:
                continue
            seen.add(q["text"])
            questions.append({**q, "story": _story_for(q, stories)})
        room = await _room(db, uid, interview_id)
        requirements = [{"text": r, "evidence": next((s["name"] for s in stories if any(k.lower() in r.lower() for k in s["skills"])), None)}
                        for r in brief["requirements"]]
        run.action(f"Built war room for {i.get('company')}: {len(questions)} questions, {len(stories)} stories")
        run.output = {"questions": len(questions), "stories": len(stories)}
    return {
        "interview_id": interview_id, "company": i.get("company"), "role": i.get("role"), "round": i.get("round"),
        "scheduled_at": i["scheduled_at"].isoformat(), "duration_minutes": i.get("duration_minutes", 60),
        "interviewer": i.get("interviewer"), "has_job": brief["has_job"],
        "links": {"join": i.get("meeting_url"), "ics": f"/api/interviews/{interview_id}.ics"},
        "skills": brief["skills"], "brush_up": brief["brush_up"],
        "requirements": requirements, "questions": questions, "stories": stories, "stories_note": None if stories else UNKNOWN,
        "checklist": _out_room(room),
    }


@router.patch("/{interview_id}/checklist")
async def patch_checklist(interview_id: str, body: ChecklistPatch, user: dict = Depends(get_current_user),
                          db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    await _interview(db, uid, interview_id)
    room = await _room(db, uid, interview_id)
    items = room["items"]
    if body.add and body.add.strip():
        items.append({"id": new_id()[:8], "text": body.add.strip(), "done": False, "custom": True})
    elif body.remove:
        if not any(x["id"] == body.remove and x.get("custom") for x in items):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Custom checklist item not found")
        items = [x for x in items if x["id"] != body.remove]
    elif body.item_id and body.done is not None:
        target = next((x for x in items if x["id"] == body.item_id), None)
        if not target:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Checklist item not found")
        target["done"] = body.done
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Provide item_id+done, add or remove")
    await db[c.WAR_ROOMS].update_one({"_id": room["_id"]}, {"$set": {"items": items, "updated_at": utcnow()}})
    await log_action(db, user_id=uid, action="war_room.checklist", entity="interview", entity_id=interview_id,
                     details={"done": sum(1 for x in items if x["done"]), "total": len(items)})
    return _out_room({**room, "items": items})

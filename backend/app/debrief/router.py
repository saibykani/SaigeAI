"""Interview debrief (/api/debriefs, /api/question-bank): spoken or typed notes -> structured notes, question bank, thank-you draft.

Extraction is deterministic and uses only the user's own text. The thank-you email is a draft; sending needs an explicit
approval flag, a connected Gmail and `automation.is_allowed("emails")`."""

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.auth.deps import db_dep, get_current_user
from app.automation.service import is_allowed
from app.database import collections as c
from app.debrief import extract as ex
from app.email import outbound
from app.email.gmail import GmailError
from app.services.agent_runs import agent_run
from app.services.audit import log_action
from app.services.notify import notify
from app.services.skills_vocab import find_skills
from app.utils import new_id, utcnow

router = APIRouter(tags=["debrief"])


class DebriefIn(BaseModel):
    interview_id: str | None = None
    application_id: str | None = None
    company: str | None = Field(default=None, max_length=200)
    role: str | None = Field(default=None, max_length=200)
    round: str | None = Field(default=None, max_length=100)
    text: str = Field(min_length=10, max_length=20000)
    date: str | None = None


class DraftUpdate(BaseModel):
    subject: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, max_length=5000)
    to: str | None = Field(default=None, max_length=200)


class SendIn(BaseModel):
    to: str = Field(min_length=3, max_length=200)
    approved: bool = False
    subject: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, max_length=5000)


def out(d: dict) -> dict:
    ty = dict(d["thank_you"])
    if isinstance(ty.get("sent_at"), datetime):
        ty["sent_at"] = ty["sent_at"].isoformat()
    return {"id": d["_id"], "interview_id": d.get("interview_id"), "application_id": d.get("application_id"),
            "company": d["company"], "role": d["role"], "round": d.get("round"), "date": d.get("date"), "text": d["text"],
            "questions": d["questions"], "skills": d["skills"], "went_well": d["went_well"], "to_improve": d["to_improve"],
            "next_steps": d["next_steps"], "dates": d["dates"], "interviewers": d["interviewers"],
            "thank_you": ty, "created_at": d["created_at"].isoformat()}


async def _owned(db: AsyncIOMotorDatabase, uid: str, debrief_id: str) -> dict:
    d = await db[c.DEBRIEFS].find_one({"_id": debrief_id, "user_id": uid})
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Debrief not found")
    return d


@router.post("/debriefs", status_code=201)
async def create_debrief(body: DebriefIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    iv = await db[c.INTERVIEWS].find_one({"_id": body.interview_id, "user_id": uid}) if body.interview_id else None
    if body.interview_id and not iv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    app_id = body.application_id or (iv or {}).get("application_id")
    a = await db[c.APPLICATIONS].find_one({"_id": app_id, "user_id": uid}) if app_id else None
    if body.application_id and not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    company = (body.company or (iv or {}).get("company") or (a or {}).get("company") or "").strip()
    role = (body.role or (iv or {}).get("role") or (a or {}).get("role") or "").strip()
    if not company or not role:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Pick an interview or application, or enter company and role.")
    round_ = body.round or (iv or {}).get("round")
    sched = (iv or {}).get("scheduled_at")
    date = body.date or (sched.date().isoformat() if isinstance(sched, datetime) else None) or utcnow().date().isoformat()
    async with agent_run(db, "interview_debrief", uid, {"company": company, "role": role}) as run:
        data = ex.extract(body.text)
        now = utcnow()
        doc = {"_id": new_id(), "user_id": uid, "interview_id": body.interview_id, "application_id": app_id, "company": company,
               "role": role, "round": round_, "date": date, "text": body.text, **data,
               "thank_you": ex.thank_you(user.get("name") or "", company, role, data), "created_at": now}
        await db[c.DEBRIEFS].insert_one(doc)
        added = 0
        for q in data["questions"]:
            key = ex.question_key(q)
            res = await db[c.QUESTION_BANK].update_one(
                {"user_id": uid, "key": key},
                {"$setOnInsert": {"_id": new_id(), "user_id": uid, "key": key, "text": q, "created_at": now},
                 "$addToSet": {"companies": company, "rounds": round_ or "", "debrief_ids": doc["_id"]},
                 "$set": {"skills": find_skills(q), "updated_at": now}}, upsert=True)
            added += 1 if res.upserted_id else 0
        run.output = {"debrief_id": doc["_id"], "questions": len(data["questions"]), "new_in_bank": added}
    await log_action(db, user_id=uid, action="debrief.create", entity="debrief", entity_id=doc["_id"],
                     details={"company": company, "questions": len(data["questions"])})
    await notify(db, user_id=uid, kind="debrief_ready", title=f"Debrief saved: {role} at {company}",
                 body=f"{len(data['questions'])} questions added to your question bank. A thank-you draft is ready to review.",
                 link="/debrief")
    return out(doc)


@router.get("/debriefs")
async def list_debriefs(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    docs = await db[c.DEBRIEFS].find({"user_id": user["_id"]}).sort("created_at", -1).to_list(200)
    return [out(d) for d in docs]


@router.get("/debriefs/{debrief_id}")
async def get_debrief(debrief_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return out(await _owned(db, user["_id"], debrief_id))


@router.delete("/debriefs/{debrief_id}", status_code=204)
async def delete_debrief(debrief_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    await _owned(db, uid, debrief_id)
    await db[c.DEBRIEFS].delete_one({"_id": debrief_id, "user_id": uid})
    await db[c.QUESTION_BANK].update_many({"user_id": uid}, {"$pull": {"debrief_ids": debrief_id}})
    await db[c.QUESTION_BANK].delete_many({"user_id": uid, "debrief_ids": {"$size": 0}})
    await log_action(db, user_id=uid, action="debrief.delete", entity="debrief", entity_id=debrief_id)


@router.patch("/debriefs/{debrief_id}/thank-you")
async def edit_draft(debrief_id: str, body: DraftUpdate, user: dict = Depends(get_current_user),
                     db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    d = await _owned(db, uid, debrief_id)
    if d["thank_you"].get("status") == "sent":
        raise HTTPException(status.HTTP_409_CONFLICT, "Already sent")
    upd = {f"thank_you.{k}": v for k, v in body.model_dump(exclude_none=True).items()}
    if upd:
        await db[c.DEBRIEFS].update_one({"_id": debrief_id}, {"$set": upd})
    return out(await _owned(db, uid, debrief_id))


@router.post("/debriefs/{debrief_id}/thank-you/send")
async def send_thank_you(debrief_id: str, body: SendIn, user: dict = Depends(get_current_user),
                         db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    d = await _owned(db, uid, debrief_id)
    if not body.approved:
        raise HTTPException(status.HTTP_409_CONFLICT, "USER_APPROVAL_REQUIRED: confirm you approve sending this email.")
    if d["thank_you"].get("status") == "sent":
        raise HTTPException(status.HTTP_409_CONFLICT, "This thank-you was already sent.")
    if not await is_allowed(db, uid, "emails"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email sending is paused in Automation settings.")
    integ = await outbound.find_sender(db, uid)
    if not integ:
        raise HTTPException(status.HTTP_409_CONFLICT, "Connect Gmail in Integrations to send, or copy the draft and send it yourself.")
    subject = body.subject or d["thank_you"]["subject"]
    text = body.body or d["thank_you"]["body"]
    try:
        mid = await outbound.send(integ, user.get("name") or "", body.to.strip(), subject, text)
    except GmailError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    await db[c.DEBRIEFS].update_one({"_id": debrief_id}, {"$set": {
        "thank_you.status": "sent", "thank_you.to": body.to.strip(), "thank_you.subject": subject, "thank_you.body": text,
        "thank_you.sent_at": utcnow(), "thank_you.message_id": mid}})
    await log_action(db, user_id=uid, action="debrief.thank_you_sent", entity="debrief", entity_id=debrief_id,
                     details={"company": d["company"], "approved": True})
    await notify(db, user_id=uid, kind="debrief_thank_you_sent", title=f"Thank-you sent to {body.to.strip()}",
                 body=f"{d['role']} at {d['company']}", link="/debrief")
    return out(await _owned(db, uid, debrief_id))


@router.get("/question-bank")
async def question_bank(company: str | None = Query(default=None), skill: str | None = Query(default=None),
                        q: str | None = Query(default=None), user: dict = Depends(get_current_user),
                        db: AsyncIOMotorDatabase = Depends(db_dep)):
    docs = await db[c.QUESTION_BANK].find({"user_id": user["_id"]}).sort("updated_at", -1).to_list(1000)
    items = [{"id": d["_id"], "text": d["text"], "companies": [x for x in d.get("companies", []) if x],
              "rounds": [x for x in d.get("rounds", []) if x], "skills": d.get("skills", []),
              "count": len(d.get("debrief_ids", []))} for d in docs]
    companies = sorted({x for i in items for x in i["companies"]})
    skills = sorted({x for i in items for x in i["skills"]})
    if company:
        items = [i for i in items if any(company.lower() == x.lower() for x in i["companies"])]
    if skill:
        items = [i for i in items if any(skill.lower() == x.lower() for x in i["skills"])]
    if q:
        items = [i for i in items if re.search(re.escape(q), i["text"], re.I)]
    return {"items": items, "companies": companies, "skills": skills}

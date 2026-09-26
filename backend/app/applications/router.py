from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from app.applications import service as svc
from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.schemas.application import (
    AnswerEdit,
    ApplicationCreate,
    InterviewIn,
    InterviewUpdate,
    QuestionsIn,
    StatusUpdate,
)
from app.services.audit import log_action
from app.services.notify import notify
from app.utils import as_utc, new_id, utcnow

router = APIRouter(tags=["applications"])


@router.get("/applications")
async def list_applications(status_: str | None = Query(None, alias="status"), user: dict = Depends(get_current_user),
                            db: AsyncIOMotorDatabase = Depends(db_dep)):
    q: dict = {"user_id": user["_id"]}
    if status_:
        q["status"] = status_
    docs = await db[c.APPLICATIONS].find(q).sort("updated_at", DESCENDING).to_list(500)
    return [svc.app_out(a) for a in docs]


@router.post("/applications", status_code=201)
async def create_application(body: ApplicationCreate, user: dict = Depends(get_current_user),
                             db: AsyncIOMotorDatabase = Depends(db_dep)):
    return svc.app_out(await svc.create(db, user["_id"], body.job_id, body.resume_id, body.cover_letter_id))


@router.get("/applications/{app_id}")
async def get_application(app_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    a = await svc.get_owned(db, user["_id"], app_id)
    events = await db[c.APPLICATION_EVENTS].find({"application_id": app_id}).sort("at", ASCENDING).to_list(500)
    answers = await db[c.APPLICATION_ANSWERS].find({"application_id": app_id}).sort("created_at", ASCENDING).to_list(200)
    followups = await db[c.FOLLOWUPS].find({"application_id": app_id}).sort("due_at", ASCENDING).to_list(20)
    interviews = await db[c.INTERVIEWS].find({"application_id": app_id}).sort("scheduled_at", ASCENDING).to_list(50)
    return {
        **svc.app_out(a),
        "events": [{"id": e["_id"], "type": e["type"], "note": e.get("note"), "from": e.get("from"), "to": e.get("to"),
                    "source": e.get("source"), "email_id": e.get("email_id"), "at": e["at"].isoformat()} for e in events],
        "answers": [svc.answer_out(x) for x in answers],
        "followups": [{"id": f["_id"], "kind": f["kind"], "sequence": f["sequence"], "status": f["status"],
                       "due_at": f["due_at"].isoformat()} for f in followups],
        "interviews": [interview_out(i) for i in interviews],
    }


@router.post("/applications/{app_id}/prepare")
async def prepare(app_id: str, body: QuestionsIn, user: dict = Depends(get_current_user),
                  db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Answer the employer's application questions from the verified knowledge base."""
    a = await svc.get_owned(db, user["_id"], app_id)
    return [svc.answer_out(x) for x in await svc.answer_questions(db, a, body.questions)]


@router.put("/applications/{app_id}/answers/{answer_id}")
async def edit_answer(app_id: str, answer_id: str, body: AnswerEdit, user: dict = Depends(get_current_user),
                      db: AsyncIOMotorDatabase = Depends(db_dep)):
    a = await svc.get_owned(db, user["_id"], app_id)
    res = await db[c.APPLICATION_ANSWERS].update_one(
        {"_id": answer_id, "application_id": app_id},
        {"$set": {"answer": body.answer, "status": "USER_PROVIDED", "source": "Provided by you",
                  "confidence": "HIGH", "updated_at": utcnow()}})
    if not res.matched_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Answer not found")
    remaining = await db[c.APPLICATION_ANSWERS].count_documents({"application_id": app_id, "status": "REVIEW_REQUIRED"})
    if not remaining and a["status"] == "APPROVAL_REQUIRED":
        await svc.set_status(db, a, "READY_TO_APPLY", note="All answers reviewed", source="system")
    return svc.answer_out(await db[c.APPLICATION_ANSWERS].find_one({"_id": answer_id}))


@router.post("/applications/{app_id}/approve")
async def approve(app_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    a = await svc.get_owned(db, user["_id"], app_id)
    if a["status"] not in {"READY_TO_APPLY", "APPROVAL_REQUIRED", "SHORTLISTED", "APPLICATION_FAILED"}:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot apply from status {a['status']}")
    return await svc.approve_and_apply(db, user["_id"], a)


@router.post("/applications/{app_id}/mark-applied")
async def mark_applied(app_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    a = await svc.get_owned(db, user["_id"], app_id)
    return svc.app_out(await svc.mark_applied(db, a))


@router.post("/applications/{app_id}/reject")
async def reject(app_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """User declines to apply (spec 47 'reject'): the application is withdrawn."""
    a = await svc.get_owned(db, user["_id"], app_id)
    await db[c.FOLLOWUPS].update_many({"application_id": app_id, "status": "scheduled"}, {"$set": {"status": "cancelled"}})
    return svc.app_out(await svc.set_status(db, a, "WITHDRAWN", note="Withdrawn by user"))


@router.post("/applications/{app_id}/status")
async def update_status(app_id: str, body: StatusUpdate, user: dict = Depends(get_current_user),
                        db: AsyncIOMotorDatabase = Depends(db_dep)):
    a = await svc.get_owned(db, user["_id"], app_id)
    if body.status == "APPLIED":
        return svc.app_out(await svc.mark_applied(db, a))
    if body.status in {"REJECTED", "WITHDRAWN", "CLOSED", "OFFER"}:
        await db[c.FOLLOWUPS].update_many({"application_id": app_id, "status": "scheduled"},
                                          {"$set": {"status": "cancelled"}})
    a = await svc.set_status(db, a, body.status, note=body.note)
    if body.status in {"REJECTED", "OFFER"}:
        await notify(db, user_id=user["_id"], kind=body.status.lower(),
                     title=f"{'Offer received' if body.status == 'OFFER' else 'Rejection'}: {a['role']} at {a['company']}",
                     link=f"/applications/{app_id}")
    return svc.app_out(a)


@router.delete("/applications/{app_id}", status_code=204)
async def delete_application(app_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    await svc.get_owned(db, user["_id"], app_id)
    for coll in (c.APPLICATION_EVENTS, c.APPLICATION_ANSWERS, c.FOLLOWUPS):
        await db[coll].delete_many({"application_id": app_id})
    await db[c.APPLICATIONS].delete_one({"_id": app_id})
    await log_action(db, user_id=user["_id"], action="application.deleted", entity="application", entity_id=app_id)
    return Response(status_code=204)


# ------------------------------------------------------------------ interviews (spec 23)

def _parse_dt(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "scheduled_at must be an ISO 8601 datetime") from exc


def interview_out(i: dict) -> dict:
    return {"id": i["_id"], "application_id": i.get("application_id"), "company": i.get("company"),
            "role": i.get("role"), "round": i.get("round"), "scheduled_at": i["scheduled_at"].isoformat(),
            "timezone": i.get("timezone"), "duration_minutes": i.get("duration_minutes", 60),
            "meeting_url": i.get("meeting_url"), "interviewer": i.get("interviewer"),
            "interview_type": i.get("interview_type"), "status": i["status"], "notes": i.get("notes"),
            "source": i.get("source", "user"), "created_at": i["created_at"].isoformat()}


@router.get("/interviews")
async def list_interviews(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    docs = await db[c.INTERVIEWS].find({"user_id": user["_id"]}).sort("scheduled_at", ASCENDING).to_list(500)
    grouped: dict[str, list] = {"upcoming": [], "completed": [], "rescheduled": [], "cancelled": []}
    for i in docs:
        grouped.setdefault(i["status"], []).append(interview_out(i))
    return grouped


@router.post("/interviews", status_code=201)
async def create_interview(body: InterviewIn, user: dict = Depends(get_current_user),
                           db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    a = await svc.get_owned(db, uid, body.application_id) if body.application_id else None
    if not a and not (body.company and body.role):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Provide an application or company and role")
    now = utcnow()
    doc = {"_id": new_id(), "user_id": uid, **body.model_dump(exclude={"scheduled_at"}),
           "company": body.company or a["company"], "role": body.role or a["role"],
           "scheduled_at": _parse_dt(body.scheduled_at), "source": "user", "created_at": now, "updated_at": now}
    await db[c.INTERVIEWS].insert_one(doc)
    if a:
        await svc.set_status(db, a, "INTERVIEW_SCHEDULED", note=f"Interview scheduled: {body.round or 'round'}",
                             extra={"interview_id": doc["_id"], "last_contact_at": now})
    await notify(db, user_id=uid, kind="interview_scheduled", title=f"Interview scheduled: {doc['role']} at {doc['company']}",
                 link="/interviews")
    return interview_out(doc)


@router.patch("/interviews/{interview_id}")
async def update_interview(interview_id: str, body: InterviewUpdate, user: dict = Depends(get_current_user),
                           db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    i = await db[c.INTERVIEWS].find_one({"_id": interview_id, "user_id": uid})
    if not i:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    patch = body.model_dump(exclude_unset=True)
    if "scheduled_at" in patch and patch["scheduled_at"]:
        patch["scheduled_at"] = _parse_dt(patch["scheduled_at"])
        if i["status"] == "upcoming" and "status" not in patch:
            patch["status"] = "rescheduled"
    await db[c.INTERVIEWS].update_one({"_id": interview_id}, {"$set": {**patch, "updated_at": utcnow()}})
    await db[c.INTERVIEW_EVENTS].insert_one({"_id": new_id(), "user_id": uid, "interview_id": interview_id,
                                             "change": {k: str(v) for k, v in patch.items()}, "at": utcnow()})
    if patch.get("status") == "completed" and i.get("application_id"):
        a = await svc.get_owned(db, uid, i["application_id"])
        await svc.set_status(db, a, "INTERVIEW_COMPLETED", note="Interview completed")
    if patch.get("status") == "rescheduled":
        await notify(db, user_id=uid, kind="interview_rescheduled", title=f"Interview rescheduled: {i['role']}",
                     link="/interviews")
    return interview_out(await db[c.INTERVIEWS].find_one({"_id": interview_id}))


def _ics_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


@router.get("/interviews/{interview_id}.ics")
async def interview_ics(interview_id: str, user: dict = Depends(get_current_user),
                        db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Calendar file for Google Calendar / Outlook / Apple Calendar - no calendar write access needed."""
    i = await db[c.INTERVIEWS].find_one({"_id": interview_id, "user_id": user["_id"]})
    if not i:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    start = as_utc(i["scheduled_at"])
    end = start + timedelta(minutes=i.get("duration_minutes", 60))
    fmt = "%Y%m%dT%H%M%SZ"
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Saige AI//Interviews//EN", "BEGIN:VEVENT",
        f"UID:{i['_id']}@saige.ai", f"DTSTAMP:{utcnow().strftime(fmt)}",
        f"DTSTART:{start.strftime(fmt)}", f"DTEND:{end.strftime(fmt)}",
        "SUMMARY:" + _ics_escape(f"Interview: {i.get('role')} at {i.get('company')}"),
    ]
    if i.get("meeting_url"):
        lines += [f"LOCATION:{_ics_escape(i['meeting_url'])}", f"URL:{i['meeting_url']}"]
    if i.get("round"):
        lines.append(f"DESCRIPTION:{_ics_escape(i['round'])}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return Response(content="\r\n".join(lines) + "\r\n", media_type="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="interview-{interview_id}.ics"'})


@router.delete("/interviews/{interview_id}", status_code=204)
async def delete_interview(interview_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    res = await db[c.INTERVIEWS].delete_one({"_id": interview_id, "user_id": user["_id"]})
    if not res.deleted_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    return Response(status_code=204)

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.recruiters import service as svc
from app.schemas.recruiter import ContactIn, ContactUpdate, CsvImport, DraftIn, OutreachEdit, OutreachStatus

router = APIRouter(tags=["recruiters"])


# ------------------------------------------------------------------ contacts

@router.get("/recruiters")
async def list_contacts(q: str | None = Query(None, max_length=100), company: str | None = None, source: str | None = None,
                        user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    query: dict = {"user_id": user["_id"]}
    if company:
        query["company_key"] = svc.company_key(company)
    if source:
        query["source"] = source
    docs = await db[c.RECRUITER_CONTACTS].find(query).sort("updated_at", DESCENDING).to_list(1000)
    if q:
        needle = q.lower()
        docs = [d for d in docs if needle in f"{d['name']} {d['company']} {d.get('title') or ''} {d.get('email') or ''}".lower()]
    return [svc.contact_out(d) for d in docs]


@router.post("/recruiters", status_code=201)
async def add_contact(body: ContactIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    doc, created = await svc.create_contact(db, user["_id"], body)
    if not created:
        raise HTTPException(status.HTTP_409_CONFLICT, {"message": "You already have this contact", "id": doc["_id"]})
    return svc.contact_out(doc)


@router.put("/recruiters/{contact_id}")
async def edit_contact(contact_id: str, body: ContactUpdate, user: dict = Depends(get_current_user),
                       db: AsyncIOMotorDatabase = Depends(db_dep)):
    return svc.contact_out(await svc.update_contact(db, user["_id"], contact_id, body))


@router.delete("/recruiters/{contact_id}", status_code=204)
async def delete_contact(contact_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    await svc.get_contact(db, user["_id"], contact_id)
    await db[c.RECRUITER_CONTACTS].delete_one({"_id": contact_id})
    ids = [d["_id"] async for d in db[c.OUTREACH].find({"user_id": user["_id"], "contact_id": contact_id}, {"_id": 1})]
    await db[c.OUTREACH].delete_many({"_id": {"$in": ids}})
    await db[c.FOLLOWUPS].delete_many({"user_id": user["_id"], "outreach_id": {"$in": ids}})
    return Response(status_code=204)


@router.post("/recruiters/import-csv")
async def import_csv(body: CsvImport, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await svc.import_csv(db, user["_id"], body.csv)


@router.post("/recruiters/import-inbox")
async def import_inbox(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await svc.import_from_inbox(db, user["_id"])


@router.post("/recruiters/sync")
async def sync_contacts(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Recruiters from your inbox plus contacts published in your saved job postings."""
    return await svc.sync_contacts(db, user["_id"])


@router.get("/recruiters/companies")
async def companies(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    rows = await db[c.RECRUITER_CONTACTS].aggregate([
        {"$match": {"user_id": user["_id"]}},
        {"$group": {"_id": "$company_key", "company": {"$first": "$company"}, "contacts": {"$sum": 1}}},
        {"$sort": {"contacts": -1}}]).to_list(500)
    return [{"company": r["company"], "contacts": r["contacts"]} for r in rows]


@router.get("/recruiters/for-job/{job_id}")
async def contacts_for_job(job_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """People you know at the job's company - the starting point for a referral request."""
    job = await db[c.JOBS].find_one({"_id": job_id, "user_id": user["_id"]})
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    docs = await db[c.RECRUITER_CONTACTS].find({"user_id": user["_id"], "company_key": job["company_key"]}).to_list(100)
    rank = {"referral": 0, "alumni": 1, "hiring_manager": 2, "recruiter": 3}
    docs.sort(key=lambda d: rank.get(d.get("role"), 9))
    return {"company": job["company"], "contacts": [svc.contact_out(d) for d in docs]}


# ------------------------------------------------------------------ outreach

@router.get("/outreach")
async def list_outreach(status_: OutreachStatus | None = Query(None, alias="status"), contact_id: str | None = None,
                        user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    q: dict = {"user_id": user["_id"]}
    if status_:
        q["status"] = status_
    if contact_id:
        q["contact_id"] = contact_id
    docs = await db[c.OUTREACH].find(q).sort("updated_at", DESCENDING).to_list(300)
    ids = list({d["contact_id"] for d in docs})
    contacts = {x["_id"]: x async for x in db[c.RECRUITER_CONTACTS].find({"_id": {"$in": ids}})}
    return [svc.outreach_out(d, contacts.get(d["contact_id"])) for d in docs]


@router.get("/outreach/templates")
async def outreach_templates(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    from app.profiles.service import get_profile

    return svc.templates(await get_profile(db, user["_id"]))


@router.get("/outreach/stats")
async def outreach_stats(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await svc.stats(db, user["_id"])


@router.post("/outreach/draft", status_code=201)
async def draft(body: DraftIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await svc.create_draft(db, user["_id"], body)


@router.put("/outreach/{outreach_id}")
async def edit(outreach_id: str, body: OutreachEdit, user: dict = Depends(get_current_user),
               db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await svc.edit_draft(db, user["_id"], outreach_id, body.subject, body.body)


@router.post("/outreach/{outreach_id}/approve")
async def approve(outreach_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await svc.approve(db, user["_id"], outreach_id)


@router.post("/outreach/{outreach_id}/send")
async def send(outreach_id: str, approve: bool = False, user: dict = Depends(get_current_user),
               db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Send from the user's Gmail. With approve=true a draft is approved and sent in one click."""
    return await svc.send_now(db, user["_id"], outreach_id, approve_first=approve)


@router.post("/outreach/{outreach_id}/mark-sent")
async def mark_sent(outreach_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await svc.mark_sent(db, user["_id"], outreach_id)


@router.post("/outreach/{outreach_id}/outcome/{outcome}")
async def outcome(outreach_id: str, outcome: Literal["replied", "bounced", "no_response", "unsubscribed", "cancelled"],
                  user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await svc.set_outcome(db, user["_id"], outreach_id, outcome)


@router.post("/outreach/followups/{followup_id}/done", status_code=204)
async def followup_done(followup_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    await svc.complete_followup(db, user["_id"], followup_id)
    return Response(status_code=204)

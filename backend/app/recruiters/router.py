from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from pymongo import DESCENDING

from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.recruiters import bulk
from app.recruiters import service as svc
from app.schemas.recruiter import (
    BulkIn,
    CompanyTypePatch,
    ContactIn,
    ContactUpdate,
    CsvImport,
    DraftIn,
    EmailTemplateIn,
    EmailTemplateUpdate,
    OutreachEdit,
    OutreachStatus,
)

router = APIRouter(tags=["recruiters"])


# ------------------------------------------------------------------ contacts

@router.get("/recruiters")
async def list_contacts(q: str | None = Query(None, max_length=100), company: str | None = None, source: str | None = None,
                        company_type: Literal["service", "product", "startup", "unknown"] | None = None,
                        has_email: bool | None = None, contacted: bool | None = None,
                        paged: bool = False, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                        sort: Literal["recent", "name", "company"] = "recent",
                        user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """A plain list (first 1000, used by the mobile app) or, with paged=1, {items, total, page, page_size}."""
    filters = {"q": q, "company": company, "company_type": company_type, "has_email": has_email, "contacted": contacted, "source": source}
    if paged:
        return await bulk.list_page(db, user["_id"], filters, page=page, page_size=page_size, sort=sort)
    await bulk.ensure_types(db, user["_id"])
    docs = await db[c.RECRUITER_CONTACTS].find(bulk.build_query(user["_id"], **filters)).sort("updated_at", DESCENDING).to_list(1000)
    return [svc.contact_out(d) for d in docs]


@router.post("/recruiters", status_code=201)
async def add_contact(body: ContactIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    doc, created = await svc.create_contact(db, user["_id"], body)
    if not created:
        raise HTTPException(status.HTTP_409_CONFLICT, {"message": "You already have this contact", "id": doc["_id"]})
    return svc.contact_out(doc)


@router.patch("/recruiters/{contact_id}")
async def patch_company_type(contact_id: str, body: CompanyTypePatch, user: dict = Depends(get_current_user),
                             db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Override a contact's company type (null goes back to the curated list)."""
    return await bulk.set_company_type(db, user["_id"], contact_id, body.company_type)


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
async def companies(q: str | None = Query(None, max_length=100), limit: int = Query(500, ge=1, le=500),
                    user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await bulk.companies(db, user["_id"], q, limit)


# ---- bulk email to HR contacts (templates, preview, approved send within the caps)

@router.get("/recruiters/email-templates")
async def email_templates(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await bulk.list_templates(db, user["_id"])


class RenderIn(BaseModel):
    template_id: str = Field(max_length=80)
    company: str = Field(default="", max_length=120)
    role: str = Field(default="", max_length=200)
    hr_name: str = Field(default="", max_length=120)


@router.post("/recruiters/email-templates/render")
async def render_email_template(body: RenderIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Fill a template for one email (Apply by email): verified profile values only; missing ones are dropped."""
    from app.profiles.service import get_profile
    from app.recruiters import email_templates as et

    tpl = next((t for t in await bulk.list_templates(db, user["_id"]) if t.get("id") == body.template_id), None)
    if not tpl:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    contact = {"name": body.hr_name, "company": body.company, "role_applied": body.role}
    subject, text = et.render_for(tpl, await get_profile(db, user["_id"]), contact)
    return {"subject": subject, "body": text, "attach_resume": tpl.get("attach_resume", False)}


@router.post("/recruiters/email-templates", status_code=201)
async def create_email_template(body: EmailTemplateIn, user: dict = Depends(get_current_user),
                                db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await bulk.save_template(db, user["_id"], body.model_dump())


@router.put("/recruiters/email-templates/{template_id}")
async def edit_email_template(template_id: str, body: EmailTemplateUpdate, user: dict = Depends(get_current_user),
                              db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await bulk.save_template(db, user["_id"], body.model_dump(exclude_unset=True), template_id)


@router.delete("/recruiters/email-templates/{template_id}", status_code=204)
async def remove_email_template(template_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    await bulk.delete_template(db, user["_id"], template_id)
    return Response(status_code=204)


@router.post("/recruiters/bulk/preview")
async def bulk_preview(body: BulkIn, limit: int = Query(10, ge=1, le=50), user: dict = Depends(get_current_user),
                       db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await bulk.preview(db, user["_id"], body, limit)


@router.post("/recruiters/bulk/send")
async def bulk_send(body: BulkIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Needs confirm=true (the user's approval). Sends what the caps allow now and queues the rest, approved, for the next send."""
    return await bulk.send(db, user["_id"], body)


@router.post("/recruiters/bulk/send-queued")
async def bulk_send_queued(confirm: bool = False, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await bulk.send_queued(db, user["_id"], confirm)


@router.get("/recruiters/find-people")
async def find_people(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """For each company you're pursuing: who to reach (HR, talent acquisition, QA / test managers), as
    LinkedIn people-search links you open yourself, plus the contacts and hiring emails Saige already has.
    Saige never scrapes LinkedIn; you open the search, pick the person, and add them."""
    from urllib.parse import quote

    from app.jobs.dedupe import company_key

    uid = user["_id"]
    counts: dict[str, dict] = {}

    def bump(name: str | None, source: str, url: str | None = None) -> None:
        if not name or name.lower() in ("unknown company", "company not listed"):
            return
        k = company_key(name)
        if not k:
            return
        row = counts.setdefault(k, {"company": name, "score": 0, "sources": set(), "job_url": None})
        row["score"] += {"application": 3, "job": 1, "feed": 1}[source]
        row["sources"].add(source)
        row["job_url"] = row["job_url"] or url

    async for a in db[c.APPLICATIONS].find({"user_id": uid}, {"company": 1, "application_url": 1}).limit(300):
        bump(a.get("company"), "application", a.get("application_url"))
    async for j in db[c.JOBS].find({"user_id": uid}, {"company": 1, "application_url": 1}).limit(300):
        bump(j.get("company"), "job", j.get("application_url"))
    feed = await db[c.JOB_FEED].find_one({"_id": uid}, {"items.company": 1, "items.score": 1}) or {}
    for it in feed.get("items", []):
        if (it.get("score") or 0) >= 60:
            bump(it.get("company"), "feed")

    contacts: dict[str, list] = {}
    async for ct in db[c.RECRUITER_CONTACTS].find({"user_id": uid}, {"name": 1, "company_key": 1, "email": 1, "phone": 1, "title": 1}):
        contacts.setdefault(ct.get("company_key") or "", []).append(
            {"id": ct["_id"], "name": ct["name"], "email": ct.get("email"), "phone": ct.get("phone"), "title": ct.get("title")})
    people = ["HR", "Talent Acquisition", "Technical Recruiter", "QA Manager", "Test Lead", "SDET Manager", "Engineering Manager"]
    out = []
    for k, row in sorted(counts.items(), key=lambda kv: -kv[1]["score"])[:40]:
        name = row["company"]
        out.append({
            "company": name, "sources": sorted(row["sources"]), "job_url": row["job_url"], "known": contacts.get(k, []),
            "searches": [{"label": p, "url": f"https://www.linkedin.com/search/results/people/?keywords={quote(p + ' ' + name)}"}
                         for p in people],
            "email_search": f"https://www.google.com/search?q={quote(f'{name} HR recruiter email careers')}",
        })
    return out


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

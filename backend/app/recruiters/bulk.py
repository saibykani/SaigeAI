"""Contact listing (server-side paging, filters, company types) and bulk email to HR contacts.

Bulk sending never bypasses the caps: at most the daily limit (hard max 10) goes out now and at most 3 per company per
7 days; everything else is saved as an approved message in the queue ("Ready to send tomorrow") and is only sent when
the user clicks send again. The user's explicit confirmation is the approval. Nothing is scheduled automatically.
"""

import re
from datetime import timedelta

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from app.automation.service import get_settings_doc, is_allowed, is_blocked
from app.database import collections as c
from app.email import outbound
from app.profiles.service import get_profile
from app.recruiters import company_types as ct
from app.recruiters import email_templates as et
from app.recruiters import service as svc
from app.schemas.recruiter import BulkIn
from app.services.agent_runs import agent_run
from app.services.audit import log_action
from app.utils import new_id, utcnow

BULK_MAX = 200
PAGE_SIZES = (25, 50, 100)
SORTS = {"recent": [("created_at", DESCENDING), ("_id", ASCENDING)], "name": [("name", ASCENDING), ("_id", ASCENDING)],
         "company": [("company_key", ASCENDING), ("name", ASCENDING), ("_id", ASCENDING)]}


# ------------------------------------------------------------------ listing

def build_query(uid: str, *, q: str | None = None, company: str | None = None, company_type: str | None = None,
                has_email: bool | None = None, contacted: bool | None = None, source: str | None = None) -> dict:
    ands: list[dict] = [{"user_id": uid}]
    if company:
        ands.append({"company_key": svc.company_key(company)})
    if source:
        ands.append({"source": source})
    if company_type:
        ands.append({"$or": [{"ctype_user": company_type}, {"ctype_user": None, "ctype": company_type}]})
    if has_email is True:
        ands.append({"email_key": {"$nin": [None, ""]}})
    elif has_email is False:
        ands.append({"email_key": {"$in": [None, ""]}})
    if contacted is True:
        ands.append({"last_contacted_at": {"$ne": None}})
    elif contacted is False:
        ands.append({"last_contacted_at": None})
    if q and q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        ands.append({"$or": [{"name": rx}, {"company": rx}, {"email": rx}, {"title": rx}]})
    return ands[0] if len(ands) == 1 else {"$and": ands}


async def ensure_types(db: AsyncIOMotorDatabase, uid: str) -> None:
    """Classify contacts that have no stored company type yet (older rows, new imports): a handful of bulk updates."""
    col = db[c.RECRUITER_CONTACTS]
    if not await col.find_one({"user_id": uid, "ctype": None}, {"_id": 1}):
        return
    keys: dict[str, list] = {}
    async for g in col.aggregate([{"$match": {"user_id": uid, "ctype": None}},
                                  {"$group": {"_id": "$company_key", "company": {"$first": "$company"}, "email": {"$first": "$email"}}}]):
        keys.setdefault(ct.auto_company_type(g["company"], g.get("email")), []).append(g["_id"])
    for t in ct.TYPES:
        if keys.get(t):
            await col.update_many({"user_id": uid, "ctype": None, "company_key": {"$in": keys[t]}}, {"$set": {"ctype": t}})


async def list_page(db: AsyncIOMotorDatabase, uid: str, filters: dict, *, page: int, page_size: int, sort: str) -> dict:
    await ensure_types(db, uid)
    query = build_query(uid, **filters)
    col = db[c.RECRUITER_CONTACTS]
    total = await col.count_documents(query)
    cur = col.find(query).sort(SORTS.get(sort, SORTS["recent"])).skip((page - 1) * page_size).limit(page_size)
    return {"items": [svc.contact_out(d) async for d in cur], "total": total, "page": page, "page_size": page_size}


async def companies(db: AsyncIOMotorDatabase, uid: str, q: str | None, limit: int) -> list[dict]:
    await ensure_types(db, uid)
    rows = await db[c.RECRUITER_CONTACTS].aggregate([
        {"$match": {"user_id": uid}},
        {"$group": {"_id": "$company_key", "company": {"$first": "$company"}, "contacts": {"$sum": 1}, "ctype": {"$first": "$ctype"}}},
        {"$sort": {"contacts": -1, "company": 1}}]).to_list(20000)
    needle = (q or "").strip().lower()
    out = [{"company": r["company"], "contacts": r["contacts"], "company_type": r.get("ctype") or "unknown"}
           for r in rows if not needle or needle in (r["company"] or "").lower()]
    return out[:limit]


async def set_company_type(db: AsyncIOMotorDatabase, uid: str, contact_id: str, value: str | None) -> dict:
    await svc.get_contact(db, uid, contact_id)
    await db[c.RECRUITER_CONTACTS].update_one({"_id": contact_id}, {"$set": {"ctype_user": value, "updated_at": utcnow()}})
    await log_action(db, user_id=uid, action="recruiter.company_type_set", entity="recruiter_contact", entity_id=contact_id,
                     details={"company_type": value})
    return svc.contact_out(await svc.get_contact(db, uid, contact_id))


# ------------------------------------------------------------------ templates

async def get_template(db: AsyncIOMotorDatabase, uid: str, template_id: str) -> dict:
    for b in et.BUILTIN:
        if b["id"] == template_id:
            return b
    d = await db[c.EMAIL_TEMPLATES].find_one({"_id": template_id, "user_id": uid})
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    return d


async def list_templates(db: AsyncIOMotorDatabase, uid: str) -> list[dict]:
    mine = await db[c.EMAIL_TEMPLATES].find({"user_id": uid}).sort("created_at", DESCENDING).to_list(200)
    return [et.template_out(b, True) for b in et.BUILTIN] + [et.template_out(d) for d in mine]


async def save_template(db: AsyncIOMotorDatabase, uid: str, data: dict, template_id: str | None = None) -> dict:
    now = utcnow()
    if template_id is None:
        if await db[c.EMAIL_TEMPLATES].count_documents({"user_id": uid}) >= 50:
            raise HTTPException(status.HTTP_409_CONFLICT, "You can keep up to 50 templates")
        doc = {"_id": new_id(), "user_id": uid, **data, "created_at": now, "updated_at": now}
        await db[c.EMAIL_TEMPLATES].insert_one(doc)
        return et.template_out(doc)
    res = await db[c.EMAIL_TEMPLATES].find_one_and_update({"_id": template_id, "user_id": uid}, {"$set": {**data, "updated_at": now}},
                                                          return_document=True)
    if not res:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found (built-in templates are read-only: duplicate them)")
    return et.template_out(res)


async def delete_template(db: AsyncIOMotorDatabase, uid: str, template_id: str) -> None:
    res = await db[c.EMAIL_TEMPLATES].delete_one({"_id": template_id, "user_id": uid})
    if not res.deleted_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found (built-in templates can't be deleted)")


# ------------------------------------------------------------------ bulk plan

async def _quota(db: AsyncIOMotorDatabase, uid: str, now) -> dict:
    limit = await svc.daily_limit(db, uid)
    today = await svc.sent_today(db, uid, now)
    return {"daily_limit": limit, "sent_today": today, "remaining_today": max(0, limit - today),
            "per_company_weekly_cap": svc.PER_COMPANY_WEEKLY_CAP, "can_send_from_saige": bool(await outbound.find_sender(db, uid))}


async def _contacts(db: AsyncIOMotorDatabase, uid: str, body: BulkIn) -> list[dict]:
    if body.contact_ids is not None:
        ids = list(dict.fromkeys(body.contact_ids))[:BULK_MAX]
        found = {d["_id"]: d async for d in db[c.RECRUITER_CONTACTS].find({"user_id": uid, "_id": {"$in": ids}})}
        return [found[i] for i in ids if i in found]
    if body.filter is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Select contacts or a filter")
    await ensure_types(db, uid)
    query = build_query(uid, **body.filter.model_dump())
    return await db[c.RECRUITER_CONTACTS].find(query).sort(SORTS["recent"]).limit(BULK_MAX).to_list(BULK_MAX)


async def plan(db: AsyncIOMotorDatabase, uid: str, body: BulkIn) -> dict:
    """Render the template for every selected contact, skip the ineligible and decide who goes now vs. queued."""
    now = utcnow()
    tpl = await get_template(db, uid, body.template_id)
    profile = await get_profile(db, uid)
    settings = await get_settings_doc(db, uid)
    contacts = await _contacts(db, uid, body)
    open_ids = {o["contact_id"] async for o in db[c.OUTREACH].find(
        {"user_id": uid, "status": {"$in": list(svc.OPEN)}, "contact_id": {"$in": [x["_id"] for x in contacts]}}, {"contact_id": 1})}
    keys = list({x.get("company_key") for x in contacts if x.get("company_key")})
    week: dict[str, int] = {}
    async for g in db[c.OUTREACH].aggregate([
            {"$match": {"user_id": uid, "company_key": {"$in": keys}, "sent_at": {"$gte": now - timedelta(days=7)}}},
            {"$group": {"_id": "$company_key", "n": {"$sum": 1}}}]):
        week[g["_id"]] = g["n"]
    quota = await _quota(db, uid, now)
    remaining = quota["remaining_today"]
    items, skipped = [], []
    for contact in contacts:
        reason = None
        if not contact.get("email"):
            reason = "No email address"
        elif contact.get("unsubscribed"):
            reason = "Asked not to be contacted"
        elif contact["_id"] in open_ids:
            reason = "Already has a message in your queue"
        elif is_blocked(settings, contact.get("company")):
            reason = "Company is in your blocked list"
        subject = text = ""
        validation = None
        if not reason:
            subject, text = et.render_for(tpl, profile, contact)
            validation = svc.check_truth(profile, text)
            if validation["status"] != "PASSED":
                reason = "Contains claims not in your verified profile"
            elif not text:
                reason = "Template is empty after removing unknown values"
        if reason:
            skipped.append({"contact_id": contact["_id"], "name": contact["name"], "company": contact["company"], "reason": reason})
            continue
        k = contact.get("company_key") or ""
        now_ok = remaining > 0 and week.get(k, 0) < svc.PER_COMPANY_WEEKLY_CAP
        if now_ok:
            remaining -= 1
            week[k] = week.get(k, 0) + 1
        items.append({"contact": contact, "subject": subject, "body": text, "validation": validation, "send_now": now_ok})
    return {"template": tpl, "items": items, "skipped": skipped, "selected": len(contacts), "quota": quota,
            "paused": not await is_allowed(db, uid, "recruiter_outreach")}


async def preview(db: AsyncIOMotorDatabase, uid: str, body: BulkIn, limit: int = 10) -> dict:
    p = await plan(db, uid, body)
    now_n = sum(1 for i in p["items"] if i["send_now"])
    return {
        "template_id": body.template_id, "selected": p["selected"], "eligible": len(p["items"]), "send_now": now_n,
        "queued": len(p["items"]) - now_n, "skipped": p["skipped"][:50], "skipped_count": len(p["skipped"]), "paused": p["paused"],
        "attach_resume": bool(p["template"].get("attach_resume")), "quota": p["quota"], "max_per_action": BULK_MAX,
        "previews": [{"contact_id": i["contact"]["_id"], "name": i["contact"]["name"], "company": i["contact"]["company"],
                      "to": i["contact"]["email"], "subject": i["subject"], "body": i["body"], "send_now": i["send_now"]}
                     for i in p["items"][:limit]],
    }


# ------------------------------------------------------------------ send

async def send(db: AsyncIOMotorDatabase, uid: str, body: BulkIn) -> dict:
    if not body.confirm:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Confirm to approve sending these emails")
    if not await is_allowed(db, uid, "recruiter_outreach"):
        raise HTTPException(status.HTTP_423_LOCKED, "Recruiter outreach is paused. Resume it in Automation settings.")
    p = await plan(db, uid, body)
    if not p["items"]:
        return {"sent": 0, "queued": 0, "failed": 0, "skipped": p["skipped"][:50], "skipped_count": len(p["skipped"]), "results": []}
    if not p["quota"]["can_send_from_saige"] and any(i["send_now"] for i in p["items"]):
        raise HTTPException(status.HTTP_409_CONFLICT, "Connect Gmail (Integrations) so Saige can send for you.")
    tpl, bulk_id = p["template"], new_id()
    results: list[dict] = []
    async with agent_run(db, "recruiter_bulk_send", uid, {"template": tpl["name"], "selected": p["selected"]}) as run:
        for it in p["items"]:
            contact, now = it["contact"], utcnow()
            doc = {"_id": new_id(), "user_id": uid, "contact_id": contact["_id"], "contact_name": contact["name"],
                   "company": contact["company"], "company_key": contact.get("company_key"), "job_id": None, "parent_id": None,
                   "kind": tpl["kind"], "status": "approved", "subject": it["subject"], "body": it["body"],
                   "validation": it["validation"], "approved_at": now, "sent_at": None, "replied_at": None,
                   "attach_resume": bool(tpl.get("attach_resume")), "bulk_id": bulk_id, "template_id": body.template_id,
                   "queued": not it["send_now"], "created_at": now, "updated_at": now}
            await db[c.OUTREACH].insert_one(doc)
            outcome = "queued"
            if it["send_now"]:
                try:
                    await svc.send_now(db, uid, doc["_id"])
                    outcome = "sent"
                    await db[c.OUTREACH].update_one({"_id": doc["_id"]}, {"$set": {"queued": False}})
                except HTTPException as exc:  # a cap tripped between planning and sending: it stays queued
                    if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
                        outcome = "failed"
                        run.errors.append(f"{contact['company']}: {exc.detail}")
            results.append({"contact_id": contact["_id"], "outreach_id": doc["_id"], "name": contact["name"],
                            "company": contact["company"], "result": outcome})
        n = {k: sum(1 for r in results if r["result"] == k) for k in ("sent", "queued", "failed")}
        run.output = {**n, "skipped": len(p["skipped"]), "bulk_id": bulk_id}
        run.action(f"Bulk email '{tpl['name']}': {n['sent']} sent, {n['queued']} queued, {n['failed']} failed")
    await log_action(db, user_id=uid, action="recruiter.bulk_send", entity="outreach", entity_id=bulk_id,
                     details={"template": tpl["name"], **n, "skipped": len(p["skipped"])})
    return {**n, "skipped": p["skipped"][:50], "skipped_count": len(p["skipped"]), "bulk_id": bulk_id, "results": results[:100]}


async def send_queued(db: AsyncIOMotorDatabase, uid: str, confirm: bool) -> dict:
    """Send previously approved bulk messages ("Ready to send tomorrow") within today's remaining quota."""
    if not confirm:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Confirm to send the queued emails")
    if not await is_allowed(db, uid, "recruiter_outreach"):
        raise HTTPException(status.HTTP_423_LOCKED, "Recruiter outreach is paused. Resume it in Automation settings.")
    quota = await _quota(db, uid, utcnow())
    if not quota["can_send_from_saige"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "Connect Gmail (Integrations) so Saige can send for you.")
    sent = 0
    async for o in db[c.OUTREACH].find({"user_id": uid, "status": "approved", "queued": True}).sort("created_at", ASCENDING).limit(150):
        if sent >= quota["remaining_today"]:
            break
        try:
            await svc.send_now(db, uid, o["_id"])
            await db[c.OUTREACH].update_one({"_id": o["_id"]}, {"$set": {"queued": False}})
            sent += 1
        except HTTPException:
            continue
    left = await queued_count(db, uid)
    if sent:
        await log_action(db, user_id=uid, action="recruiter.bulk_send_queued", entity="outreach", details={"sent": sent, "still_queued": left})
    return {"sent": sent, "still_queued": left, "quota": await _quota(db, uid, utcnow())}


async def queued_count(db: AsyncIOMotorDatabase, uid: str) -> int:
    return await db[c.OUTREACH].count_documents({"user_id": uid, "status": "approved", "queued": True})

"""Email reply tracking: every email Saige sends is stored in `sent_emails` and linked to the reply found by the
existing read-only Gmail sync. No tracking pixels, no link rewriting: matching uses only headers and addresses of
mail that already reached the user's own inbox.

Match order for an incoming email: (a) In-Reply-To / References contains our Message-ID, (b) same Gmail thread id,
(c) the sender is the recipient (or, for a non-free domain, a colleague) within 30 days with a Re: / subject overlap.
Mail from mailer-daemon / postmaster that mentions our Message-ID or the recipient address marks a bounce.
"""

import logging
import re
from datetime import UTC, datetime, timedelta
from statistics import median

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from app.database import collections as c
from app.utils import new_id, utcnow

log = logging.getLogger(__name__)
KINDS = ("outreach", "apply", "auto_apply", "bulk", "thank_you")
REPLY_WINDOW = timedelta(days=30)
MIN_SAMPLE = 5  # no "best" claims under this many sends
INTERVIEW_CATEGORIES = ("Interview Invitation", "Assessment", "Coding Test")
FREE_DOMAINS = {"gmail.com", "googlemail.com", "yahoo.com", "yahoo.in", "yahoo.co.in", "outlook.com", "hotmail.com", "live.com",
                "icloud.com", "rediffmail.com", "proton.me", "protonmail.com", "aol.com"}
_BOUNCE_SENDER = re.compile(r"(mailer-daemon|postmaster)@", re.I)
_MSGID = re.compile(r"<[^<>\s]+>")


def _aware(d):
    if d is None:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def norm_subject(s: str) -> str:
    s = (s or "").lower()
    while True:
        n = re.sub(r"^\s*((re|fwd?|aw)\s*:\s*)+", "", s)
        if n == s:
            break
        s = n
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def message_ids(*values: str | None) -> list[str]:
    return [m.lower() for v in values for m in _MSGID.findall(v or "")]


def _subject_overlap(a: str, b: str) -> bool:
    x, y = norm_subject(a), norm_subject(b)
    if not x or not y:
        return False
    if x in y or y in x:
        return True
    tx, ty = {w for w in x.split() if len(w) > 3}, {w for w in y.split() if len(w) > 3}
    return bool(tx and ty and len(tx & ty) >= max(2, min(len(tx), len(ty)) // 2))


def _email_of(sender: str | None) -> str:
    m = re.search(r"[\w.+'-]+@[\w.-]+\.\w+", sender or "")
    return m.group(0).lower() if m else ""


def _domain(addr: str) -> str:
    return addr.split("@")[-1].lower() if "@" in addr else ""


async def record_sent(db: AsyncIOMotorDatabase, uid: str, *, kind: str, to: str, subject: str, message_id: str | None,
                      company: str | None = None, role: str | None = None, template_id: str | None = None,
                      template_name: str | None = None, application_id: str | None = None, outreach_id: str | None = None,
                      contact_id: str | None = None, thread_id: str | None = None, sent_at: datetime | None = None,
                      status: str = "sent") -> dict | None:
    """Store one sent email. Never raises: tracking must not break sending. Idempotent per (user, message id)."""
    try:
        to_email = _email_of(to) or (to or "").strip().lower()
        mid = (message_id or "").strip() or None
        if mid:
            existing = await db[c.SENT_EMAILS].find_one({"user_id": uid, "message_id": mid})
            if existing:
                return None
        doc = {"_id": new_id(), "user_id": uid, "kind": kind, "template_id": template_id, "template_name": template_name,
               "to_email": to_email, "to_domain": _domain(to_email), "company": company, "role": role, "subject": (subject or "")[:300],
               "message_id": mid, "thread_id": thread_id, "application_id": application_id, "outreach_id": outreach_id,
               "contact_id": contact_id, "sent_at": sent_at or utcnow(), "status": status, "replied_at": None,
               "reply_email_id": None, "reply_category": None, "reply_snippet": None, "created_at": utcnow()}
        await db[c.SENT_EMAILS].insert_one(doc)
        return doc
    except Exception:  # noqa: BLE001
        log.warning("couldn't record sent email", exc_info=True)
        return None


def _mid_query(uid: str, mid: str) -> dict:
    return {"user_id": uid, "message_id": {"$regex": f"^{re.escape(mid)}$", "$options": "i"}}


# ------------------------------------------------------------------ matching

async def find_match(db: AsyncIOMotorDatabase, uid: str, msg: dict, *, sender_email: str, received: datetime) -> tuple[dict | None, bool]:
    """(sent_email, is_bounce) for an incoming email, without changing anything."""
    coll = db[c.SENT_EMAILS]
    refs = message_ids(msg.get("in_reply_to"), msg.get("references"))
    sender = sender_email or _email_of(msg.get("sender"))
    if _BOUNCE_SENDER.match(sender or ""):
        body = (msg.get("body") or "").lower()
        for mid in dict.fromkeys(refs + message_ids(body)):
            se = await coll.find_one(_mid_query(uid, mid))
            if se:
                return se, True
        async for se in coll.find({"user_id": uid, "status": "sent", "sent_at": {"$lte": received}}).sort("sent_at", DESCENDING).limit(300):
            if se["to_email"] and se["to_email"] in body:
                return se, True
        return None, False
    for mid in refs:  # (a) headers
        se = await coll.find_one(_mid_query(uid, mid))
        if se:
            return se, False
    if msg.get("thread_id"):  # (b) same Gmail thread
        se = await coll.find_one({"user_id": uid, "thread_id": msg["thread_id"], "status": "sent", "sent_at": {"$lte": received}},
                                 sort=[("sent_at", DESCENDING)])
        if se:
            return se, False
    if not sender:  # (c) sender window
        return None, False
    subject = msg.get("subject") or ""
    re_prefix = bool(re.match(r"\s*(re|aw)\s*:", subject, re.I))
    dom = _domain(sender)
    q = {"user_id": uid, "status": "sent", "sent_at": {"$lte": received, "$gte": received - REPLY_WINDOW}}
    async for se in coll.find(q).sort("sent_at", DESCENDING).limit(300):
        if se["to_email"] == sender and (re_prefix or _subject_overlap(subject, se["subject"])):
            return se, False
        if dom and dom not in FREE_DOMAINS and se["to_domain"] == dom and _subject_overlap(subject, se["subject"]):
            return se, False
    return None, False


async def apply_match(db: AsyncIOMotorDatabase, uid: str, se: dict, bounce: bool, *, email_id: str | None, category: str | None,
                      snippet: str | None, received: datetime, thread_id: str | None = None) -> bool:
    """Mark the sent email replied / bounced (first reply only) and sync an outreach that is still waiting."""
    if se["status"] != "sent":
        # a header/thread match to an already-replied email only fills in a missing thread id
        if thread_id and not se.get("thread_id"):
            await db[c.SENT_EMAILS].update_one({"_id": se["_id"]}, {"$set": {"thread_id": thread_id}})
        return False
    patch: dict = {}
    if thread_id and not se.get("thread_id"):
        patch["thread_id"] = thread_id
    if bounce:
        patch.update(status="bounced", reply_email_id=email_id, reply_category="Bounce", reply_snippet=(snippet or "")[:300])
    else:
        patch.update(status="replied", replied_at=received, reply_email_id=email_id, reply_category=category or "Reply",
                     reply_snippet=(snippet or "")[:300])
    await db[c.SENT_EMAILS].update_one({"_id": se["_id"]}, {"$set": patch})
    if se.get("outreach_id"):  # existing logic usually did this already: only move an outreach that is still waiting
        o = await db[c.OUTREACH].find_one({"_id": se["outreach_id"], "user_id": uid})
        if o and o.get("status") == "sent":
            from app.recruiters.service import set_outcome

            try:
                await set_outcome(db, uid, o["_id"], "bounced" if bounce else "replied")
            except Exception:  # noqa: BLE001
                log.warning("outreach status sync failed", exc_info=True)
    return True


async def on_inbound(db: AsyncIOMotorDatabase, uid: str, msg: dict, *, email_id: str | None, category: str | None, sender_email: str,
                     received: datetime, match: tuple[dict | None, bool] | None = None) -> bool:
    se, bounce = match if match is not None else await find_match(db, uid, msg, sender_email=sender_email, received=received)
    if not se:
        return False
    return await apply_match(db, uid, se, bounce, email_id=email_id, category=category,
                             snippet=msg.get("snippet") or (msg.get("body") or "")[:200], received=received, thread_id=msg.get("thread_id"))


# ------------------------------------------------------------------ backfill

async def backfill(db: AsyncIOMotorDatabase, uid: str) -> dict:
    created = 0
    q = {"user_id": uid, "status": {"$in": ["sent", "replied", "bounced", "no_response"]}, "sent_at": {"$ne": None}, "sent_via": "gmail"}
    async for o in db[c.OUTREACH].find(q):
        ct = await db[c.RECRUITER_CONTACTS].find_one({"_id": o["contact_id"]}) or {}
        if not ct.get("email") or o.get("kind") == "linkedin_note":
            continue
        tname = None
        if o.get("template_id"):
            tpl = await db[c.EMAIL_TEMPLATES].find_one({"_id": o["template_id"]})
            tname = (tpl or {}).get("name") or o["template_id"]
        if not await db[c.SENT_EMAILS].find_one({"user_id": uid, "outreach_id": o["_id"]}):
            rec = await record_sent(db, uid, kind="bulk" if o.get("template_id") else "outreach", to=ct["email"], subject=o["subject"],
                                    message_id=o.get("message_id") or f"<outreach-{o['_id']}@saige.local>", company=o.get("company"),
                                    template_id=o.get("template_id"), template_name=tname or f"Outreach: {o.get('kind')}",
                                    outreach_id=o["_id"], contact_id=o.get("contact_id"), sent_at=_aware(o["sent_at"]))
            created += bool(rec)
        if o.get("status") == "replied":
            await db[c.SENT_EMAILS].update_one({"user_id": uid, "outreach_id": o["_id"], "status": "sent"}, {"$set": {
                "status": "replied", "replied_at": _aware(o.get("replied_at")) or _aware(o.get("updated_at")), "reply_category": "Recruiter Reply"}})
        elif o.get("status") == "bounced":
            await db[c.SENT_EMAILS].update_one({"user_id": uid, "outreach_id": o["_id"], "status": "sent"},
                                               {"$set": {"status": "bounced", "reply_category": "Bounce"}})
    async for r in db[c.RESUMES].find({"user_id": uid, "sent.0": {"$exists": True}}, {"sent": 1, "company": 1, "target_title": 1}):
        for s in r["sent"]:
            rec = await record_sent(db, uid, kind="apply", to=s["to"], subject=s.get("subject", ""), message_id=s.get("message_id"),
                                    company=r.get("company"), role=r.get("target_title"), template_name="Application email",
                                    sent_at=_aware(s.get("at")))
            created += bool(rec)
    async for a in db[c.APPLICATIONS].find({"user_id": uid, "applied_via": "email", "apply_message_id": {"$ne": None}}):
        rec = await record_sent(db, uid, kind="auto_apply", to=a.get("apply_email") or "", subject=f"Application: {a['role']}",
                                message_id=a["apply_message_id"], company=a["company"], role=a["role"], template_name="Auto-apply",
                                application_id=a["_id"], sent_at=_aware(a.get("applied_at") or a.get("updated_at")))
        created += bool(rec)
    async for d in db[c.DEBRIEFS].find({"user_id": uid, "thank_you.status": "sent"}):
        ty = d["thank_you"]
        rec = await record_sent(db, uid, kind="thank_you", to=ty.get("to", ""), subject=ty.get("subject", ""), message_id=ty.get("message_id"),
                                company=d.get("company"), role=d.get("role"), template_name="Thank-you", sent_at=_aware(ty.get("sent_at")))
        created += bool(rec)
    linked = 0
    async for e in db[c.EMAILS].find({"user_id": uid, "hidden": {"$ne": True}}).sort("received_at", 1):
        sender = (e.get("extracted") or {}).get("sender_email") or _email_of(e.get("sender"))
        received = _aware(e["received_at"])
        se, bounce = await find_match(db, uid, e, sender_email=sender, received=received)
        if se and await apply_match(db, uid, se, bounce, email_id=e["_id"], category=e.get("category"),
                                    snippet=e.get("snippet") or (e.get("body") or "")[:200], received=received, thread_id=e.get("thread_id")):
            linked += 1
    return {"recorded": created, "linked": linked}


# ------------------------------------------------------------------ queries

def sent_out(s: dict) -> dict:
    def iso(d):
        return _aware(d).isoformat() if d else None

    return {"id": s["_id"], "kind": s["kind"], "template_id": s.get("template_id"), "template_name": s.get("template_name"),
            "to_email": s["to_email"], "company": s.get("company"), "role": s.get("role"), "subject": s["subject"],
            "thread_id": s.get("thread_id"), "status": s["status"], "sent_at": iso(s["sent_at"]), "replied_at": iso(s.get("replied_at")),
            "reply_email_id": s.get("reply_email_id"), "reply_category": s.get("reply_category"), "reply_snippet": s.get("reply_snippet"),
            "gmail_url": f"https://mail.google.com/mail/u/0/#inbox/{s['thread_id']}" if s.get("thread_id") else None}


def build_query(uid: str, *, kind=None, status=None, template=None, company=None, since=None, until=None) -> dict:
    q: dict = {"user_id": uid}
    if kind:
        q["kind"] = kind
    if status:
        q["status"] = status
    if template:
        q["$or"] = [{"template_id": template}, {"template_name": template}]
    if company:
        q["company"] = {"$regex": re.escape(company), "$options": "i"}
    if since or until:
        q["sent_at"] = {**({"$gte": since} if since else {}), **({"$lte": until} if until else {})}
    return q


def _rate(sent: int, replied: int) -> float | None:
    return round(replied / sent * 100, 1) if sent else None


def _group(rows: list[dict], key) -> list[dict]:
    g: dict = {}
    for s in rows:
        k = key(s)
        if k is None:
            continue
        b = g.setdefault(k, {"sent": 0, "replies": 0, "bounced": 0, "interviews": 0})
        b["sent"] += 1
        b["replies"] += s["status"] == "replied"
        b["bounced"] += s["status"] == "bounced"
        b["interviews"] += s["status"] == "replied" and s.get("reply_category") in INTERVIEW_CATEGORIES
    return [{"key": k, **v, "rate": _rate(v["sent"], v["replies"]), "enough_data": v["sent"] >= MIN_SAMPLE}
            for k, v in sorted(g.items(), key=lambda kv: (-kv[1]["replies"], -kv[1]["sent"]))]


async def stats(db: AsyncIOMotorDatabase, uid: str, tz_name: str = "Asia/Kolkata") -> dict:
    from zoneinfo import ZoneInfo

    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        tz, tz_name = UTC, "UTC"
    rows = await db[c.SENT_EMAILS].find({"user_id": uid}).sort("sent_at", DESCENDING).to_list(5000)
    sent = len(rows)
    replied = [s for s in rows if s["status"] == "replied"]
    bounced = sum(s["status"] == "bounced" for s in rows)
    hours = [(_aware(s["replied_at"]) - _aware(s["sent_at"])).total_seconds() / 3600 for s in replied if s.get("replied_at")]
    hours = [h for h in hours if h >= 0]
    wd = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    by_wd = sorted(_group(rows, lambda s: wd[_aware(s["sent_at"]).astimezone(tz).weekday()]), key=lambda r: wd.index(r["key"]))
    by_hour = sorted(_group(rows, lambda s: _aware(s["sent_at"]).astimezone(tz).hour), key=lambda r: r["key"])
    by_domain = _group([s for s in rows if s.get("to_domain") and s["to_domain"] not in FREE_DOMAINS], lambda s: s["to_domain"])
    return {"sent": sent, "replied": len(replied), "bounced": bounced, "reply_rate": _rate(sent - bounced, len(replied)),
            "median_reply_hours": round(median(hours), 1) if hours else None, "min_sample": MIN_SAMPLE,
            "by_template": _group(rows, lambda s: s.get("template_name") or s.get("template_id") or "No template"),
            "by_kind": _group(rows, lambda s: s["kind"]), "by_domain": by_domain[:15],
            "by_weekday": by_wd, "by_hour": by_hour, "timezone": tz_name}

"""Career jobs email digest, sent to the user's own inbox.

It goes to the user (the account email, or `careers.digest_to`), never to a third party, so it isn't an
outward action that needs per-message approval; the user turns it on or off in Career jobs settings, and
the `emails` pause stops it. It is sent from the user's Gmail through the App Password connection. Each
posting is included once (`emailed_at`).
"""

import html
import re

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.automation.service import get_settings_doc, is_allowed
from app.careers.service import FIT_LABEL, roles_for
from app.config import get_settings
from app.database import collections as c
from app.profiles.service import get_profile
from app.services.audit import log_action
from app.services.notify import notify
from app.utils import utcnow

MAX_ITEMS = 25
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)


async def pending(db: AsyncIOMotorDatabase, uid: str, *, min_score: int, locations: list[str], limit: int = MAX_ITEMS,
                  include_sent: bool = False) -> list[dict]:
    q: dict = {"user_id": uid, "active": True, "score": {"$gte": min_score}}
    if not include_sent:
        q["emailed_at"] = None
    locs = [re.escape(x.strip()) for x in locations if x.strip()]
    if locs:
        q["$or"] = [{"location": {"$regex": "|".join(locs), "$options": "i"}}, {"scope": "remote"}]
    else:
        q["scope"] = {"$in": ["country", "remote"]}
    return await db[c.CAREER_JOBS].find(q, {"description": 0}).sort([("score", -1), ("first_seen", -1)]).to_list(limit)


def _gap_line(d: dict) -> str:
    parts = []
    if d.get("matched_skills"):
        parts.append("You match: " + ", ".join(d["matched_skills"][:5]))
    if d.get("missing_skills"):
        parts.append("Gaps: " + ", ".join(d["missing_skills"][:4]))
    return " · ".join(parts)


def render(items: list[dict], roles: list[str], app_url: str) -> tuple[str, str, str]:
    n = len(items)
    subject = f"Saige: {n} new {'job' if n == 1 else 'jobs'} for {', '.join(roles[:2])} on company career pages"
    text = [f"{n} new opening(s) on company career pages that fit your profile.", ""]
    rows = []
    for d in items:
        where = d.get("location") or ("Remote" if d.get("remote") else "Location not listed")
        text += [f"{d['score']}%  {d['title']} at {d['company']} ({where})", f"    {FIT_LABEL.get(d.get('fit', ''), '')}",
                 f"    {_gap_line(d)}" if _gap_line(d) else "", f"    Apply: {d.get('url') or d.get('careers_url')}", ""]
        e = html.escape
        rows.append(
            "<tr><td style='padding:14px 0;border-bottom:1px solid #2a2a2a'>"
            f"<div style='font-size:15px;font-weight:600;color:#f5f5f5'>{e(d['title'])}</div>"
            f"<div style='color:#a3a3a3;font-size:13px;margin-top:2px'>{e(d['company'])} · {e(where)}"
            + (f" · posted {e(d['posted'])}" if d.get("posted") else "") + "</div>"
            f"<div style='color:#d4d4d4;font-size:13px;margin-top:6px'>{e(FIT_LABEL.get(d.get('fit', ''), ''))}"
            + (f"<br><span style='color:#a3a3a3'>{e(_gap_line(d))}</span>" if _gap_line(d) else "") + "</div>"
            f"<div style='margin-top:8px'><a href='{e(d.get('url') or d.get('careers_url') or '')}' "
            "style='color:#ff9f0a;text-decoration:none;font-weight:600'>Open on career page</a></div></td>"
            f"<td style='padding:14px 0 14px 16px;border-bottom:1px solid #2a2a2a;text-align:right;vertical-align:top'>"
            f"<span style='font-size:20px;font-weight:700;color:#30d158'>{d['score']}%</span></td></tr>")
    text += [f"See every job, filters and resume advice: {app_url}/careers"]
    body_html = (
        "<div style='background:#000;padding:24px;font-family:Google Sans,Arial,sans-serif'>"
        "<div style='max-width:640px;margin:0 auto;background:#111;border-radius:20px;padding:24px'>"
        "<div style='color:#f5f5f5;font-size:20px;font-weight:700'>Saige AI · Career jobs</div>"
        f"<div style='color:#a3a3a3;font-size:14px;margin:6px 0 12px'>{n} new opening(s) for {html.escape(', '.join(roles))}</div>"
        f"<table style='width:100%;border-collapse:collapse'>{''.join(rows)}</table>"
        f"<div style='margin-top:20px'><a href='{html.escape(app_url)}/careers' style='color:#ff9f0a'>See all jobs, filters and "
        "resume advice in Saige</a></div></div></div>")
    return subject, "\n".join(t for t in text if t is not None), body_html


async def send(db: AsyncIOMotorDatabase, uid: str, *, trigger: str = "manual", test: bool = False) -> dict:
    """Email the new career-portal matches. `test` re-sends the current top matches even if already emailed."""
    from app.email import smtp
    from app.email.gmail import GmailError
    from app.services import crypto

    s = await get_settings_doc(db, uid)
    if trigger != "manual" and not s.careers.email_digest:
        return {"skipped": "email digest off"}
    if not await is_allowed(db, uid, "emails"):
        return {"skipped": "emails paused"}
    items = await pending(db, uid, min_score=s.careers.min_score, locations=s.careers.locations, include_sent=test)
    if not items:
        return {"sent": 0, "reason": "no new matches above your threshold"}
    user = await db[c.USERS].find_one({"_id": uid}, {"email": 1}) or {}
    to = (s.careers.digest_to or user.get("email") or "").strip()
    profile = await get_profile(db, uid)
    subject, text, body_html = render(items, roles_for(profile, s), get_settings().frontend_url.rstrip("/"))
    integ = await db[c.INTEGRATIONS].find_one({"user_id": uid, "provider": "gmail", "method": "app_password"})
    if not integ or not EMAIL_RE.match(to):
        await notify(db, user_id=uid, kind="career_jobs", title=subject[7:], link="/careers",
                     body="Connect Gmail with an App Password in Integrations to also get this by email.",
                     details=[{"platform": d["company"], "field": d["title"], "after": f"{d['score']}%"} for d in items[:5]])
        return {"sent": 0, "notified": len(items), "error": "Connect Gmail with an App Password (Settings → Integrations) to get it by email."}
    try:
        mid = await smtp.send(integ["email"], crypto.decrypt(integ["app_password_enc"]), "Saige AI", to, subject, text, html=body_html)
    except GmailError as exc:
        return {"sent": 0, "error": str(exc)}
    await db[c.CAREER_JOBS].update_many({"_id": {"$in": [d["_id"] for d in items]}}, {"$set": {"emailed_at": utcnow()}})
    await log_action(db, user_id=uid, action="careers.digest_sent", entity="career_jobs",
                     details={"to": to, "jobs": len(items), "trigger": trigger, "message_id": mid})
    return {"sent": len(items), "to": to}

"""Career jobs email digest, sent to the user's own inbox.

It goes to the user (the account email, or `careers.digest_to`), never to a third party, so it isn't an
outward action that needs per-message approval; the user turns it on or off in Career jobs settings, and
the `emails` pause stops it. It is sent from the user's Gmail through the App Password connection. Each
posting is included once (`emailed_at`).
"""

import html
import re
from datetime import timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.automation.service import get_settings_doc, is_allowed
from app.careers.service import FIT_LABEL, roles_for
from app.config import get_settings
from app.database import collections as c
from app.email import outbound
from app.profiles.service import get_profile
from app.services.audit import log_action
from app.services.notify import notify
from app.utils import as_utc, utcnow

MAX_ITEMS = 25
MAIL_BACKOFF = timedelta(minutes=30)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)


async def pending(db: AsyncIOMotorDatabase, uid: str, *, min_score: int, locations: list[str], limit: int = MAX_ITEMS,
                  include_sent: bool = False, categories: list[str] | None = None, exp_years: float | None = None,
                  min_salary_lpa: float | None = None) -> list[dict]:
    q: dict = {"user_id": uid, "active": True, "score": {"$gte": min_score}}
    extra: list[dict] = []
    if categories:
        q["category"] = {"$in": categories}
    if exp_years is not None:
        extra.append({"$or": [{"exp_min": None}, {"exp_min": {"$lte": exp_years}}]})
    if min_salary_lpa:
        extra.append({"$or": [{"salary_lpa": None}, {"salary_lpa": {"$gte": min_salary_lpa}}]})
    if extra:
        q["$and"] = extra
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


def _pill(score: int) -> str:
    bg = "#e8f5ec" if score >= 85 else "#fff4e5" if score >= 70 else "#f3f4f6"
    fg = "#137333" if score >= 85 else "#b45309" if score >= 70 else "#4b5563"
    return (f"<span style='display:inline-block;min-width:54px;text-align:center;padding:8px 10px;border-radius:14px;background:{bg};"
            f"color:{fg};font-size:18px;font-weight:700'>{score}%</span>")


def render(items: list[dict], roles: list[str], app_url: str) -> tuple[str, str, str]:
    """Premium job-alert email: summary numbers, ranked cards with why-it-fits, matched skills and one clear action each."""
    e = html.escape
    n = len(items)
    top = max(items, key=lambda d: d["score"]) if items else None
    companies = len({d["company"] for d in items})
    subject = (f"{n} new {'job' if n == 1 else 'jobs'} for {', '.join(roles[:2])} on company career pages"
               + (f" · top match {top['score']}% at {top['company']}" if top else ""))
    text = [f"{n} new opening(s) on company career pages that fit your profile.", ""]
    cards = []
    for d in items:
        where = d.get("location") or ("Remote" if d.get("remote") else "Location not listed")
        url = d.get("url") or d.get("careers_url") or ""
        text += [f"{d['score']}%  {d['title']} at {d['company']} ({where})", f"    {FIT_LABEL.get(d.get('fit', ''), '')}",
                 f"    {_gap_line(d)}" if _gap_line(d) else "", f"    Apply: {url}", ""]
        meta = " · ".join(e(x) for x in [d["company"], where, f"posted {d['posted']}" if d.get("posted") else "", d.get("salary_text") or ""] if x)
        chips = "".join(f"<span style='display:inline-block;margin:0 6px 6px 0;padding:4px 10px;border-radius:99px;background:#fbeaec;color:#b8102e;"
                        f"font-size:12px'>{e(s)}</span>" for s in (d.get("matched_skills") or [])[:6])
        gaps = ", ".join(e(s) for s in (d.get("missing_skills") or [])[:4])
        cards.append(
            "<tr><td style='padding:0 0 14px'><table role='presentation' width='100%' style='border-collapse:separate;background:#ffffff;"
            "border:1px solid #f0dfe1;border-radius:18px'><tr><td style='padding:18px 20px'>"
            f"<div style='font-size:17px;font-weight:600;color:#1f1a1b;line-height:1.35'>{e(d['title'])}</div>"
            f"<div style='color:#6b5f61;font-size:13px;margin:4px 0 10px'>{meta}</div>"
            f"<div style='color:#1f1a1b;font-size:13px;margin-bottom:10px'>{e(FIT_LABEL.get(d.get('fit', ''), ''))}</div>"
            + (f"<div>{chips}</div>" if chips else "")
            + (f"<div style='color:#6b5f61;font-size:12px;margin-top:4px'>Worth brushing up: {gaps}</div>" if gaps else "")
            + f"<div style='margin-top:14px'><a href='{e(url)}' style='display:inline-block;background:#b8102e;color:#ffffff;text-decoration:none;"
            "padding:10px 18px;border-radius:12px;font-size:14px;font-weight:600'>View &amp; apply</a>"
            f"<a href='{e(app_url)}/careers' style='margin-left:14px;color:#b8102e;font-size:13px;text-decoration:none'>Tailor my resume →</a></div>"
            f"</td><td style='padding:18px 20px 0 0;vertical-align:top;text-align:right;width:70px'>{_pill(d['score'])}</td></tr></table></td></tr>")
    text += [f"See every job, filters and resume advice: {app_url}/careers"]
    stat = ("<td style='padding:14px;background:#ffffff;border:1px solid #f0dfe1;border-radius:16px;text-align:center'>"
            "<div style='font-size:24px;font-weight:700;color:#b8102e'>{}</div><div style='font-size:12px;color:#6b5f61'>{}</div></td>")
    stats = ("<table role='presentation' width='100%' style='border-collapse:separate;border-spacing:10px 0;margin:0 -10px 18px'><tr>"
             + stat.format(n, "new jobs") + stat.format(f"{top['score']}%" if top else "–", "top match") + stat.format(companies, "companies")
             + "</tr></table>")
    body_html = (
        "<div style='background:#fbf6f6;padding:28px 12px;font-family:Google Sans,Segoe UI,Arial,sans-serif'>"
        "<div style='max-width:640px;margin:0 auto'>"
        "<div style='font-size:20px;font-weight:700;color:#1f1a1b;margin-bottom:4px'>Saige <span style='color:#b8102e'>AI</span></div>"
        f"<div style='font-size:28px;font-weight:300;color:#1f1a1b;letter-spacing:-.02em;margin:14px 0 4px'>Fresh openings picked for you</div>"
        f"<div style='color:#6b5f61;font-size:14px;margin-bottom:18px'>For {e(', '.join(roles))} · scored against your verified profile</div>"
        f"{stats}<table role='presentation' width='100%' style='border-collapse:collapse'>{''.join(cards)}</table>"
        f"<div style='text-align:center;margin:22px 0'><a href='{e(app_url)}/careers' style='display:inline-block;background:#1f1a1b;color:#ffffff;"
        "text-decoration:none;padding:12px 22px;border-radius:14px;font-size:14px;font-weight:600'>See all jobs in Saige</a></div>"
        f"<div style='text-align:center;color:#9a8f91;font-size:12px;line-height:1.6'>Matches use only facts in your profile. "
        f"<a href='{e(app_url)}/alerts' style='color:#9a8f91'>Change alert settings</a></div></div></div>")
    return subject, "\n".join(t for t in text if t is not None), body_html


async def send(db: AsyncIOMotorDatabase, uid: str, *, trigger: str = "manual", test: bool = False) -> dict:
    """Email the new career-portal matches. `test` re-sends the current top matches even if already emailed."""
    from app.email.gmail import GmailError

    s = await get_settings_doc(db, uid)
    if trigger != "manual" and not s.careers.email_digest:
        return {"skipped": "email digest off"}
    if not await is_allowed(db, uid, "emails"):
        return {"skipped": "emails paused"}
    items = await pending(db, uid, min_score=s.careers.min_score, locations=s.careers.locations, include_sent=test,
                          categories=s.careers.categories, exp_years=s.careers.exp_years, min_salary_lpa=s.careers.min_salary_lpa)
    if not items:
        return {"sent": 0, "reason": "no new matches above your threshold"}
    user = await db[c.USERS].find_one({"_id": uid}, {"email": 1}) or {}
    to = (s.careers.digest_to or user.get("email") or "").strip()
    profile = await get_profile(db, uid)
    subject, text, body_html = render(items, roles_for(profile, s), get_settings().frontend_url.rstrip("/"))
    integ = await outbound.find_sender(db, uid)
    if not integ or not EMAIL_RE.match(to):
        await notify(db, user_id=uid, kind="career_jobs", title=subject[7:], link="/careers",
                     body="Connect Gmail with an App Password in Integrations to also get this by email.",
                     details=[{"platform": d["company"], "field": d["title"], "after": f"{d['score']}%"} for d in items[:5]])
        return {"sent": 0, "notified": len(items), "error": "Connect Gmail with an App Password (Settings → Integrations) to get it by email."}
    # After a failed send, automatic runs wait MAIL_BACKOFF before logging in to Gmail again: retrying every
    # 30 s makes Gmail throttle the account, and then it drops every connection ("Connection unexpectedly closed").
    state = (await db[c.SYSTEM_SETTINGS].find_one({"user_id": uid}, {"careers_mail": 1}) or {}).get("careers_mail") or {}
    if trigger != "manual" and state.get("retry_after") and as_utc(state["retry_after"]) > utcnow():
        return {"sent": 0, "skipped": "waiting after a Gmail error", "retry_after": as_utc(state["retry_after"]).isoformat()}
    try:
        mid = await outbound.send(integ, "Saige AI", to, subject, text, html=body_html)
    except GmailError as exc:
        await db[c.SYSTEM_SETTINGS].update_one({"user_id": uid}, {"$set": {"careers_mail": {
            "retry_after": utcnow() + MAIL_BACKOFF, "error": str(exc)[:300]}}}, upsert=True)
        msg = str(exc)
        if "unexpectedly closed" in msg:
            msg = ("Gmail is refusing logins for a while, usually after many attempts in a short time. Saige will try again "
                   "in 30 minutes. If it keeps failing, create a new App Password and reconnect Gmail in Integrations.")
        return {"sent": 0, "error": msg}
    await db[c.SYSTEM_SETTINGS].update_one({"user_id": uid}, {"$unset": {"careers_mail": ""}})
    await db[c.CAREER_JOBS].update_many({"_id": {"$in": [d["_id"] for d in items]}}, {"$set": {"emailed_at": utcnow()}})
    await log_action(db, user_id=uid, action="careers.digest_sent", entity="career_jobs",
                     details={"to": to, "jobs": len(items), "trigger": trigger, "message_id": mid})
    return {"sent": len(items), "to": to}

"""Job Match Radar: today's best-fit jobs, merged from the Jobs-for-you feed and the career-portal jobs.

Nothing is re-scored here. Scores, matched skills and missing skills come from the existing 9-dimension matching
(`jobs.discover.score`, stored in the feed and in `career_jobs`); the "why you fit" reasons are built only from that
output (matched skills are matched against the verified profile), so no reason is invented.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.automation.service import get_settings_doc, is_allowed
from app.careers import digest
from app.careers.service import FIT_LABEL, fit_for, roles_for
from app.config import get_settings
from app.database import collections as c
from app.email import outbound
from app.jobs import feed
from app.jobs.dedupe import canonical_url
from app.profiles.service import get_profile
from app.services.agent_runs import agent_run
from app.services.audit import log_action
from app.services.notify import notify

DEFAULT_TOP = 12
MAX_TOP = 30
SCOPE_REASON = {"country": "Located in your country", "remote": "Open to remote work"}


def reasons_for(it: dict) -> list[str]:
    """Up to 3 reasons, each taken from the matching output of this job (never invented)."""
    out: list[str] = []
    skills = [s for s in it.get("matched_skills") or [] if s][:4]
    if skills:
        out.append("Your verified skills match: " + ", ".join(skills))
    label = FIT_LABEL.get(it.get("fit") or "", "")
    if label:
        out.append(label)
    elif it.get("classification"):
        out.append(f"Match rating: {it['classification']}")
    if it.get("ai_score") is not None:
        out.append(f"Saige learning rates it {it['ai_score']}% from your feedback")
    if it.get("scope") in SCOPE_REASON:
        out.append(SCOPE_REASON[it["scope"]])
    return out[:3]


def _key(it: dict) -> str:
    url = it.get("url") or ""
    if url:
        return canonical_url(url)
    return f"{(it.get('company') or '').lower()}|{(it.get('title') or '').lower()}"


def _row(it: dict, origin: str) -> dict:
    score = int(it.get("score") or 0)
    return {
        "id": str(it.get("id") or it.get("_id") or _key(it)),
        "origin": origin,
        "title": it.get("title") or "",
        "company": it.get("company") or "",
        "location": it.get("location") or ("Remote" if it.get("remote") else None),
        "source": it.get("source_label") or feed.SOURCE_LABEL.get(it.get("source") or "", it.get("source") or ""),
        "url": it.get("url") or it.get("careers_url") or "",
        "score": score,
        "ai_score": it.get("ai_score"),
        "fit": it.get("fit") or fit_for(score),
        "classification": it.get("classification"),
        "scope": it.get("scope"),
        "matched_skills": list(it.get("matched_skills") or [])[:8],
        "missing_skills": list(it.get("missing_skills") or [])[:5],
        "reasons": reasons_for(it),
        "posted": it.get("posted"),
    }


async def radar(db: AsyncIOMotorDatabase, uid: str, *, top: int = DEFAULT_TOP) -> dict:
    top = max(1, min(top, MAX_TOP))
    doc = await db[c.JOB_FEED].find_one({"_id": uid}) or {}
    feed_items = [it for it in doc.get("items") or [] if it.get("scope") != "abroad"]
    career = await db[c.CAREER_JOBS].find({"user_id": uid, "active": True}, {"description": 0}).sort("score", -1).to_list(300)
    merged: dict[str, dict] = {}
    for it in feed_items:
        merged[_key(it)] = _row(it, "feed")
    for it in career:
        if it.get("scope") == "abroad":
            continue
        merged[_key(it)] = _row(it, "careers")  # the career-portal copy carries fit + ai_score
    rows = sorted(merged.values(), key=lambda r: (-r["score"], -(r["ai_score"] or 0), r["company"], r["title"]))
    return {"generated_from": {"feed": len(feed_items), "careers": len(career)}, "total": len(rows), "items": rows[:top]}


async def send_test_digest(db: AsyncIOMotorDatabase, uid: str) -> dict:
    """Email today's top 5 to the user's own account address (never anyone else)."""
    from app.email.gmail import GmailError

    if not await is_allowed(db, uid, "emails"):
        return {"sent": 0, "skipped": "emails paused"}
    async with agent_run(db, "job_match_radar", uid, {"action": "digest_test"}) as run:
        items = (await radar(db, uid, top=5))["items"]
        run.output = {"jobs": len(items)}
        if not items:
            return {"sent": 0, "reason": "no matching jobs yet"}
        user = await db[c.USERS].find_one({"_id": uid}, {"email": 1}) or {}
        to = (user.get("email") or "").strip()
        s = await get_settings_doc(db, uid)
        profile = await get_profile(db, uid)
        subject, text, body_html = digest.render(items, roles_for(profile, s), get_settings().frontend_url.rstrip("/"))
        subject = "Job Match Radar: " + subject
        integ = await outbound.find_digest_sender(db, uid)
        if not integ or not digest.EMAIL_RE.match(to):
            await notify(db, user_id=uid, kind="job_radar", title=f"Your top {len(items)} matches today", link="/radar",
                         body="Connect Gmail with an App Password in Integrations to also get this by email.",
                         details=[{"platform": d["company"], "field": d["title"], "after": f"{d['score']}%"} for d in items])
            run.action("notified in app (no sender connected)")
            return {"sent": 0, "notified": len(items), "error": "Connect Gmail with an App Password (Settings → Integrations) to get it by email."}
        try:
            mid = await outbound.send(integ, integ.get("from_name") or "Saige AI", to, subject, text, html=body_html)
        except GmailError as exc:
            run.errors.append(str(exc)[:200])
            return {"sent": 0, "error": str(exc)}
        run.action(f"emailed top {len(items)} to the account address")
        await log_action(db, user_id=uid, action="radar.digest_sent", entity="job_radar",
                         details={"to": to, "jobs": len(items), "message_id": mid})
        return {"sent": len(items), "to": to}

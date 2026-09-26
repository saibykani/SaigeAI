"""Saige AI assistant: a chat that knows your job search (profile, jobs, applications, inbox, contacts).

With ANTHROPIC_API_KEY set it answers with Claude, grounded in a summary of your own records; without
it, a built-in assistant answers the common questions from the same data. Either way it never invents
facts about you: anything not in your verified profile is described as unknown.
"""

import re

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from pymongo import DESCENDING

from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.profiles.service import get_profile
from app.services.rate_limit import RateLimiter
from app.utils import utcnow

router = APIRouter(prefix="/assistant", tags=["assistant"])
limiter = RateLimiter(max_calls=30, window_seconds=60)


class Msg(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class ChatIn(BaseModel):
    messages: list[Msg] = Field(min_length=1, max_length=30)


async def context(db: AsyncIOMotorDatabase, uid: str) -> dict:
    p = await get_profile(db, uid)
    apps: dict[str, int] = {}
    async for a in db[c.APPLICATIONS].find({"user_id": uid}, {"status": 1}):
        apps[a["status"]] = apps.get(a["status"], 0) + 1
    feed = await db[c.JOB_FEED].find_one({"_id": uid}, {"items": {"$slice": 8}, "country": 1, "roles": 1}) or {}
    upcoming = [i async for i in db[c.INTERVIEWS].find({"user_id": uid, "scheduled_at": {"$gte": utcnow()}},
                                                        {"company": 1, "role": 1, "scheduled_at": 1}).sort("scheduled_at", 1).limit(5)]
    emails = [e async for e in db[c.EMAILS].find({"user_id": uid}, {"subject": 1, "category": 1, "sender": 1})
              .sort("received_at", DESCENDING).limit(8)]
    drafts = await db[c.OUTREACH].count_documents({"user_id": uid, "status": "draft"})
    return {
        "profile": {"name": p.personal.name, "role": p.personal.current_designation, "years": p.personal.total_experience_years,
                    "location": p.personal.current_location, "country": p.personal.country,
                    "notice_days": p.personal.notice_period_days, "target_roles": p.preferences.target_roles,
                    "skills": list(p.skills.all())[:25]},
        "applications": apps,
        "top_jobs": [{"title": i.get("title"), "company": i.get("company"), "score": i.get("score"), "location": i.get("location"),
                      "url": i.get("url")} for i in feed.get("items", [])],
        "upcoming_interviews": [{"company": i.get("company"), "role": i.get("role"), "at": i["scheduled_at"].isoformat()} for i in upcoming],
        "recent_emails": [{"subject": e["subject"][:100], "category": e["category"]} for e in emails],
        "reply_drafts_waiting": drafts,
    }


SYSTEM = """You are Saige, the AI career assistant inside Saige AI, helping one job seeker.
Use ONLY the facts in <records> about the user. Never invent skills, employers, numbers or results; if something
isn't in the records, say you don't know and suggest where to add it (Profile). Be concise, warm and practical.
When useful, point to the right place in the app: Jobs (Jobs for you, auto-applier), Applications (Ready to approve),
Resumes (ATS scorer, Resume health), Recruiters (contacts, templates, Find people), Inbox, LinkedIn & Naukri,
Settings (Alerts & templates, Integrations, Agent). You can draft messages, interview answers and plans, but you
cannot send anything or apply yourself: the user approves actions in the app.
<records>
{records}
</records>"""

ACTIONS = {
    "jobs": ("Open Jobs for you", "/jobs"), "apply": ("Ready to approve", "/applications"), "resume": ("Resume health & ATS", "/resumes"),
    "recruiters": ("Recruiters", "/recruiters"), "people": ("Find people", "/recruiters?tab=find"), "inbox": ("Inbox", "/inbox"),
    "profile": ("Profile", "/profile"), "whatsapp": ("Alerts & templates", "/alerts"), "templates": ("Templates", "/alerts"),
    "linkedin": ("LinkedIn & Naukri", "/profiles"), "interviews": ("Interviews", "/interviews"),
}


def actions_for(text: str) -> list[dict]:
    t = text.lower()
    keys = [k for k, words in {
        "jobs": ("job", "role", "opening", "match"), "apply": ("apply", "application"), "resume": ("resume", "cv", "ats"),
        "people": ("recruiter", "hr", "referral", "manager", "contact"), "inbox": ("email", "mail", "inbox"),
        "templates": ("template", "message", "whatsapp"), "linkedin": ("linkedin", "naukri", "headline"),
        "interviews": ("interview",), "profile": ("profile", "skill", "ctc", "notice"),
    }.items() if any(w in t for w in words)]
    return [{"label": ACTIONS[k][0], "href": ACTIONS[k][1]} for k in keys[:3]]


def builtin(question: str, ctx: dict) -> str:
    """Answers without an LLM, from the same records."""
    q = question.lower()
    p = ctx["profile"]
    if re.search(r"\b(job|jobs|match|opening|role)s?\b", q) and ctx["top_jobs"]:
        lines = [f"• {j['title']} at {j['company']} — {j['score']}% match ({j.get('location') or 'location n/a'})" for j in ctx["top_jobs"][:5]]
        return "Your best matches right now:\n" + "\n".join(lines) + "\n\nSelect them in Jobs → Jobs for you and click Auto-apply."
    if "interview" in q:
        if not ctx["upcoming_interviews"]:
            return "No upcoming interviews yet. When an invite arrives in Gmail, Saige adds it to Interviews automatically."
        rows = [f"• {i['company']} · {i['role']} · {i['at'][:16].replace('T', ' ')}" for i in ctx["upcoming_interviews"]]
        return "Upcoming interviews:\n" + "\n".join(rows)
    if "application" in q or "applied" in q or "status" in q:
        if not ctx["applications"]:
            return "You have no applications yet. Pick jobs in Jobs for you and click Auto-apply to prepare them."
        return "Your applications by stage:\n" + "\n".join(f"• {k.replace('_', ' ').title()}: {v}" for k, v in ctx["applications"].items())
    if re.search(r"\b(ctc|salary|notice)\b", q):
        return (f"From your profile: notice period {p['notice_days'] if p['notice_days'] is not None else 'not set'} days. "
                "Add current and expected CTC in Profile so replies to recruiters can include them.")
    if "email" in q or "mail" in q or "inbox" in q:
        if not ctx["recent_emails"]:
            return "No emails imported yet. Connect Gmail in Settings → Integrations; Saige syncs every minute while it's open."
        return "Latest job emails:\n" + "\n".join(f"• [{e['category']}] {e['subject']}" for e in ctx["recent_emails"][:6])
    if "skill" in q:
        return f"Your verified skills: {', '.join(p['skills']) or 'none yet'}. Add more in Profile (only ones you can back up)."
    return (f"Hi {(p['name'] or 'there').split()[0]}! I can show your best job matches, application status, upcoming interviews, "
            "latest recruiter emails and your skills, and point you to the right tool. Ask me e.g. “What are my best jobs today?”. "
            "For drafted messages and interview prep, the full AI mode turns on when the server has an Anthropic API key.")


@router.post("/chat", dependencies=[Depends(limiter.dependency("assistant"))])
async def chat(body: ChatIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    import json

    from app.agents.llm import get_provider

    ctx = await context(db, user["_id"])
    question = body.messages[-1].content
    provider = get_provider()
    reply, engine = None, "builtin"
    if provider is not None and hasattr(provider, "chat"):
        reply = await provider.chat(system=SYSTEM.format(records=json.dumps(ctx, default=str)[:12000]),
                                    messages=[m.model_dump() for m in body.messages[-16:]])
        engine = "claude" if reply else engine
    if not reply:
        reply = builtin(question, ctx)
    return {"reply": reply, "engine": engine, "actions": actions_for(question + " " + reply)}

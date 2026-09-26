"""Jobs from the portal job-alert emails that already arrive in the user's Gmail.

LinkedIn, Naukri, Indeed and similar portals don't allow automated searching, but they email their
members job alerts. With the user's Gmail connected, Saige reads those alerts (read-only) and lists
each job with its link. The user opens the posting on the portal to apply.
"""

import re
from datetime import timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import collections as c
from app.utils import new_id, utcnow

# portal key -> sender domains
PORTALS: dict[str, tuple[str, ...]] = {
    "linkedin": ("linkedin.com",), "naukri": ("naukri.com",), "indeed": ("indeed.com", "indeedemail.com"),
    "foundit": ("foundit.in", "monsterindia.com"), "glassdoor": ("glassdoor.com", "glassdoor.co.in"),
    "instahyre": ("instahyre.com",), "hirist": ("hirist.tech", "hirist.com"), "cutshort": ("cutshort.io",),
    "wellfound": ("wellfound.com", "angel.co"), "shine": ("shine.com",), "iimjobs": ("iimjobs.com",),
    "timesjobs": ("timesjobs.com",), "internshala": ("internshala.com",), "apna": ("apna.co",),
}
ALERT_QUERY = "newer_than:21d from:(" + " OR ".join(d for ds in PORTALS.values() for d in ds) + ")"

JOB_URL = re.compile(
    r"https?://(?:[\w-]+\.)*(?:"
    r"linkedin\.com/(?:comm/)?jobs/view/\d+"
    r"|naukri\.com/(?:job-listings-[^\s\"'<>)]+|[^\s\"'<>)]*jid=\d+[^\s\"'<>)]*)"
    r"|indeed\.(?:com|co\.in)/(?:viewjob|rc/clk|pagead/clk|m/viewjob)[^\s\"'<>)]*"
    r"|(?:foundit\.in|glassdoor\.[\w.]+|instahyre\.com|hirist\.(?:tech|com)|cutshort\.io|wellfound\.com|shine\.com"
    r"|iimjobs\.com|timesjobs\.com|internshala\.com|apna\.co)/[^\s\"'<>)]*job[^\s\"'<>)]*"
    r")", re.I)
NOISE = re.compile(r"^(view job|apply( now)?|see (all|more) jobs?|easy apply|new|actively recruiting|promoted|be an early applicant"
                   r"|\d+ (applicants?|connections?)|posted .*|unsubscribe.*|https?://\S+|[-–•|·]+)$"
                   r"|job alert|jobs? (for you|matching|you may|based on)|new jobs?\b|recommended for you", re.I)
EXP = re.compile(r"^\d+\s*(-|to)?\s*\d*\s*(yrs?|years)\b", re.I)


def portal_for(sender: str) -> str | None:
    s = (sender or "").lower()
    for key, domains in PORTALS.items():
        if any(d in s for d in domains):
            return key
    return None


def parse(sender: str, subject: str, body: str) -> list[dict]:
    """Each job link with the few lines of text before it (title, company, location)."""
    portal = portal_for(sender)
    if not portal:
        return []
    lines = [ln.strip() for ln in (body or "").splitlines()]
    items, seen, prev_end = [], set(), 0
    for i, line in enumerate(lines):
        m = JOB_URL.search(line)
        if not m:
            continue
        url = m.group(0).rstrip(".,;")
        key = url.split("?")[0].lower()
        if key in seen:
            prev_end = i + 1
            continue
        seen.add(key)
        before = line[: m.start()].strip(" :-–|")
        block = [ln for ln in lines[max(prev_end, i - 6): i] if ln and len(ln) <= 140]
        if before:
            block.append(before)
        exp = next((ln for ln in block if EXP.match(ln)), None)
        cands = [ln for ln in block if not NOISE.search(ln) and not EXP.match(ln)]
        prev_end = i + 1
        if not cands:
            continue
        title, rest = cands[0], cands[1:]
        company = rest[0] if rest else ""
        location = rest[1] if len(rest) > 1 else None
        desc = "\n".join([title, company, location or "", exp or "", f"From your {portal.title()} job alert: {subject}"])
        items.append({"source": portal, "source_job_id": key[-120:], "title": title[:200], "company": company[:200],
                      "location": location, "remote": None, "url": url, "description": desc.strip()})
    return items[:40]


async def store(db: AsyncIOMotorDatabase, uid: str, messages: list[dict]) -> int:
    """Save parsed alerts (one doc per email); returns the number of jobs found."""
    found = 0
    for m in messages:
        items = parse(m.get("sender", ""), m.get("subject", ""), m.get("body", ""))
        await db[c.JOB_ALERTS].update_one(
            {"user_id": uid, "gmail_id": m.get("gmail_id")},
            {"$setOnInsert": {"_id": new_id(), "portal": portal_for(m.get("sender", "")), "subject": m.get("subject", "")[:200],
                              "items": items, "received_ms": m.get("received_ms"), "created_at": utcnow()}},
            upsert=True)
        found += len(items)
    return found


async def recent_items(db: AsyncIOMotorDatabase, uid: str, days: int = 21) -> list[dict]:
    since = utcnow() - timedelta(days=days)
    out: list[dict] = []
    async for d in db[c.JOB_ALERTS].find({"user_id": uid, "created_at": {"$gte": since}}).sort("created_at", -1).limit(60):
        out.extend(d.get("items", []))
    return out

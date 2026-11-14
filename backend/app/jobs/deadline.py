"""Application deadline read from a job description ("Apply by 30 Nov", "Last date to apply: 2026-12-05"),
and daily reminders for saved jobs whose deadline is close. Dates come only from the posting text."""

import re
from datetime import date, datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import collections as c
from app.services.notify import notify

_CUE = re.compile(
    r"(?:apply\s+(?:by|before|until)|last\s+date(?:\s+to\s+apply)?|closing\s+date|application\s+deadline|applications?\s+close[sd]?(?:\s+on)?|"
    r"deadline(?:\s+to\s+apply)?|apply\s+no\s+later\s+than)\s*[:\-–]?\s*([^\n.;]{4,40})", re.I)
_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def _parse(s: str, today: date) -> date | None:
    s = s.strip().lower().replace(",", " ")
    if m := re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s):
        y, mo, d = map(int, m.groups())
    elif m := re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", s):  # Indian order: day/month/year
        d, mo, y = map(int, m.groups())
        y += 2000 if y < 100 else 0
    elif m := re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]{3})[a-z]*\.?\s*(\d{4})?", s):
        d, mo, y = int(m.group(1)), _MONTHS.get(m.group(2)), int(m.group(3)) if m.group(3) else None
    elif m := re.search(r"([a-z]{3})[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?\s*(\d{4})?", s):
        mo, d, y = _MONTHS.get(m.group(1)), int(m.group(2)), int(m.group(3)) if m.group(3) else None
    else:
        return None
    if not mo:
        return None
    try:
        out = date(y or today.year, mo, d)
    except ValueError:
        return None
    if y is None and out < today - timedelta(days=30):  # "30 Jan" written in December means next year
        out = date(today.year + 1, mo, d)
    return out


def extract_deadline(text: str, today: date | None = None) -> date | None:
    today = today or date.today()
    for m in _CUE.finditer((text or "")[:20000]):
        if d := _parse(m.group(1), today):
            return d
    return None


async def remind(db: AsyncIOMotorDatabase, uid: str, now: datetime) -> int:
    """Notify once a day about saved jobs (not yet applied) that close within 3 days."""
    today = now.date()
    soon = []
    async for j in db[c.JOBS].find({"user_id": uid, "deadline": {"$ne": None}, "status": {"$nin": ["applied", "hidden", "archived"]}},
                                   {"title": 1, "company": 1, "deadline": 1, "deadline_reminded_on": 1}):
        d = j["deadline"]
        d = d.date() if isinstance(d, datetime) else d if isinstance(d, date) else _parse(str(d), today)
        if d and 0 <= (d - today).days <= 3 and j.get("deadline_reminded_on") != today.isoformat():
            soon.append((j, (d - today).days))
    for j, left in soon:
        when = "today" if left == 0 else "tomorrow" if left == 1 else f"in {left} days"
        await notify(db, user_id=uid, kind="deadline", title=f"Applications close {when}: {j.get('title')} at {j.get('company')}",
                     body="Apply before the deadline, or hide the job if you're not interested.", link=f"/jobs/{j['_id']}")
        await db[c.JOBS].update_one({"_id": j["_id"]}, {"$set": {"deadline_reminded_on": today.isoformat()}})
    return len(soon)

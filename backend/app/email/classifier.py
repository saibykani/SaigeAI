"""Job-search email classification and extraction (spec section 21).

Deterministic rules over subject + body, ordered so the most decisive signals win (an offer email
that also says "interview" is an Offer). Extraction pulls company, interview date/time, meeting
link and deadlines. Everything extracted is read from the email text itself.
"""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

CATEGORIES = ["Application Confirmation", "Recruiter Outreach", "Recruiter Reply", "Interview Invitation",
              "Interview Reschedule", "Assessment", "Coding Test", "Rejection", "Offer", "Follow-up", "Other"]

_RULES: list[tuple[str, list[str]]] = [
    ("Offer", [r"\boffer letter\b", r"\bpleased to (extend|offer)\b", r"\boffer of employment\b", r"\bjob offer\b",
               r"\bextend(ing)? (you )?an offer\b"]),
    ("Rejection", [r"\bunfortunately\b", r"\bnot (be )?moving forward\b", r"\bdecided to (move|proceed) forward with other",
                   r"\bwill not be (proceeding|moving)\b", r"\bregret to inform\b", r"\bnot selected\b",
                   r"\bother candidates (whose|who)\b", r"\bposition has been filled\b"]),
    ("Interview Reschedule", [r"\breschedul", r"\bnew (time|slot|date)\b", r"\bmoved (your|the) interview\b"]),
    ("Coding Test", [r"\bhackerrank\b", r"\bcodility\b", r"\bleetcode\b", r"\bcodesignal\b", r"\bcoding (test|challenge|round|assessment)\b"]),
    ("Assessment", [r"\bassessment\b", r"\btake[- ]home\b", r"\bonline test\b", r"\baptitude test\b", r"\bassignment\b"]),
    ("Interview Invitation", [r"\binterview\b", r"\bschedule (a|an|your) (call|chat|meeting)\b", r"\bcalendly\.com\b",
                              r"\binvite you (to|for)\b", r"\bnext round\b", r"\bmeet the team\b"]),
    ("Application Confirmation", [r"\bthank(s| you) for (applying|your application|your interest)\b",
                                  r"\bapplication (has been )?(received|submitted)\b", r"\bwe (have )?received your application\b",
                                  r"\bsuccessfully applied\b", r"\byour application (for|to)\b"]),
    ("Recruiter Outreach", [r"\bcame across your profile\b", r"\bare you open to\b", r"\bexciting opportunity\b",
                            r"\bwould you be interested\b", r"\bi('| a)m a (recruiter|talent)\b", r"\breaching out\b"]),
    ("Follow-up", [r"\bfollowing up\b", r"\bchecking in\b", r"\bgentle reminder\b", r"\bjust a reminder\b"]),
]

_MEETING = re.compile(
    r"https?://(?:meet\.google\.com/[a-z0-9-]+|[a-z0-9.-]*zoom\.us/[^\s)>\"]+|teams\.microsoft\.com/[^\s)>\"]+"
    r"|[a-z0-9.-]*webex\.com/[^\s)>\"]+|calendly\.com/[^\s)>\"]+)", re.I)
_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_TZ = {"ist": "Asia/Kolkata", "pst": "America/Los_Angeles", "pdt": "America/Los_Angeles", "est": "America/New_York",
       "edt": "America/New_York", "gmt": "UTC", "utc": "UTC", "bst": "Europe/London", "cet": "Europe/Berlin",
       "sgt": "Asia/Singapore", "gst": "Asia/Dubai"}
_DATE_TEXT = re.compile(
    r"(?:(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*,?\s+)?(?:(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,9})|([a-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?)"
    r",?\s*(\d{4})?", re.I)
_DATE_NUM = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b|\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_TIME = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b|\b([01]?\d|2[0-3]):([0-5]\d)\b", re.I)
_TZ_TOKEN = re.compile(r"\b(IST|PST|PDT|EST|EDT|GMT|UTC|BST|CET|SGT|GST)\b")


def classify(subject: str, body: str) -> tuple[str, float, list[str]]:
    text = f"{subject}\n{body}".lower()
    for category, patterns in _RULES:
        hits = [p for p in patterns if re.search(p, text)]
        if hits:
            in_subject = any(re.search(p, subject.lower()) for p in hits)
            return category, min(0.95, 0.6 + 0.15 * len(hits) + (0.15 if in_subject else 0)), hits
    return "Other", 0.3, []


def _date_parts(text: str, now: datetime) -> tuple[int, int, int] | None:
    for m in _DATE_TEXT.finditer(text):
        day, mon = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        month = _MONTHS.get((mon or "")[:3].lower())
        if not month or not day or int(day) > 31:
            continue
        year = int(m.group(5)) if m.group(5) else now.year
        if not m.group(5) and (month, int(day)) < (now.month, now.day):
            year += 1  # "Oct 5" mentioned in December refers to next year
        return year, month, int(day)
    m = _DATE_NUM.search(text)
    if m:
        if m.group(1):
            return int(m.group(1)), int(m.group(2)), int(m.group(3))
        return int(m.group(6)), int(m.group(5)), int(m.group(4))  # dd/mm/yyyy (India/UK convention)
    low = text.lower()
    if "tomorrow" in low:
        d = now + timedelta(days=1)
        return d.year, d.month, d.day
    return None


def extract_datetime(text: str, default_tz: str, now: datetime | None = None) -> tuple[datetime | None, str]:
    """Interview date/time as an aware UTC datetime plus the timezone name used."""
    tz_name = default_tz
    tzm = _TZ_TOKEN.search(text)
    if tzm:
        tz_name = _TZ[tzm.group(1).lower()]
    tz = ZoneInfo(tz_name)
    now = now or datetime.now(tz)
    parts = _date_parts(text, now)
    tm = _TIME.search(text)
    if not parts or not tm:
        return None, tz_name
    if tm.group(3):
        hour = int(tm.group(1)) % 12 + (12 if tm.group(3).lower() == "pm" else 0)
        minute = int(tm.group(2) or 0)
    else:
        hour, minute = int(tm.group(4)), int(tm.group(5))
    try:
        local = datetime(parts[0], parts[1], parts[2], hour, minute, tzinfo=tz)
    except ValueError:
        return None, tz_name
    return local.astimezone(ZoneInfo("UTC")), tz_name


def extract(subject: str, body: str, sender: str, default_tz: str = "Asia/Kolkata") -> dict:
    text = f"{subject}\n{body}"
    meeting = _MEETING.search(text)
    when, tz = extract_datetime(text, default_tz)
    deadline = None
    dm = re.search(r"\b(?:by|before|deadline[:\s]+|due(?: date)?[:\s]+)\s*([^.\n]{3,40})", text, re.I)
    if dm:
        d, _ = extract_datetime(dm.group(1) + " 11:59 pm", default_tz)
        deadline = d.isoformat() if d else None
    name_m = re.match(r"\s*\"?([^\"<]+?)\"?\s*<([^>]+)>", sender)
    sender_name = name_m.group(1).strip() if name_m else None
    sender_email = (name_m.group(2) if name_m else sender).strip().lower()
    domain = sender_email.split("@")[-1] if "@" in sender_email else ""
    round_m = re.search(r"\b((?:technical|hr|managerial|final|first|second|third|1st|2nd|3rd)\s+(?:round|interview))\b", text, re.I)
    return {
        "sender_name": sender_name, "sender_email": sender_email, "sender_domain": domain,
        "interview_at": when.isoformat() if when else None, "timezone": tz,
        "meeting_url": meeting.group(0).rstrip(".,") if meeting else None,
        "deadline": deadline, "interview_round": round_m.group(1).title() if round_m else None,
    }

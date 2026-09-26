"""Emails from job portals (LinkedIn, Naukri, Indeed, ...) that arrive in the user's own Gmail.

Portals don't allow automated access to their sites, but they email their members: job alerts,
recruiter invites ("X from Acme invited you to apply"), InMail/message notifications, profile views
and application updates. Saige classifies those emails for the Inbox, lists their jobs in
Jobs → Job alerts, and adds the recruiters they name to Recruiters (source "portal"). Nothing is
fetched from the portals themselves.
"""

import re

from app.jobs.alerts import PORTALS, portal_for

PORTAL_QUERY = "newer_than:30d from:(" + " OR ".join(d for ds in PORTALS.values() for d in ds) + ")"
PORTAL_CATEGORIES = ("Job Alert", "Portal Invite", "Portal Message", "Profile View", "Application Update", "Portal Notification")

_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("Portal Invite", re.compile(r"invit(ed|es|ation) you to apply|wants you to apply|recruiter.{0,40}(invite|interested)|"
                                 r"interested in your profile|shortlisted you|job invite|you('| ha)ve been invited|apply invite", re.I)),
    ("Portal Message", re.compile(r"sent you a (new )?message|new message from|inmail|replied to your message|messaged you", re.I)),
    ("Profile View", re.compile(r"viewed your profile|appeared in \d+ searches|profile views?|recruiters? (viewed|searched)|"
                                r"who('s| has) viewed", re.I)),
    ("Application Update", re.compile(r"your application (was|has been|to)|application (viewed|sent|status)|you applied|"
                                      r"application for .{0,80} (was|has)", re.I)),
    ("Job Alert", re.compile(r"job alert|jobs? (for you|matching|you may|recommended)|new jobs?|recommended jobs?|"
                             r"jobs? based on|\d+\+? (new )?(jobs|openings)|hiring now", re.I)),
]

# "Priya Sharma from Acme Corp", "Priya Sharma, Talent Acquisition at Acme Corp"
_FROM_COMPANY = re.compile(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+){0,2}) (?:from|at) ([A-Z][\w&.\- ]{1,60}?)"
                           r"(?= (?:has|is|invited|wants|sent|viewed)\b|[,.\n])")
_TITLE_AT = re.compile(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+){0,2}),? ((?:Senior |Lead |Head of )?(?:HR|Talent[\w ]{0,30}|Recruit\w*[\w ]{0,20}|"
                       r"Hiring Manager|Technical Recruiter|People[\w ]{0,20}|Human Resources[\w ]{0,20})) (?:at|@) "
                       r"([A-Z][\w&.\- ]{1,60}?)(?=[,.\n]|$)")
PHONE_RE = re.compile(r"(?<![\d+])(?:\+91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d)|\+\d{1,3}[\s-]?\d{3,4}[\s-]?\d{3,4}[\s-]?\d{3,4}")


def category(sender: str, subject: str, body: str) -> str | None:
    """Portal email category, or None when the sender isn't a job portal."""
    if not portal_for(sender):
        return None
    head = f"{subject}\n{(body or '')[:1500]}"
    for name, pat in _RULES:
        if pat.search(head):
            return name
    return "Portal Notification"


def phones(text: str) -> list[str]:
    out = []
    for m in PHONE_RE.findall(text or ""):
        digits = re.sub(r"[^\d+]", "", m)
        if len(re.sub(r"\D", "", digits)) >= 10:
            out.append(digits)
    return list(dict.fromkeys(out))[:3]


def recruiter(sender: str, subject: str, body: str) -> dict | None:
    """The recruiter a portal invite / message names, with any contact details the email itself contains."""
    portal = portal_for(sender)
    if not portal:
        return None
    text = f"{subject}\n{(body or '')[:4000]}"
    m = _TITLE_AT.search(text)
    if m:
        name, title, company = m.group(1), m.group(2).strip(), m.group(3).strip()
    else:
        m = _FROM_COMPANY.search(text)
        if not m:
            return None
        name, title, company = m.group(1), None, m.group(2).strip()
    if name.lower() in {"team", "linkedin", "naukri", "indeed", "the", "your"} or len(company) < 2:
        return None
    emails = [e for e in re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", body or "")
              if portal_for(e) is None and not re.match(r"(no-?reply|notifications?|support|help)@", e, re.I)]
    return {"name": name[:120], "company": company.rstrip(" .")[:160], "title": title, "portal": portal,
            "email": emails[0].lower() if emails else None, "phone": (phones(body or "") or [None])[0]}

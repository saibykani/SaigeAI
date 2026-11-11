"""Apply by email: read a JD or a LinkedIn hiring post, find where to send, ask for missing facts, draft the email.

Everything in the email comes from the verified profile or from facts the user typed in when asked. Nothing is
sent from here: the router sends only after the user reviews the draft and clicks Send.
"""

import re

from app.profiles.experience import describe
from app.schemas.profile import Profile

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SKIP_EMAIL = re.compile(r"^(no-?reply|donotreply|notifications?|mailer-daemon|privacy|support)@", re.I)
SUBJECT_RE = re.compile(r"subject(?:\s+line)?\s*(?:as|:|-|should be|with)?\s*[\"'“‘]([^\"'”’\n]{3,100})[\"'”’]", re.I)

# Facts a hiring post often asks for: (key, label, profile field, words in the post that ask for it, input type)
FACTS = [
    ("phone", "Phone number", "phone", None, "text"),
    ("current_ctc", "Current CTC (LPA)", "current_ctc", r"\b(?:ctc|current\s+(?:salary|compensation|package))\b", "number"),
    ("expected_ctc", "Expected CTC (LPA)", "expected_ctc", r"\b(?:ectc|expected\s+(?:ctc|salary|compensation|package))\b", "number"),
    ("notice_period_days", "Notice period (days)", "notice_period_days", r"\b(?:notice\s+period|np|immediate\s+joiners?|joining)\b", "number"),
    ("current_location", "Current location", "current_location", r"\b(?:current\s+location|location|relocat\w*|based\s+in)\b", "text"),
]


def emails_in(text: str) -> list[str]:
    """Addresses in the post, the likely application address first (careers@/hr@/jobs@ before others)."""
    seen: dict[str, None] = {}
    for m in EMAIL_RE.findall(text or ""):
        e = m.strip(".").lower()
        if not SKIP_EMAIL.match(e):
            seen.setdefault(e, None)
    rank = ("career", "hr", "job", "talent", "hiring", "recruit", "resume", "cv")
    return sorted(seen, key=lambda e: (not any(e.startswith(r) or f".{r}" in e.split("@")[0] for r in rank), list(seen).index(e)))


def subject_asked(text: str) -> str | None:
    m = SUBJECT_RE.search(text or "")
    return m.group(1).strip() if m else None


def questions(profile: Profile, text: str) -> list[dict]:
    """Facts the post asks for (and the phone number, always) that aren't in the profile yet."""
    p, low, out = profile.personal, (text or "").lower(), []
    for key, label, field, pattern, kind in FACTS:
        if getattr(p, field) not in (None, "") or (pattern and not re.search(pattern, low)):
            continue
        out.append({"key": key, "label": label, "type": kind})
    if not p.total_experience_years and not profile.knowledge.experience:
        out.append({"key": "total_experience_years", "label": "Total experience (years)", "type": "number"})
    return out


def coerce(answers: dict) -> dict:
    """Typed answers -> personal-info patch. Blank answers are ignored."""
    nums = {"current_ctc", "expected_ctc", "total_experience_years"}
    patch: dict = {}
    for k, v in (answers or {}).items():
        v = str(v).strip()
        if not v or k not in {f[0] for f in FACTS} | {"total_experience_years"}:
            continue
        if k in nums:
            patch[k] = float(re.sub(r"[^\d.]", "", v) or 0)
        elif k == "notice_period_days":
            patch[k] = int(float(re.sub(r"[^\d.]", "", v) or 0))
        else:
            patch[k] = v[:120]
    return patch


def _lpa(v: float | None, cur: str | None) -> str | None:
    if v is None:
        return None
    return f"{v:g} LPA" if (cur or "INR").upper() == "INR" else f"{v:g} {cur}"


def draft(profile: Profile, title: str, company: str, skills: list[str], text: str) -> tuple[str, str]:
    """Subject and body. Uses the subject line the post asks for when it gives one."""
    p = profile.personal
    low = (text or "").lower()
    role = title or "the open"
    yrs = describe(p.total_experience_years) if p.total_experience_years else None
    subject = subject_asked(text) or f"Application for {title or 'the role'}" + (f" – {p.name}" if p.name else "")
    lines = ["Dear Hiring Team,", "",
             f"I came across your opening for {role} role" + (f" at {company}" if company else "") + " and would like to apply."]
    intro = []
    if p.current_designation:
        intro.append(f"I'm currently working as a {p.current_designation}" + (f" at {p.current_company}" if p.current_company else ""))
    if yrs:
        intro.append(f"with {yrs} of experience" if intro else f"I have {yrs} of experience")
    if intro:
        lines.append(" ".join(intro) + ".")
    if skills:
        lines.append(f"My hands-on experience includes {', '.join(skills[:6])}, which match what you're looking for.")
    npd = p.notice_period_days
    facts = [("Total experience", yrs), ("Current CTC", _lpa(p.current_ctc, p.ctc_currency)),
             ("Expected CTC", _lpa(p.expected_ctc, p.ctc_currency)),
             ("Notice period", None if npd is None else ("Immediate" if npd == 0 else f"{npd} days")),
             ("Current location", p.current_location)]
    asked = {f[0]: re.search(f[3], low) for f in FACTS if f[3]}
    keep = {"Total experience": True, "Current CTC": asked.get("current_ctc"), "Expected CTC": asked.get("expected_ctc"),
            "Notice period": asked.get("notice_period_days"), "Current location": asked.get("current_location")}
    rows = [f"• {k}: {v}" for k, v in facts if v and keep[k]]
    if rows:
        lines += ["", "Quick details:", *rows]
    lines += ["", "I've attached my resume for your review. I'd welcome the chance to discuss how I can contribute.", "",
              "Best regards,", p.name or ""]
    lines += [x for x in (p.phone, p.email, str(p.linkedin_url) if p.linkedin_url else None) if x]
    return subject[:200], "\n".join(lines).strip()

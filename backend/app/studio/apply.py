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


_SUBJECT_LINE = re.compile(r"(?:email\s+)?subject(?:\s+line)?\s*(?:format)?\s*(?:as|:|-|should be|should read|with)\s*([^\n\"“”]{3,100})", re.I)
_PLACEHOLDER = re.compile(r"[\[{<(]\s*(?:job\s+|role\s+)?(?:role|title|position|job\s*title|designation)(?:\s+name)?\s*[\]}>)]", re.I)
_OTHER_FILL = re.compile(r"[\[{<(]\s*(?:your\s+name|name|company|experience|years|exp|notice period|location|ctc)[^\]}>)]*[\]}>)]", re.I)


def subject_asked(text: str, role: str | None = None, name: str | None = None, company: str | None = None) -> str | None:
    """The subject the post asks for. Quoted text is used as written; an unquoted "subject: [Role] - Name" has the role filled in."""
    m = SUBJECT_RE.search(text or "")
    raw = m.group(1).strip() if m else None
    if raw is None:
        m = _SUBJECT_LINE.search(text or "")
        raw = re.split(r"\s{2,}|\.\s", m.group(1).strip())[0].rstrip(" .") if m else None
    if raw is None:
        return None
    if role:
        raw = _PLACEHOLDER.sub(role, raw)
    if name:
        raw = re.sub(r"[\[{<(]\s*(?:your\s+)?name\s*[\]}>)]|your\s+name", name, raw, flags=re.I)
    if company:
        raw = re.sub(r"[\[{<(]\s*company(?:\s+name)?\s*[\]}>)]", company, raw, flags=re.I)
    if _PLACEHOLDER.search(raw) or _OTHER_FILL.search(raw):  # a template we can't fill truthfully -> use our own subject
        return None if not role else _OTHER_FILL.sub("", raw).strip(" -|:") or None
    return raw


NAME_RE = re.compile(r"(?i:contact|attention|attn|reach\s+out\s+to|ping|send\s+(?:your\s+)?(?:cv|resume)\s+to|hiring\s+manager|recruiter)\s*[:\-]?\s*"
                     r"(?:is\s+)?([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)(?=\s*(?:[,.:;(\n]|$|\s+at\b|\s+on\b|\s+@))")
_NOT_NAMES = {"the", "our", "team", "hr", "us", "me", "email", "mail", "dm", "whatsapp", "details", "resume", "cv"}


def contact_name(text: str) -> str | None:
    """First name of the person to write to, only when the post names one ("Contact: Priya Sharma")."""
    for m in NAME_RE.finditer(text or ""):
        first = m.group(1).split()[0]
        if first.lower() not in _NOT_NAMES:
            return first
    return None


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
    """Subject and body (about 120-150 words). Uses the subject the post asks for. Every line is a verified profile fact."""
    from app.resumes import craft
    from app.services.skills_vocab import canonical, normalize_key
    from app.studio.analyzer import clean_role

    p = profile.personal
    low = (text or "").lower()
    yrs = describe(p.total_experience_years) if p.total_experience_years else None
    role = clean_role(title) or title or ""
    bits = [f"Application for {role or 'the role'}"]
    if yrs:
        bits.append(f"{yrs} experience")
    if p.notice_period_days is not None:
        bits.append("Immediate joiner" if p.notice_period_days == 0 else f"{p.notice_period_days} days notice")
    if p.name:
        bits.append(p.name)
    subject = subject_asked(text, role, p.name, company) or " | ".join(bits)
    who = contact_name(text)
    lines = [f"Hi {who}," if who else "Hello Hiring Team,", ""]
    first = f"I'd like to apply for the {role} role" if role else "I'd like to apply for the open role"
    first += f" at {company}." if company else "."
    if yrs:
        first += f" I have {yrs} of experience" + (f" as a {p.current_designation}" if p.current_designation else "") + "."
    lines.append(first)
    top = craft.jd_emphasis([canonical(s) for s in skills], text)[:3]
    keys = {normalize_key(canonical(s)) for s in skills}
    proof = craft.best_bullets(profile, keys, n=1)
    para = []
    if top:
        para.append(f"The closest matches to your requirements: {', '.join(top)}.")
    if proof:
        para.append(f"For example, {craft.lower_first(proof[0].rstrip('.'))}.")
    if para:
        lines += ["", " ".join(para)]
    npd = p.notice_period_days
    facts = [("Current CTC", _lpa(p.current_ctc, p.ctc_currency)),
             ("Expected CTC", _lpa(p.expected_ctc, p.ctc_currency)),
             ("Notice period", None if npd is None else ("Immediate" if npd == 0 else f"{npd} days")),
             ("Current location", p.current_location)]
    asked = {f[0]: re.search(f[3], low) for f in FACTS if f[3]}
    keep = {"Current CTC": asked.get("current_ctc"), "Expected CTC": asked.get("expected_ctc"),
            "Notice period": asked.get("notice_period_days"), "Current location": asked.get("current_location")}
    rows = [f"• {k}: {v}" for k, v in facts if v and keep[k]]
    if rows:
        lines += ["", *rows]
    lines += ["", "My resume is attached. I'd be glad to talk through how I can help your team.", "", "Regards,", p.name or ""]
    lines += [x for x in (p.phone, str(p.linkedin_url) if p.linkedin_url else None, p.email) if x]
    return subject[:200], craft.drop_repeats("\n".join(lines)).strip()

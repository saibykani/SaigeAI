"""Deterministic interview-debrief extraction. Everything returned is lifted from the user's own text (never invented)."""

import re

from app.services.skills_vocab import find_skills

_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_Q_CUE = re.compile(r"^(?:.*?\b(?:they asked(?: me)?|he asked(?: me)?|she asked(?: me)?|asked me|asked|question was|questions were|"
                    r"another question|next question)\b)[\s:,\-]*(?:about|to|if|whether)?[\s:,\-]*", re.I)
_GOOD = re.compile(r"went well|\bgood\b|\bgreat\b|nailed|confident|answered well|\bhappy with\b|smooth|aced|strong", re.I)
_BAD = re.compile(r"struggl|couldn'?t|could not|forgot|\bimprove|\bweak|\bmissed\b|blank|nervous|didn'?t know|did not know|"
                  r"\bmistake|should have|\bslow\b|unsure", re.I)
_NEXT = re.compile(r"next (?:step|round)|will (?:get back|hear|call|share|schedule)|follow[- ]?up|expect|by (?:next )?(?:week|monday|tuesday|"
                   r"wednesday|thursday|friday)|within \d+|in \d+ (?:days|weeks)|hr round|final round|assignment|take[- ]home|offer", re.I)
_DATE = re.compile(r"\b(?:\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*|"
                   r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?|\d{4}-\d{2}-\d{2}|"
                   r"(?:next\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|tomorrow|next week)\b", re.I)
_PERSON = re.compile(r"\b(?:interviewer|interviewed by|spoke (?:with|to)|panel(?: was)?|manager(?: was)?|recruiter(?: was)?|named)\s*"
                     r"(?:was|were|:|is)?\s*((?:Mr\.?|Ms\.?|Mrs\.?|Dr\.?)?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)")
_STOP_NAMES = {"The", "He", "She", "They", "It", "We", "I", "My", "Our", "Also", "Then", "There", "This", "That"}
_BULLETS = " -*•\t"


def _sentences(text: str) -> list[str]:
    return [s.strip(_BULLETS) for s in _SPLIT.split(text or "") if s and s.strip(_BULLETS)]


def _clean_q(s: str) -> str:
    s = s.strip()
    return s if s.endswith("?") else s.rstrip(".!") + "?"


def question_key(q: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", q.lower()).strip()[:200]


def questions(text: str) -> list[str]:
    out: list[str] = []
    for s in _sentences(text):
        stripped = _Q_CUE.sub("", s).strip() if _Q_CUE.match(s) else ""
        if "?" in s:
            out.append(_clean_q(stripped if len(stripped) > 8 and "?" in stripped else s))
        elif len(stripped) > 8:
            out.append(_clean_q(stripped[0].upper() + stripped[1:]))
    seen, uniq = set(), []
    for q in out:
        k = question_key(q)
        if k and k not in seen:
            seen.add(k)
            uniq.append(q[:300])
    return uniq[:30]


def _bucket(text: str, pat: re.Pattern, exclude: re.Pattern | None = None) -> list[str]:
    res = []
    for s in _sentences(text):
        if "?" in s or not pat.search(s) or (exclude and exclude.search(s)):
            continue
        res.append(s[:300])
    return list(dict.fromkeys(res))[:12]


def extract(text: str) -> dict:
    nxt = _bucket(text, _NEXT)
    dates = list(dict.fromkeys(m.group(0) for m in _DATE.finditer(" ".join(nxt))))[:6]
    people: list[str] = []
    for m in _PERSON.finditer(text or ""):
        name = m.group(1).strip()
        if name.split()[0] not in _STOP_NAMES and name not in people:
            people.append(name)
    return {"questions": questions(text), "skills": find_skills(text or ""), "went_well": _bucket(text, _GOOD, _BAD),
            "to_improve": _bucket(text, _BAD), "next_steps": nxt, "dates": dates, "interviewers": people[:4]}


def thank_you(name: str, company: str, role: str, data: dict) -> dict:
    """Draft built only from the user's words, company, role and profile name."""
    lines = ["Hi,", "", f"Thank you for taking the time to speak with me about the {role} role at {company}. I enjoyed the conversation."]
    if data["skills"]:
        lines.append(f"I especially enjoyed discussing {' and '.join(data['skills'][:2])}.")
    lines.append(f"I am very interested in the {role} position and in contributing to {company}.")
    if data["next_steps"]:
        lines.append("I noted the next steps you mentioned and look forward to them.")
    lines += ["Please let me know if I can share anything else.", "", "Best regards,", name or ""]
    return {"subject": f"Thank you: {role} interview at {company}", "body": "\n".join(lines).strip(), "to": None, "status": "draft"}

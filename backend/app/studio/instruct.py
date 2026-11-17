"""Edit a resume by chat: plain-English instructions that remove, reorder, shorten or reword what is ALREADY in the resume.

Nothing new is invented: "add" only works for skills already in the verified profile, and every result is re-checked by the
truth guard before it is saved as a new version."""

import re

from app.schemas.profile import Profile
from app.schemas.resume import ParsedResume

_SECTIONS = {"projects": "projects", "project section": "projects", "certifications": "certifications", "certificates": "certifications",
             "achievements": "achievements", "summary": "summary", "education": "education", "tools": "tools"}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9+#.]+", " ", (s or "").lower()).strip()


def _targets(text: str) -> list[str]:
    """'remove Healthcare and SaaS, Jira' -> ['healthcare', 'saas', 'jira']"""
    where = r"\b(from|in|on)\s+(the\s+)?(my\s+)?(resume|skills?|skill section|summary|projects?|experience|bullets?)\b.*$"
    text = re.sub(where, "", text, flags=re.I)
    parts = re.split(r",|\band\b|;|/", text, flags=re.I)
    out = []
    for p in parts:
        t = re.sub(r"^(the|my|all)\s+", "", _norm(p).strip(" '\""))
        t = re.sub(r"\s+(project|projects|skill|skills|bullet|bullets|certification|certificate|tool|line|entry)$", "", t).strip()
        if t:
            out.append(t)
    return out


def apply(r: ParsedResume, profile: Profile, instruction: str) -> tuple[ParsedResume, list[str]]:
    r = r.model_copy(deep=True)
    changes: list[str] = []
    cmds = [c.strip() for c in re.split(r"[\n.]|\bthen\b", instruction or "", flags=re.I) if c.strip()]
    verified = {x.lower(): x for x in profile.skills.all()}
    for cmd in cmds:
        low = cmd.lower().strip()
        # remove a whole section
        m = re.match(r"^(?:please\s+)?(?:remove|delete|drop|hide)\s+(?:the\s+|my\s+)?(.+?)(?:\s+section)?$", low)
        if m and m.group(1).strip() in _SECTIONS:
            sec = _SECTIONS[m.group(1).strip()]
            setattr(r, sec, None if sec == "summary" else [])
            changes.append(f"Removed the {sec} section")
            continue
        # shorten summary
        if re.search(r"\b(shorten|shorter|trim|cut)\b.*\bsummary\b|\bsummary\b.*\b(shorter|short)\b", low) and r.summary:
            sents = re.split(r"(?<=[.!?])\s+", r.summary.strip())
            if len(sents) > 2:
                r.summary = " ".join(sents[:2])
                changes.append("Shortened the summary to 2 sentences")
            continue
        # move skill to top
        m = re.match(r"^(?:move|put|show)\s+(.+?)\s+(?:to\s+the\s+|at\s+the\s+|to\s+)?(?:top|first|start)\b", low)
        if m:
            for t in _targets(m.group(1)):
                hit = next((s for s in r.skills if _norm(s) == t), None) or next((s for s in r.skills if t in _norm(s)), None)
                if hit:
                    r.skills = [hit, *[s for s in r.skills if s != hit]]
                    changes.append(f"Moved {hit} to the top of skills")
            continue
        # add a skill (only if verified in the profile)
        m = re.match(r"^(?:please\s+)?add\s+(.+)$", low)
        if m:
            for t in _targets(m.group(1)):
                src = verified.get(t) or next((v for k, v in verified.items() if _norm(k) == t), None)
                if src and src not in r.skills:
                    r.skills.append(src)
                    changes.append(f"Added {src} (it's in your verified profile)")
                elif not src:
                    changes.append(f"Didn't add “{t}”: it isn't in your verified profile. Add it in Profile first if it's true.")
            continue
        # replace wording X with Y (Y must not introduce a new skill; the truth guard re-checks)
        m = re.match(r"^(?:change|replace|rename)\s+(.+?)\s+(?:to|with)\s+(.+)$", cmd.strip(), re.I)
        if m:
            old, new = m.group(1).strip(" '\""), m.group(2).strip(" '\"")
            n = 0
            for e in r.experience:
                for field in ("achievements", "responsibilities"):
                    vals = getattr(e, field)
                    upd = [re.sub(re.escape(old), new, b, flags=re.I) for b in vals]
                    n += sum(a != b for a, b in zip(vals, upd, strict=False))
                    setattr(e, field, upd)
            if r.summary and re.search(re.escape(old), r.summary, re.I):
                r.summary = re.sub(re.escape(old), new, r.summary, flags=re.I)
                n += 1
            r.skills = [new if _norm(s) == _norm(old) else s for s in r.skills]
            changes.append(f"Changed “{old}” to “{new}” ({n} place(s))" if n else f"Couldn't find “{old}” to change")
            continue
        # remove items: skills, projects, certifications, bullets mentioning the term
        m = re.match(r"^(?:please\s+)?(?:remove|delete|drop|hide|take out)\s+(.+)$", low)
        if m:
            for t in _targets(m.group(1)):
                before = (len(r.skills), len(r.tools), len(r.projects), len(r.certifications))
                r.skills = [s for s in r.skills if t not in _norm(s)]
                r.tools = [s for s in r.tools if t not in _norm(s)]
                r.projects = [p for p in r.projects if t not in _norm(p.name or "")]
                r.certifications = [x for x in r.certifications if t not in _norm(x)]
                bullets = 0
                for e in r.experience:
                    for field in ("achievements", "responsibilities"):
                        vals = getattr(e, field)
                        keep = [b for b in vals if t not in _norm(b)]
                        bullets += len(vals) - len(keep)
                        setattr(e, field, keep)
                    e.technologies = [x for x in e.technologies if t not in _norm(x)]
                after = (len(r.skills), len(r.tools), len(r.projects), len(r.certifications))
                gone = sum(a - b for a, b in zip(before, after, strict=False)) + bullets
                if r.summary and t in _norm(r.summary):
                    sents = [s for s in re.split(r"(?<=[.!?])\s+", r.summary) if t not in _norm(s)]
                    r.summary = " ".join(sents) or r.summary
                    gone += 1
                changes.append(f"Removed “{t}” ({gone} place(s))" if gone else f"Couldn't find “{t}” in this resume")
            continue
        changes.append(f"Didn't understand “{cmd}”. Try: remove X, move X to top, shorten summary, change X to Y, add X, remove projects section.")
    return r, changes

"""Deterministic resume parser: raw text -> structured `ParsedResume`.

Heuristic by design (no LLM) so results are reproducible and nothing is invented: every value
is copied from the source text. Anything the parser is unsure about is left empty and reported
in `warnings` for the user to review.
"""

import re

from app.schemas.resume import (
    ParsedEducation,
    ParsedExperience,
    ParsedLinks,
    ParsedProject,
    ParsedResume,
)
from app.services.skills_vocab import canonical, category_of, find_skills

SECTION_HEADINGS: dict[str, set[str]] = {
    "summary": {"summary", "professional summary", "profile", "profile summary", "objective",
                "career objective", "about me", "professional profile", "career summary"},
    "experience": {"experience", "work experience", "professional experience",
                   "employment history", "work history", "employment", "career history"},
    "skills": {"skills", "technical skills", "key skills", "core competencies", "skill set",
               "technical expertise", "tools and technologies", "technologies", "expertise"},
    "projects": {"projects", "key projects", "personal projects", "academic projects",
                 "project experience", "project details"},
    "education": {"education", "academic background", "qualifications",
                  "educational qualifications", "academic qualifications", "education details"},
    "certifications": {"certifications", "certificates", "licenses and certifications",
                       "certifications and trainings", "certification", "trainings"},
    "achievements": {"achievements", "awards", "accomplishments", "honors", "awards and recognition"},
}

_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DATE = rf"(?:{_MONTH}\s*[,'’]?\s*\d{{2,4}}|\d{{1,2}}[/-]\d{{2,4}}|(?:19|20)\d{{2}})"
_RANGE_RE = re.compile(
    rf"\(?\s*({_DATE})\s*(?:-|–|—|to|till)\s*({_DATE}|present|current|till date|now|ongoing)\s*\)?",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,5}\)?[\s-]?)?\d{3,5}[\s-]?\d{4,6}")
_URL_RE = re.compile(r"(?:https?://)?(?:www\.)?[A-Za-z0-9.-]+\.[a-z]{2,}(?:/[^\s|,]*)?")
_BULLET_RE = re.compile(r"^\s*(?:[•●▪◦‣∙·*\-–—>]|\d+[.)])\s+")
_DEGREE_RE = re.compile(
    r"\b(b\.?\s?tech|m\.?\s?tech|b\.?\s?e\.?|m\.?\s?e\.?|b\.?\s?sc|m\.?\s?sc|bca|mca|mba|bba|"
    r"b\.?\s?com|m\.?\s?com|bachelor(?:'s)?(?: of [a-z ]+)?|master(?:'s)?(?: of [a-z ]+)?|"
    r"ph\.?\s?d|diploma|b\.?s\.?|m\.?s\.?|intermediate|ssc|hsc)\b",
    re.IGNORECASE,
)
_INSTITUTION_RE = re.compile(r"(university|college|institute|school|iit|nit|academy|vidyalaya)",
                             re.IGNORECASE)
_TITLE_WORDS = re.compile(
    r"\b(engineer|tester|analyst|lead|manager|developer|sdet|qa|consultant|architect|intern|"
    r"specialist|associate|director|head|officer|administrator|designer|scientist|programmer)\b",
    re.IGNORECASE,
)
_METRIC_RE = re.compile(r"\d+(?:\.\d+)?\s?(?:%|x\b|\+)|[$₹€£]\s?\d")
_SPLIT_HEADER_RE = re.compile(r"\s+\|\s+|\s+at\s+|\s+[-–—]\s+|\s*,\s*|\t+|\s{3,}")


def _norm_heading(line: str) -> str:
    s = re.sub(r"[^a-z& ]", "", line.lower()).replace("&", "and")
    return re.sub(r"\s+", " ", s).strip()


def _heading_of(line: str) -> str | None:
    stripped = line.strip().rstrip(":")
    if not stripped or len(stripped) > 45:
        return None
    key = _norm_heading(stripped)
    for section, names in SECTION_HEADINGS.items():
        if key in names:
            return section
    return None


def _is_bullet(line: str) -> bool:
    return bool(_BULLET_RE.match(line))


def _strip_bullet(line: str) -> str:
    return _BULLET_RE.sub("", line).strip()


def split_sections(text: str) -> tuple[list[str], dict[str, list[str]]]:
    header: list[str] = []
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        heading = _heading_of(line)
        if heading:
            current = heading
            sections.setdefault(current, [])
            continue
        if not line.strip():
            continue
        (sections[current] if current else header).append(line)
    return header, sections


def _parse_name(header: list[str]) -> str | None:
    for line in header[:5]:
        candidate = line.strip()
        if _EMAIL_RE.search(candidate) or re.search(r"\d", candidate):
            continue
        words = candidate.split()
        if 2 <= len(words) <= 4 and all(re.fullmatch(r"[A-Za-z.'-]+", w) for w in words):
            return " ".join(w if not w.isupper() else w.title() for w in words)
    return None


def _parse_links(text: str) -> ParsedLinks:
    links = ParsedLinks()
    for m in _URL_RE.findall(text):
        if "@" in m or m.count(".") == 0:
            continue
        url = m if m.startswith("http") else f"https://{m}"
        low = url.lower()
        if "linkedin.com" in low:
            links.linkedin = links.linkedin or url
        elif "github.com" in low:
            links.github = links.github or url
        elif any(d in low for d in ("gmail.com", "yahoo.com", "outlook.com")):
            continue
        elif re.search(r"\.(com|io|dev|me|in|net|org|app|site)(/|$)", low) and len(links.other) < 5:
            links.other.append(url)
    if links.other:
        links.portfolio = links.other[0]
    return links


def _parse_skills(lines: list[str]) -> list[str]:
    skills: dict[str, None] = {}
    for line in lines:
        body = _strip_bullet(line)
        if ":" in body:
            body = body.split(":", 1)[1]
        for token in re.split(r"[,|•;]|\s{2,}|\t", body):
            token = token.strip(" .()")
            if 1 <= len(token) <= 40 and len(token.split()) <= 4:
                skills[canonical(token)] = None
    return list(skills)


def _classify_header_tokens(parts: list[str], exp: ParsedExperience) -> None:
    tokens = [t.strip(" |,()") for p in parts for t in _SPLIT_HEADER_RE.split(p) if t.strip(" |,()")]
    rest: list[str] = []
    for t in tokens:
        if exp.title is None and _TITLE_WORDS.search(t):
            exp.title = t
        else:
            rest.append(t)
    for t in rest:
        if exp.company is None:
            exp.company = t
        elif exp.location is None and len(t.split()) <= 3:
            exp.location = t


def _looks_like_header(line: str) -> bool:
    s = line.strip()
    return len(s.split()) <= 10 and not s.endswith(".") and not s[:1].islower()


def _parse_experience(lines: list[str], warnings: list[str]) -> list[ParsedExperience]:
    entries: list[ParsedExperience] = []
    pending: list[str] = []
    current: ParsedExperience | None = None
    last_bullet: list[str] | None = None

    def add_bullet(exp: ParsedExperience, text: str) -> list[str]:
        target = exp.achievements if _METRIC_RE.search(text) else exp.responsibilities
        target.append(text)
        return target

    for line in lines:
        m = _RANGE_RE.search(line)
        if m and not _is_bullet(line):
            current = ParsedExperience(start_date=m.group(1).strip(), end_date=m.group(2).strip())
            if current.end_date.lower() in {"present", "current", "till date", "now", "ongoing"}:
                current.is_current = True
                current.end_date = None
            remainder = (line[: m.start()] + " " + line[m.end():]).strip(" |,-–—")
            _classify_header_tokens(pending + ([remainder] if remainder else []), current)
            entries.append(current)
            pending, last_bullet = [], None
            continue
        if _is_bullet(line):
            text = _strip_bullet(line)
            if current is None:
                continue
            last_bullet = add_bullet(current, text)
            continue
        # Non-bullet, non-date line
        if current is not None and last_bullet is None and (current.company is None or
                                                            current.title is None):
            _classify_header_tokens([line], current)
        elif last_bullet is not None and not _looks_like_header(line):
            last_bullet[-1] = f"{last_bullet[-1]} {line.strip()}"  # wrapped bullet
        else:
            pending.append(line)

    for exp in entries:
        exp.technologies = find_skills(" ".join(exp.responsibilities + exp.achievements))
        if not exp.company or not exp.title:
            warnings.append(
                f"Experience starting {exp.start_date}: could not confirm "
                f"{'company' if not exp.company else 'title'} - please review"
            )
    if lines and not entries:
        warnings.append("Experience section found but no dated roles were recognised")
    return entries


def _parse_education(lines: list[str]) -> list[ParsedEducation]:
    entries: list[ParsedEducation] = []
    current: ParsedEducation | None = None
    for line in lines:
        text = _strip_bullet(line)
        deg = _DEGREE_RE.search(text)
        if deg:
            current = ParsedEducation(degree=deg.group(0).strip(), raw=text)
            after = text[deg.end():].strip(" ,-–|")
            field_m = re.match(r"(?:in|of)?\s*([A-Za-z &]+?)(?:\s*[,|(\-–]|$)", after)
            if field_m and field_m.group(1).strip() and not _INSTITUTION_RE.search(field_m.group(1)):
                current.field = field_m.group(1).strip()
            entries.append(current)
        elif current is not None:
            current.raw = f"{current.raw} {text}"
        else:
            continue
        if _INSTITUTION_RE.search(text) and current.institution is None:
            parts = [p.strip() for p in re.split(r"[,|–—-]", text)]
            current.institution = next((p for p in parts if _INSTITUTION_RE.search(p)), None)
        years = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", text)]
        if years:
            if len(years) >= 2:
                current.start_year, current.end_year = years[0], years[1]
            else:
                current.end_year = current.end_year or years[0]
    return entries


def _parse_projects(lines: list[str]) -> list[ParsedProject]:
    projects: list[ParsedProject] = []
    for line in lines:
        if _is_bullet(line) and projects:
            projects[-1].highlights.append(_strip_bullet(line))
            continue
        text = _strip_bullet(line)
        tech = re.match(r"(?:technologies|tech stack|tools|environment)\s*:\s*(.+)", text, re.I)
        if tech and projects:
            projects[-1].technologies += [canonical(t) for t in re.split(r"[,|;]", tech.group(1))
                                          if t.strip()]
            continue
        if _looks_like_header(text):
            name = re.sub(r"^project\s*(?:name)?\s*[:\-]\s*", "", text, flags=re.I)
            name = re.split(r"\s+\|\s+|\s+[-–—]\s+", name)[0].strip()
            if name:
                projects.append(ParsedProject(name=name[:200]))
        elif projects:
            projects[-1].highlights.append(text)
    for p in projects:
        found = find_skills(" ".join(p.highlights))
        p.technologies = list(dict.fromkeys(p.technologies + found))
    return projects


def parse_resume(text: str) -> ParsedResume:
    header, sections = split_sections(text)
    warnings: list[str] = []

    email_m = _EMAIL_RE.search(text)
    phone_m = next((m for m in _PHONE_RE.finditer("\n".join(header) or text)
                    if len(re.sub(r"\D", "", m.group(0))) >= 10), None)
    skills_section = _parse_skills(sections.get("skills", []))
    vocab_skills = find_skills(text)
    skills = list(dict.fromkeys(skills_section + vocab_skills))

    result = ParsedResume(
        name=_parse_name(header),
        email=email_m.group(0) if email_m else None,
        phone=phone_m.group(0).strip() if phone_m else None,
        links=_parse_links(text),
        summary=" ".join(line.strip() for line in sections.get("summary", [])) or None,
        skills=skills,
        tools=[s for s in skills if category_of(s) in {"tools", "testing_tools", "ci_cd"}],
        experience=_parse_experience(sections.get("experience", []), warnings),
        projects=_parse_projects(sections.get("projects", [])),
        education=_parse_education(sections.get("education", [])),
        certifications=[_strip_bullet(line) for line in sections.get("certifications", [])],
        achievements=[_strip_bullet(line) for line in sections.get("achievements", [])],
        sections_found=list(sections),
        warnings=warnings,
    )
    for field, label in (("name", "Name"), ("email", "Email"), ("phone", "Phone")):
        if getattr(result, field) is None:
            result.warnings.append(f"{label} not found - marked UNKNOWN")
    if not text.strip():
        result.warnings.append("No text could be extracted (scanned PDFs need OCR)")
    return result

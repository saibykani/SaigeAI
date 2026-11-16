"""Wording helpers for resumes, summaries, cover letters and application emails.

Everything here only selects, orders, trims or re-opens text the candidate already wrote. Nothing adds a fact:
a bullet keeps every number and tool it had, and a skill phrase is used only when the profile supports it.
"""

import re

from app.services.skills_vocab import canonical, find_skills, normalize_key

# "Worked on X" style openers -> a stronger opener that means the same thing.
_OPENERS = [
    (r"^(?:was\s+|am\s+)?responsible\s+for\s+", "Owned "), (r"^(?:was\s+|am\s+)?involved\s+in\s+", "Contributed to "),
    (r"^worked\s+(?:on|with|in)\s+", "Contributed to "), (r"^participated\s+in\s+", "Contributed to "),
    (r"^(?:was\s+)?(?:part\s+of|a\s+part\s+of)\s+", "Contributed to "), (r"^(?:helped|assisted)\s+(?:in|with)\s+", "Supported "),
    (r"^(?:helped|assisted)\s+(?:to\s+)?", "Supported "), (r"^handled\s+", "Managed "), (r"^did\s+", "Performed "),
    (r"^(?:took\s+care\s+of|looked\s+after)\s+", "Managed "), (r"^(?:used|utili[sz]ed)\s+", "Applied "),
]
# Gerunds that can follow a weak opener: "Responsible for creating X" -> "Created X".
_GERUNDS = {
    "creating": "Created", "testing": "Tested", "developing": "Developed", "designing": "Designed", "building": "Built",
    "writing": "Wrote", "executing": "Executed", "automating": "Automated", "analysing": "Analysed", "analyzing": "Analyzed",
    "maintaining": "Maintained", "implementing": "Implemented", "managing": "Managed", "preparing": "Prepared",
    "validating": "Validated", "monitoring": "Monitored", "reviewing": "Reviewed", "integrating": "Integrated",
    "configuring": "Configured", "debugging": "Debugged", "reporting": "Reported", "leading": "Led", "running": "Ran",
    "performing": "Performed", "setting": "Set", "supporting": "Supported", "coordinating": "Coordinated",
    "deploying": "Deployed", "optimising": "Optimised", "optimizing": "Optimized", "creation": "Created",
}
ACTION_VERBS = set(_GERUNDS.values()) | {
    "Owned", "Contributed", "Supported", "Managed", "Performed", "Applied", "Delivered", "Improved", "Reduced", "Increased",
    "Led", "Drove", "Automated", "Built", "Developed", "Designed", "Implemented", "Created", "Executed", "Identified",
    "Collaborated", "Migrated", "Established", "Streamlined", "Resolved", "Achieved", "Coordinated", "Authored", "Enhanced",
}
_WEAK_START = re.compile(r"^(?:responsible|worked|involved|participated|helped|assisted|handled|did|was|were|am|part|utili[sz]ed|used)\b", re.I)


def strengthen(bullet: str) -> str:
    """Re-open a weak bullet ("Worked on", "Responsible for") with an action verb, keeping its meaning and all its facts."""
    b = re.sub(r"^[\s•\-–*·]+", "", bullet or "").strip()
    for rx, verb in _OPENERS:
        m = re.match(rx, b, re.I)
        if not m:
            continue
        rest = b[m.end():]
        first, _, tail = rest.partition(" ")
        if verb in ("Owned ", "Contributed to ", "Managed ") and first.lower() in _GERUNDS:
            return f"{_GERUNDS[first.lower()]} {tail}".strip()
        return verb + rest
    return b[:1].upper() + b[1:] if b else b


def starts_with_action_verb(bullet: str) -> bool:
    w = (re.findall(r"[A-Za-z]+", bullet or "") or [""])[0]
    return bool(w) and not _WEAK_START.match(w) and (w in ACTION_VERBS or w.lower().endswith("ed"))


def condense(text: str, limit: int = 220) -> str:
    """Cut an over-long bullet at a clause boundary (never mid-word); the kept text is the user's own words."""
    t = re.sub(r"\s+", " ", text or "").strip()
    if len(t) <= limit:
        return t
    cut = max((t.rfind(sep, 60, limit) for sep in (". ", "; ", " - ", ", ")), default=-1)
    return t[:cut].rstrip(" ,;-.") + "." if cut > 0 else t


_NUM = re.compile(r"\d")


def has_number(text: str) -> bool:
    return bool(_NUM.search(text or ""))


def score_bullet(text: str, jd_keys: set[str], req_words: set[str]) -> float:
    skills = {normalize_key(canonical(s)) for s in find_skills(text)}
    words = set(re.findall(r"[a-z0-9+#]{3,}", text.lower()))
    return 2.0 * len(skills & jd_keys) + 0.15 * len(words & req_words) + (2.5 if has_number(text) else 0.0)


def bullet_cap(role_index: int) -> int:
    """Most recent roles keep more bullets."""
    return 6 if role_index < 2 else 5 if role_index < 4 else 4


def pick_bullets(achievements: list[str], responsibilities: list[str], role_index: int, jd_keys: set[str],
                 req_words: set[str]) -> tuple[list[str], list[str]]:
    """Rank a role's bullets by JD overlap and numbers, cap the count, strengthen openers, trim length."""
    pool = [(a, True) for a in achievements] + [(r, False) for r in responsibilities]
    ranked = sorted(range(len(pool)), key=lambda i: (-score_bullet(pool[i][0], jd_keys, req_words) - (0.5 if pool[i][1] else 0), i))
    keep = ranked[:bullet_cap(role_index)]
    ach, res, seen = [], [], set()
    for i in keep:
        text, is_ach = pool[i]
        b = condense(strengthen(text))
        if not b or normalize_key(b) in seen:
            continue
        seen.add(normalize_key(b))
        (ach if is_ach else res).append(b)
    return ach, res


def jd_emphasis(skills: list[str], jd_text: str) -> list[str]:
    """Skills ordered by how often the JD mentions them (stable for ties)."""
    low = (jd_text or "").lower()
    return sorted(skills, key=lambda s: -len(re.findall(rf"(?<![a-z0-9]){re.escape(s.lower())}(?![a-z0-9])", low)))


def _toks(s: str) -> list[str]:
    return re.findall(r"[a-z0-9+#]+", s.lower())


def supported_phrases(jd_text: str, have_skills: list[str]) -> list[str]:
    """JD phrases like "REST API testing" the profile genuinely supports: a verified multi-word skill ("API Testing") covers
    the phrase and the leftover word ("REST") is a prefix of another verified skill ("Rest Assured")."""
    out: list[str] = []
    have = [(s, set(_toks(s))) for s in have_skills]
    have_tokens = {t for _, ts in have for t in ts}
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#/-]*", jd_text or "")
    for i, w in enumerate(words):
        if w.lower() not in ("testing", "automation"):
            continue
        for n in (2, 1):  # the one or two words before "testing", e.g. "REST API testing"
            if i - n < 0:
                continue
            phrase = " ".join(words[i - n:i + 1])
            pt = set(_toks(phrase))
            if len(pt) < 3 or any(normalize_key(phrase) == normalize_key(s) for s, _ in have):
                continue
            head = next((ts for _, ts in have if len(ts) >= 2 and ts < pt), None)
            rest = pt - head if head else set()
            if rest and all(any(ht.startswith(r) and len(r) >= 3 for ht in have_tokens) for r in rest):
                out.append(phrase)
                break
    return list(dict.fromkeys(out))


def dedupe_skills(skills: list[str]) -> list[str]:
    """Drop duplicates that differ by case, punctuation or spacing ("Rest Assured" / "RestAssured", "CI/CD" / "CI CD")."""
    seen: dict[str, str] = {}
    for s in skills:
        key = re.sub(r"[^a-z0-9+#]", "", normalize_key(canonical(s)))
        if key and key not in seen:
            seen[key] = s
    return list(seen.values())


def best_bullets(profile, keys: set[str], req_words: set[str] | None = None, n: int = 1) -> list[str]:
    """The user's own strongest bullets for these JD keywords (numbers and keyword hits), condensed."""
    pool: list[tuple[float, int, str]] = []
    for ri, e in enumerate(profile.knowledge.experience):
        for b in [*e.achievements, *e.responsibilities]:
            s = score_bullet(b, keys, req_words or set())
            if s - (2.5 if has_number(b) else 0) >= 2:  # must hit at least one JD keyword (a number alone is not relevance)
                pool.append((-s, ri, b))
    pool.sort(key=lambda x: (x[0], x[1]))
    return [condense(strengthen(b), 150) for _, _, b in pool[:n]]


def lower_first(s: str) -> str:
    return s[:1].lower() + s[1:] if s and not s[:2].isupper() else s


def drop_repeats(text: str) -> str:
    """Remove an immediately repeated word ("the the") and collapse spaces."""
    return re.sub(r"\b(\w+)([ \t]+\1\b)+", r"\1", re.sub(r"[ \t]+", " ", text), flags=re.I).strip()

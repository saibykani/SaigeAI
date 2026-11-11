"""Tidy a generated resume without changing what it claims.

Resume imports often leave artefacts: skills split on commas inside brackets ("Java (Test Automation",
"Page Object Model (POM"), one-word fragments ("Testing", "Spike"), the same skill twice, and bullets broken
across lines mid-sentence. This module repairs the structure only: it splits, merges, de-duplicates and
groups the user's own words. It never adds a skill, employer, number or claim.
"""

import re

from app.schemas.resume import ParsedResume
from app.services.skills_vocab import canonical, normalize_key

# Words that are never a skill on their own (fragments left by bad comma splitting).
FRAGMENTS = {"testing", "test", "data", "validation", "analysis", "apis", "api", "workflow", "reporting", "monitoring", "planning",
             "execution", "tools", "and", "&", "frameworks", "framework", "automation", "backend", "frontend", "management",
             "development", "design", "support", "systems", "transaction validation"}
# Test types listed on their own ("Functional, Regression, Spike") are skills once "Testing" is put back.
TEST_TYPES = {"functional", "regression", "integration", "end-to-end", "e2e", "smoke", "sanity", "spike", "stress", "load",
              "endurance", "soak", "exploratory", "usability", "compatibility", "security", "acceptance", "system"}

# Skill groups for an organised Skills section (first match wins).
GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("Languages", ("java", "python", "javascript", "typescript", "c#", "c++", "kotlin", "go", "ruby", "sql")),
    ("Test automation", ("selenium", "cucumber", "bdd", "testng", "junit", "pytest", "appium", "playwright", "cypress", "webdriver",
                         "page object", "pom", "data-driven", "automated regression", "test automation", "mobile automation", "robot")),
    ("API testing", ("rest assured", "postman", "newman", "api", "rest", "soap", "json", "xml", "graphql", "swagger")),
    ("Performance testing", ("jmeter", "load", "stress", "spike", "endurance", "performance", "gatling", "locust", "k6", "bottleneck")),
    ("Databases", ("mysql", "mongodb", "azure sql", "postgres", "oracle", "sql server", "database", "data validation", "reconciliation",
                   "backend data")),
    ("CI/CD and tools", ("jenkins", "azure devops", "ci/cd", "github", "gitlab", "gitea", "git", "maven", "gradle", "docker",
                         "kubernetes", "grafana", "azure", "aws", "jira", "spira", "confluence", "testrail")),
    ("Testing practice", ("manual", "functional", "regression", "integration", "end-to-end", "smoke", "sanity", "uat", "test case",
                          "test planning", "test execution", "test reporting", "defect", "rca", "root cause", "release", "sla",
                          "log analysis", "exploratory")),
    ("Methodologies", ("agile", "scrum", "sdlc", "stlc", "kanban", "waterfall")),
]


def _split_skill(raw: str) -> list[str]:
    """'Java (Test Automation' -> ['Java', 'Test Automation']; 'Newman (Postman CLI' -> ['Newman', 'Postman CLI']."""
    s = raw.strip().strip(",;|")
    if not s:
        return []
    if s.count("(") != s.count(")"):
        head, _, inner = s.partition("(")
        head, inner = head.strip(), inner.replace(")", "").strip()
        # a qualifier or abbreviation belongs to the skill: "Page Object Model (POM)", "Newman (Postman CLI)", "JMeter (Master–Slave)"
        if inner and (inner.isupper() or re.search(r"[–-]", inner) or inner.split()[-1] in {"CLI", "SDK", "UI"}):
            parts = [f"{head} ({inner})"]
        else:
            parts = [head, inner]
    else:
        parts = [s]
    out = []
    for p in parts:
        for q in re.split(r"\s*;\s*", p):
            q = re.sub(r"\s+", " ", q).strip(" -–,.")
            if q:
                out.append(q)
    return out


def clean_skills(skills: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for raw in skills:
        for s in _split_skill(raw):
            low = s.lower()
            if low in TEST_TYPES:
                s, low = f"{s[0].upper()}{s[1:]} Testing", f"{low} testing"
            if low in FRAGMENTS or len(s) < 2 or len(s) > 48:
                continue
            key = normalize_key(canonical(s))
            if key and key not in seen:
                seen[key] = s
    names = list(seen.values())
    # drop a short form when a fuller one is present ("BDD" with "Cucumber BDD", "REST" with "REST APIs")
    lowered = [n.lower() for n in names]
    keep = []
    for n in names:
        nl = n.lower()
        fuller = any(o != nl and (o.startswith(f"{nl} (") or (len(nl) <= 12 and (o.startswith(f"{nl} ") or o.endswith(f" {nl}"))))
                     for o in lowered)
        if fuller:
            continue
        keep.append(n)
    return keep


def _has(text: str, key: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", text) is not None


# Databases and tools are checked before languages so "Azure SQL" or "MySQL" don't land under Languages.
_MATCH_ORDER = ["Databases", "Performance testing", "API testing", "Test automation", "CI/CD and tools", "Testing practice",
                "Methodologies", "Languages"]


def group_skills(skills: list[str]) -> list[tuple[str, list[str]]]:
    keys = dict(GROUPS)
    groups: dict[str, list[str]] = {}
    for s in skills:
        low = s.lower()
        label = next((g for g in _MATCH_ORDER if any(_has(low, k) for k in keys[g])), "Other")
        groups.setdefault(label, []).append(s)
    order = [g for g, _ in GROUPS] + ["Other"]
    return [(g, groups[g]) for g in order if g in groups]


def merge_lines(lines: list[str]) -> list[str]:
    """Join bullets that were broken across lines ('...cases for onboarding and' + 'transaction flows ...')."""
    out: list[str] = []
    for raw in lines:
        s = re.sub(r"\s+", " ", raw or "").strip()
        if not s:
            continue
        if out and (not re.search(r"[.!?:;)]$", out[-1]) and (s[0].islower() or out[-1].endswith(("and", "or", "of", "for", "to", "with",
                                                                                                     "the", "a", "in", "-", "–", ",")))):
            out[-1] = f"{out[-1]}{s}" if out[-1].endswith(("-", "–")) else f"{out[-1]} {s}"
        else:
            out.append(s)
    seen, uniq = set(), []
    for s in out:
        k = re.sub(r"\W+", " ", s.lower()).strip()
        if k not in seen:
            seen.add(k)
            uniq.append(s)
    return uniq


def dedupe_sentences(text: str | None) -> str | None:
    """Remove a sentence that repeats an earlier one almost word for word."""
    if not text:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept: list[str] = []
    for s in sentences:
        words = set(re.findall(r"[a-z0-9+#]+", s.lower()))
        if any(len(words & set(re.findall(r"[a-z0-9+#]+", k.lower()))) >= 0.8 * max(1, len(words)) for k in kept):
            continue
        # a short opener fully contained in the next sentence ("SDET with 3+ years of experience.")
        kept.append(s)
    if len(kept) >= 2:
        first = set(re.findall(r"[a-z0-9+#]+", kept[0].lower()))
        second = set(re.findall(r"[a-z0-9+#]+", kept[1].lower()))
        if len(first) <= 12 and len(first & second) >= 0.7 * len(first):
            kept.pop(0)
    return " ".join(kept)


def polish(r: ParsedResume) -> ParsedResume:
    r = r.model_copy(deep=True)
    r.summary = dedupe_sentences(r.summary)
    r.skills = clean_skills(r.skills)
    key = {normalize_key(canonical(s)) for s in clean_skills(r.tools)}
    r.tools = [s for s in r.skills if normalize_key(canonical(s)) in key]
    for e in r.experience:
        e.responsibilities = merge_lines(e.responsibilities)
        e.achievements = merge_lines(e.achievements)
        e.technologies = clean_skills(e.technologies)
    for p in r.projects:
        p.highlights = merge_lines(p.highlights)
        p.technologies = clean_skills(p.technologies)
    return r

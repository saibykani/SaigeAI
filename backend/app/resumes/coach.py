"""ATS coach agent: for ANY target role (or a pasted JD), shows section by section where a resume is weak
and exactly what to add to reach a 100% ATS fit, separating what the verified profile already proves
(safe to add now) from what the user must confirm or learn first. It never adds an unverified claim."""

import re
from collections import Counter

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import collections as c
from app.jobs.jd_parser import analyze_jd
from app.profiles.service import get_profile
from app.resumes import tailor
from app.schemas.resume import ParsedResume
from app.services.skills_vocab import canonical, normalize_key

# Fallback keywords per role family, used only when the user's own tracked jobs don't cover the role.
ROLE_KEYWORDS: list[tuple[tuple[str, ...], list[str]]] = [
    (("sdet", "qa", "test", "quality"), ["Selenium", "Java", "TestNG", "API Testing", "Postman", "Rest Assured", "SQL", "Jenkins", "Git",
                                         "Cucumber", "Agile", "JIRA", "Regression Testing", "CI/CD", "Playwright"]),
    (("performance",), ["JMeter", "LoadRunner", "Performance Testing", "Load Testing", "Grafana", "APM", "SQL", "Linux"]),
    (("frontend", "react", "ui"), ["JavaScript", "TypeScript", "React", "HTML", "CSS", "Redux", "REST", "Git", "Jest", "Webpack"]),
    (("backend", "java", "python", "developer", "engineer", "fullstack", "full stack"),
     ["Java", "Python", "Spring Boot", "REST", "Microservices", "SQL", "Docker", "Kubernetes", "AWS", "Git", "CI/CD"]),
    (("data", "analyst", "analytics"), ["SQL", "Python", "Excel", "Power BI", "Tableau", "Statistics", "Pandas", "ETL"]),
    (("ml", "ai", "machine learning", "scientist"), ["Python", "Machine Learning", "PyTorch", "TensorFlow", "Pandas", "SQL", "NLP", "MLOps"]),
    (("devops", "sre", "cloud"), ["AWS", "Azure", "Docker", "Kubernetes", "Terraform", "Jenkins", "Linux", "CI/CD", "Prometheus"]),
    (("business analyst", "product", "owner", "manager"), ["Requirements Gathering", "JIRA", "Agile", "Scrum", "SQL", "Stakeholder Management",
                                                           "User Stories", "Confluence", "UAT"]),
]
_NUM = re.compile(r"\d|%|₹|\$")


def _k(s: str) -> str:
    return normalize_key(canonical(s))


async def role_keywords(db: AsyncIOMotorDatabase, uid: str, role: str) -> list[str]:
    """What jobs for this role ask for: first the user's own tracked postings, then the built-in role family list."""
    words = {w for w in re.findall(r"[a-z]+", role.lower()) if len(w) > 1}
    counts: Counter[str] = Counter()
    async for j in db[c.JOBS].find({"user_id": uid}, {"title": 1, "analysis.required_skills": 1}).limit(400):
        if words & set(re.findall(r"[a-z]+", (j.get("title") or "").lower())):
            counts.update((j.get("analysis") or {}).get("required_skills") or [])
    found = [s for s, n in counts.most_common(15) if n >= 2]
    low = role.lower()
    fallback = next((kw for keys, kw in ROLE_KEYWORDS if any(k in low for k in keys)), ROLE_KEYWORDS[3][1])
    return list(dict.fromkeys(found + fallback))[:18]


def synthetic_jd(role: str, keywords: list[str]) -> str:
    return f"{role}\nRequirements: {', '.join(keywords)}.\nMust have: {', '.join(keywords[:10])}.\nNice to have: {', '.join(keywords[10:])}."


async def coach(db: AsyncIOMotorDatabase, uid: str, parsed: ParsedResume, role: str, jd_text: str | None) -> dict:
    if jd_text and len(jd_text.strip()) >= 30:
        text = jd_text
    else:
        text = synthetic_jd(role, await role_keywords(db, uid, role))
    jd = analyze_jd(role, text)
    report = tailor.ats_report(parsed, jd)
    profile = await get_profile(db, uid)
    verified = {_k(s) for group in profile.skills.model_dump().values() for s in group}
    verified |= {_k(t) for e in profile.knowledge.experience for t in e.technologies}
    verified |= {_k(t) for p in profile.knowledge.projects for t in p.technologies}
    missing = report["missing_required"] + report["missing_preferred"]
    can_add = [s for s in missing if _k(s) in verified]
    confirm = [s for s in missing if _k(s) not in verified]

    bullets = [b for e in parsed.experience for b in e.responsibilities + e.achievements]
    plain = [b for b in bullets if not _NUM.search(b)]
    sections: list[dict] = []

    def sec(name: str, ok: bool, issue: str, add: list[str] | None = None, fix: str = "") -> None:
        sections.append({"section": name, "ok": ok, "issue": issue, "add": add or [], "fix": fix})

    sec("Keywords & skills", not missing, f"{len(missing)} of the role's keywords are missing" if missing else "All role keywords present",
        can_add, "Already proven in your profile: add these now." if can_add else "")
    if confirm:
        sec("Skills to confirm or learn", False, "Not in your profile. Add only the ones you have really used.", confirm,
            "Confirm in ATS Studio, or build a small project to learn them.")
    summ = (parsed.summary or "").lower()
    sec("Summary", bool(parsed.summary) and role.lower().split()[0] in summ,
        "Missing" if not parsed.summary else "Doesn't name the target role" if role.lower().split()[0] not in summ else "Names the role",
        [], f"Open with “{role} with … experience in {', '.join(report['matched_keywords'][:3]) or 'your top skills'}”.")
    sec("Experience bullets", bool(bullets) and len(plain) / max(1, len(bullets)) <= 0.6,
        f"{len(plain)} of {len(bullets)} bullets have no result/number" if bullets else "No bullets under your roles",
        [], "Start with an action verb, add the tool and a result you can back up (%, time saved, defects, users).")
    sec("Projects", len(parsed.projects) >= 2, f"{len(parsed.projects)} project(s)", [],
        "Add 2–4 projects that use the role's keywords (Profile → Update from resume picks them up from other resumes).")
    for ch in report["checks"]:
        if not ch["passed"]:
            sec(ch["check"], False, "Failing ATS check", [], "Fix this in your profile, then rebuild the resume.")

    # Projected score if every verified keyword were on the resume (structure unchanged).
    req, pref = jd.required_skills or [1], jd.preferred_skills or [1]
    hit_req = len([s for s in jd.required_skills if s not in report["missing_required"] or s in can_add])
    hit_pref = len([s for s in jd.preferred_skills if s not in report["missing_preferred"] or s in can_add])
    checks_ok = sum(ch["passed"] for ch in report["checks"]) / len(report["checks"])
    projected = round(100 * (0.55 * hit_req / len(req) + 0.15 * hit_pref / len(pref) + 0.30 * checks_ok))
    return {"role": role, "score": report["score"], "projected": max(projected, report["score"]), "matched": report["matched_keywords"],
            "can_add": can_add, "confirm": confirm, "sections": sections, "jd_text": text}

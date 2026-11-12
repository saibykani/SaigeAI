"""Question generation for mock interviews: deterministic templates built from the JD and the verified profile.

Questions only *ask*; they never assert anything about the candidate beyond verified facts (project names,
employers, skills already in the profile). Gap questions are phrased as "how would you approach/learn"."""

import random
import re

from app.schemas.profile import Profile
from app.services.skills_vocab import find_skills, normalize_key

TYPES = ("hr", "technical", "behavioural", "mixed")
DIFFICULTIES = ("easy", "medium", "hard")
LANGUAGES = ("en", "hi", "te", "ta", "kn", "ml")

HR = [
    ("Tell me about yourself and what brings you to this {role} role.", ["experience", "role", "skills", "background"]),
    ("Why do you want to work as a {role}, and why now?", ["motivation", "career", "growth", "role"]),
    ("What are your key strengths, and how have they helped you at work?", ["strength", "example", "team", "result"]),
    ("Where do you see yourself in the next three to five years?", ["growth", "goal", "learn", "lead"]),
    ("What are you looking for in your next team and manager?", ["team", "culture", "feedback", "growth"]),
    ("What is your notice period and how soon could you join?", ["notice", "days", "join", "available"]),
    ("What is one area you are actively working to improve?", ["improve", "weakness", "learn", "feedback"]),
]
BEHAVIOURAL = [
    ("Tell me about a time you faced a tight deadline. What did you do?", ["deadline", "prioritise", "plan", "deliver", "result"]),
    ("Describe a conflict with a teammate and how you resolved it.", ["conflict", "listen", "agree", "resolve", "team"]),
    ("Tell me about a mistake you made at work and what you learned.", ["mistake", "own", "fix", "learn", "process"]),
    ("Describe a time you took ownership of a problem nobody else picked up.", ["ownership", "initiative", "problem", "impact"]),
    ("Tell me about a time you had to learn something new quickly.", ["learn", "quickly", "practice", "apply", "result"]),
    ("Describe a situation where you disagreed with a decision. What happened?", ["disagree", "data", "discuss", "outcome"]),
    ("Tell me about a time you improved a process for your team.", ["improve", "process", "before", "after", "team"]),
]
TECH_GENERIC = [
    ("Walk me through how you would debug a failure that only happens in production.", ["logs", "reproduce", "isolate", "root cause", "fix"]),
    ("How do you make sure the code or tests you write stay maintainable?", ["review", "structure", "naming", "refactor", "tests"]),
    ("How would you design a solution to be reliable under heavy load?", ["scale", "cache", "monitor", "retry", "load"]),
]
SKILL_DEEP = {
    "easy": "What is {skill}, and how have you used it in your work?",
    "medium": "Walk me through a real problem you solved with {skill}. What trade-offs did you make?",
    "hard": "What are the limitations or pitfalls of {skill}, and how have you worked around them in production?",
}
GAP = "This role uses {skill}, which isn't in your profile yet. How would you get productive with it in your first month?"
PROJECT = "Tell me about your project {project}. What was your role, and what was the hardest part?"
EXPERIENCE = "At {company} as {title}, what were you responsible for, and what are you most proud of?"


def profile_skills(p: Profile) -> list[str]:
    seen: dict[str, str] = {}
    for group in p.skills.model_dump().values():
        for s in group:
            seen.setdefault(normalize_key(s), s)
    for e in p.knowledge.experience:
        for s in e.technologies:
            seen.setdefault(normalize_key(s), s)
    for pr in p.knowledge.projects:
        for s in pr.technologies:
            seen.setdefault(normalize_key(s), s)
    return list(seen.values())


def context(p: Profile, role: str, jd_text: str, jd_skills: list[str] | None = None) -> dict:
    jd = list(dict.fromkeys((jd_skills or []) + find_skills(jd_text or "")))
    have_keys = {normalize_key(s): s for s in profile_skills(p)}
    have = [s for s in jd if normalize_key(s) in have_keys]
    miss = [s for s in jd if normalize_key(s) not in have_keys]
    if not jd:  # role-only: drill into the candidate's own top skills
        have = (p.skills.primary or list(have_keys.values()))[:6]
    return {"role": role or (p.personal.current_designation or "this"), "jd_skills": jd, "have": have, "miss": miss,
            "projects": [pr.name for pr in p.knowledge.projects],
            "experience": [(e.company, e.title) for e in p.knowledge.experience]}


def _kw(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z+#.]{3,}", text.lower())
            if w not in {"what", "your", "with", "have", "tell", "about", "this", "that", "would", "how", "when", "were", "they"}][:6]


def _q(text: str, kind: str, keywords: list[str], skill: str | None = None, star: bool = False) -> dict:
    return {"text": text, "kind": kind, "skill": skill, "keywords": list(dict.fromkeys(k.lower() for k in keywords if k)), "star": star}


def generate(ctx: dict, itype: str, difficulty: str, n: int, seed: int | None = None) -> list[dict]:
    rnd = random.Random(seed)  # noqa: S311 - question order, not security
    role = ctx["role"]
    hr = [_q(t.format(role=role), "hr", k) for t, k in HR]
    beh = [_q(t, "behavioural", k, star=True) for t, k in BEHAVIOURAL]
    rnd.shuffle(beh)
    proj = [_q(PROJECT.format(project=x), "project", [x, "role", "challenge", "result"], star=True) for x in ctx["projects"]]
    exp = [_q(EXPERIENCE.format(company=c, title=t), "experience", [c, "responsible", "result"], star=True) for c, t in ctx["experience"][:2]]
    deep = [_q(SKILL_DEEP[difficulty].format(skill=s), "skill", [s, *(_kw(SKILL_DEEP[difficulty]))[:2], "example"], skill=s) for s in ctx["have"]]
    gap = [_q(GAP.format(skill=s), "gap", [s, "learn", "practice", "plan", "similar"], skill=s) for s in ctx["miss"]]
    gen = [_q(t, "technical", k) for t, k in TECH_GENERIC]

    if itype == "hr":
        pools = [hr[:1], hr[1:], beh[:2], exp]
    elif itype == "behavioural":
        pools = [hr[:1], beh, proj, exp]
    elif itype == "technical":
        pools = [proj[:1], deep, gap[:3], proj[1:], gen]
    else:
        pools = [hr[:1], proj[:1], deep, beh[:3], gap[:2], exp, hr[1:3], proj[1:], gen, beh[3:]]
    # Round-robin across pools so the interview mixes question kinds, then pad with anything left.
    out: list[dict] = []
    queues = [list(p) for p in pools if p]
    while len(out) < n and any(queues):
        for q in queues:
            if q and len(out) < n:
                item = q.pop(0)
                if item["text"] not in {o["text"] for o in out}:
                    out.append(item)
    for extra in hr + beh + gen:
        if len(out) >= n:
            break
        if extra["text"] not in {o["text"] for o in out}:
            out.append(extra)
    return out[:n]

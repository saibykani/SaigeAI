"""Deterministic answer scoring and model-answer outlines built only from verified profile facts."""

import re

from app.schemas.profile import Profile
from app.services.skills_vocab import find_skills, normalize_key
from app.services.truth_guard import GeneratedClaims, validate_claims

FILLERS = ("um", "uh", "umm", "uhh", "like", "basically", "actually", "you know", "kind of", "sort of", "literally", "i mean")
STAR = {
    "situation": ("situation", "when i was", "at the time", "context", "background", "we had", "there was", "project"),
    "task": ("task", "my role", "responsible", "goal", "needed to", "had to", "asked to", "objective"),
    "action": ("i built", "i wrote", "i designed", "i led", "i created", "i implemented", "i automated", "i analysed", "i analyzed",
               "i set up", "i worked", "i decided", "i used", "i fixed", "action", "so i", "i then"),
    "result": ("result", "as a result", "outcome", "reduced", "improved", "increased", "saved", "delivered", "achieved", "learned", "impact"),
}
WEIGHTS = {"relevance": 0.35, "structure": 0.2, "specifics": 0.2, "length": 0.15, "fluency": 0.1}


def _words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9+#.']+", text.lower())


def score_answer(q: dict, answer: str, profile_skills: list[str]) -> dict:
    text = (answer or "").strip()
    low = f" {text.lower()} "
    words = _words(text)
    n = len(words)
    if n == 0:
        return {"score": 0, "breakdown": {k: 0 for k in WEIGHTS}, "feedback": ["No answer recorded."], "word_count": 0,
                "filler_count": 0, "star": {k: False for k in STAR}, "matched_keywords": []}
    kws = q.get("keywords") or []
    hit = [k for k in kws if k in low or (len(k) >= 5 and any(w.startswith(k[:5]) for w in words))]
    relevance = min(100, round(100 * len(hit) / max(1, min(len(kws), 4)))) if kws else 60
    star = {part: any(cue in low for cue in cues) for part, cues in STAR.items()}
    structure = round(100 * sum(star.values()) / 4) if q.get("star") else min(100, 40 + 20 * sum(star.values()))
    nums = len(re.findall(r"\d+", text))
    tech = {normalize_key(s) for s in find_skills(text)}
    own = tech & {normalize_key(s) for s in profile_skills}
    specifics = min(100, 25 * min(nums, 2) + 20 * len(own)
                    + (10 if re.search(r"\bfor example\b|\bfor instance\b|\bspecifically\b", low) else 0))
    if n < 60:
        length = round(100 * n / 60)
    elif n <= 250:
        length = 100
    else:
        length = max(40, 100 - (n - 250) // 5)
    fillers = sum(len(re.findall(rf"(?<![a-z]){re.escape(f)}(?![a-z])", low)) for f in FILLERS)
    fluency = max(0, 100 - round(400 * fillers / n))
    breakdown = {"relevance": relevance, "structure": structure, "specifics": specifics, "length": length, "fluency": fluency}
    score = round(sum(breakdown[k] * w for k, w in WEIGHTS.items()))

    fb: list[str] = []
    miss = [k for k in kws if k not in hit][:3]
    if relevance < 60 and miss:
        fb.append(f"Address the question more directly: mention {', '.join(miss)}.")
    if q.get("star"):
        gaps = [p for p, ok in star.items() if not ok]
        if gaps:
            fb.append(f"Use STAR: your answer is missing the {', '.join(gaps)} part{'s' if len(gaps) > 1 else ''}.")
    if nums == 0:
        fb.append("Add a concrete result you can verify (a number, time saved, defects found), only if it is true.")
    if q.get("skill") and q.get("kind") != "gap" and normalize_key(q["skill"]) not in tech:
        fb.append(f"Name {q['skill']} explicitly and describe how you used it.")
    if n < 60:
        fb.append(f"Too short ({n} words). Aim for 60 to 250 words, about 1 to 2 minutes spoken.")
    elif n > 250:
        fb.append(f"A bit long ({n} words). Lead with the answer, then one example.")
    if fillers >= 3:
        fb.append(f"Cut filler words ({fillers} found, e.g. um, basically, like). Pause instead.")
    if not fb:
        fb.append("Strong answer: direct, structured and specific.")
    return {"score": score, "breakdown": breakdown, "feedback": fb, "word_count": n, "filler_count": fillers, "star": star,
            "matched_keywords": hit}


def model_outline(q: dict, p: Profile) -> list[str]:
    """Bullet outline of a good answer using ONLY facts already in the verified profile. Never invents metrics."""
    k = p.knowledge
    skill = (q.get("skill") or "").lower()
    qtext = q["text"].lower()
    out: list[str] = []
    if q["kind"] == "project":
        for pr in k.projects:
            if pr.name.lower() in qtext:
                out.append(f"Situation: {pr.description or pr.name}"[:300])
                if pr.role:
                    out.append(f"Your role: {pr.role}")
                if pr.technologies:
                    out.append(f"Tools you used: {', '.join(pr.technologies[:6])}")
                out += [f"Result: {h}" for h in pr.highlights[:2]]
                break
    elif q["kind"] == "experience":
        for e in k.experience:
            if e.company.lower() in qtext:
                out += [f"Responsibility: {r}" for r in e.responsibilities[:2]]
                out += [f"Achievement: {a}" for a in e.achievements[:2]]
                break
    elif q["kind"] == "skill" and skill:
        for e in k.experience:
            for b in e.achievements + e.responsibilities:
                if skill in b.lower() and len(out) < 3:
                    out.append(f"At {e.company}: {b}")
        for pr in k.projects:
            if any(skill == t.lower() for t in pr.technologies) and len(out) < 4:
                out.append(f"In {pr.name}: {pr.description or 'used ' + q['skill']}"[:300])
        out.insert(0, f"Define {q['skill']} in one line, then give your real example.")
    elif q["kind"] == "gap":
        related = (p.skills.primary + p.skills.tools)[:4]
        out = [f"Be honest: you haven't used {q['skill']} professionally yet.",
               f"Bridge from what you know{': ' + ', '.join(related) if related else ''}.",
               "Give a concrete learning plan: docs, a small practice project, pairing with the team."]
    elif q["kind"] == "hr":
        per = p.personal
        if "notice" in qtext:
            if per.notice_period_days is not None:
                out = [f"Notice period: {per.notice_period_days} days"]
        else:
            if per.current_designation or per.current_company:
                at = f" at {per.current_company}" if per.current_company else ""
                out.append(f"Now: {per.current_designation or 'working'}{at}")
            if per.total_experience_years:
                out.append(f"Experience: {per.total_experience_years:g} years")
            if k.professional_summary:
                out.append(f"Summary: {k.professional_summary[:220]}")
    if q.get("star") and not out:
        out = [f"Example from {e.company}: {a}" for e in k.experience for a in e.achievements][:2]
    if q.get("star"):
        out.append("Structure: Situation, Task, Action (what you did), Result.")
    if not out:
        out = ["Answer directly in the first sentence.", "Support it with one real example from your profile.",
               "Close with what you learned or the outcome."]
    # Truth guard: drop any line that mentions a skill the candidate has not verified
    # (gap lines name the JD skill on purpose, as something the candidate does NOT have).
    safe = [line for line in out if q["kind"] == "gap" or validate_claims(GeneratedClaims(text=line), p).passed]
    return safe[:6]

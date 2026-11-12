"""Actionable resume health: every failing check lists the exact lines to change and how.

Rewrites only change wording of the user's own text (weak verb -> action verb, split long bullets, trim an
over-long skills list to the skills the resume itself shows evidence for). Numbers are never invented: bullets
without a result get a question to answer, and only text the user types is written back."""

import math
import re

from app.resumes.tailor import resume_text
from app.schemas.resume import ParsedResume

WEAK = [  # (pattern at bullet start, replacement)
    (r"^(was )?responsible for\s+", "Owned "), (r"^worked on\s+", "Delivered "), (r"^worked with\s+", "Used "),
    (r"^worked as\s+", "Served as "), (r"^worked\s+", "Delivered "), (r"^involved in\s+", "Contributed to "),
    (r"^participated in\s+", "Contributed to "), (r"^helped (to )?", "Supported "), (r"^assisted (in |with )?", "Supported "),
    (r"^handled\s+", "Managed "), (r"^did\s+", "Performed "), (r"^tasked with\s+", "Drove "),
]
SYNONYMS = {
    "testing": "validation, verification, QA", "validation": "verification, checks", "automation": "scripted suites, automated checks",
    "automated": "scripted, built", "developed": "built, engineered", "performed": "ran, executed", "ensured": "guaranteed, safeguarded",
    "application": "app, platform, product", "applications": "apps, platforms", "various": "(drop it, or name them)",
    "multiple": "(give the number)", "using": "with", "through": "via", "different": "(drop it)", "process": "workflow",
    "functional": "feature", "scenarios": "cases, flows", "reports": "dashboards, summaries", "framework": "harness, suite",
}
_NUM = re.compile(r"\d|%|₹|\$")


def _question(b: str) -> str:
    low = b.lower()
    if re.search(r"load|performance|jmeter|loadrunner|stress|latency", low):
        return "How many users / requests per second, or how much faster did it get?"
    if re.search(r"automat|script|framework|selenium|playwright|cypress|appium", low):
        return "How many test cases or flows? How much testing time did it save?"
    if re.search(r"api|endpoint|rest|postman", low):
        return "How many APIs / endpoints did you cover?"
    if re.search(r"defect|bug|issue", low):
        return "How many defects did you find or prevent?"
    if re.search(r"team|mentor|lead|train", low):
        return "How many people? What changed because of it?"
    if re.search(r"ci|pipeline|jenkins|deploy|release", low):
        return "How often does it run, or how much faster are releases?"
    return "What was the result? Add a number you can back up (%, time, count, users)."


def _rewrite_verb(b: str) -> str | None:
    for pat, rep in WEAK:
        m = re.match(pat, b, re.I)
        if m:
            rest = b[m.end():]
            return rep + rest
    return None


def _split(b: str) -> list[str]:
    parts = [p.strip(" ,;") for p in re.split(r";\s+|,\s+and\s+|\s+and\s+(?=[a-z]+ed\b)", b) if p.strip(" ,;")]
    if len(parts) < 2:
        mid = len(b.split()) // 2
        w = b.split()
        parts = [" ".join(w[:mid]), " ".join(w[mid:])]
    return [p[:1].upper() + p[1:] + ("" if p.endswith(".") else ".") for p in parts]


def _bullets(r: ParsedResume) -> list[str]:
    return [b for e in r.experience for b in (e.achievements or []) + (e.responsibilities or [])]


def plan(r: ParsedResume) -> dict:
    """Side-by-side plan for every bullet: your line, the wording fix Saige applies, and whether it still needs a real number
    from you. Also the score after the automatic fixes and how many numbers are needed to reach 100."""
    rows = []
    for b in _bullets(r):
        after = _rewrite_verb(b) or b
        if len(after.split()) > 32:
            after = " / ".join(_split(after))
        rows.append({"before": b, "after": after, "changed": after != b, "needs_number": not _NUM.search(b),
                     "ask": "" if _NUM.search(b) else _question(b)})
    fixed, _ = apply_fixes(r, {}, verbs=True, split=True, trim_skills=True)
    rep = report(fixed, with_plan=False)
    n = max(1, rep["bullets"])
    need = max(0, math.ceil(0.4 * n) - rep["quantified"])
    blockers = [s["area"] for s in rep["sections"] if not s["ok"] and s["area"] != "Quantified impact"]
    return {"rows": rows, "projected": rep["score"], "numbers_needed": need, "blockers": blockers}


def report(r: ParsedResume, with_plan: bool = True) -> dict:
    text = resume_text(r)
    bullets = _bullets(r)
    n = max(1, len(bullets))
    quantified = [b for b in bullets if _NUM.search(b)]
    plain = [b for b in bullets if not _NUM.search(b)]
    long_b = [b for b in bullets if len(b.split()) > 32]
    weak = [(b, w) for b in bullets if (w := _rewrite_verb(b))]
    skill_words = {w for s in r.skills for w in re.findall(r"[a-z]+", s.lower())}
    words = re.findall(r"[a-z]+", text.lower())
    counts: dict[str, int] = {}
    for w in words:
        if len(w) > 5 and w not in skill_words:  # tool names (Selenium, JMeter) are meant to repeat
            counts[w] = counts.get(w, 0) + 1
    repeated = sorted((w for w, c in counts.items() if c >= 5), key=lambda w: -counts[w])[:6]
    body = " ".join([*bullets, *(h for p in r.projects for h in p.highlights), r.summary or ""]).lower()
    evidenced = [s for s in r.skills if s.lower() in body]
    unproven = [s for s in r.skills if s.lower() not in body]
    first_person = len(re.findall(r"\b(i|me|my)\b", text.lower()))
    too_many = len(r.skills) > 30

    def sec(area: str, ok: bool, tip: str, items: list[dict] | None = None, fixable: bool = False) -> dict:
        return {"area": area, "ok": ok, "tip": tip, "items": items or [], "fixable": fixable}

    sections = [
        sec("Contact details", bool(r.email and r.phone), "Email and phone are present." if r.email and r.phone
            else "Missing: " + ", ".join(x for x, v in (("email", r.email), ("phone", r.phone)) if not v) + ". Add it in Profile, then rebuild."),
        sec("Quantified impact", len(quantified) / n >= 0.4,
            f"{len(quantified)} of {len(bullets)} bullets have a number. Answer the question under each bullet with a real figure and save.",
            [{"before": b, "ask": _question(b), "edit": True} for b in plain[:8]]),
        sec("Strong verbs", not weak, "Every bullet starts with an action verb." if not weak else
            f"{len(weak)} bullet(s) start with a weak verb. Saige can rewrite the opening (your content stays the same).",
            [{"before": b, "after": a} for b, a in weak[:8]], fixable=bool(weak)),
        sec("Bullet length", not long_b,
            "Bullets are concise." if not long_b else f"{len(long_b)} bullet(s) run over 32 words. Saige can split them.",
            [{"before": b, "after": " / ".join(_split(b))} for b in long_b[:5]], fixable=bool(long_b)),
        sec("Repetition", not repeated, "No heavy repetition." if not repeated else "These words appear 5+ times. Swap some for the alternatives.",
            [{"before": f"“{w}” × {counts[w]}", "after": SYNONYMS.get(w, "rephrase a few of them")} for w in repeated]),
        sec("Skills", 8 <= len(r.skills) <= 30,
            f"{len(r.skills)} skills listed." + (" Recruiters skim; keep 12–25 you can discuss. Saige can keep the ones your experience shows."
                                                if too_many else " List at least 8 tools you really use." if len(r.skills) < 8 else " Good range."),
            ([{"before": "Keep (shown in your experience)", "after": ", ".join(evidenced[:25])},
              {"before": "Consider removing (not mentioned anywhere else)", "after": ", ".join(unproven[:30])}] if too_many else []),
            fixable=too_many and len(evidenced) >= 8),
        sec("Summary", bool(r.summary), "Summary present." if r.summary else "Add a 2–3 line summary in Profile (role, years, top 3 tools)."),
        sec("Length", 300 <= len(words) <= 1100, f"{len(words)} words; aim for 300–1,100 (1–2 pages)."),
        sec("Tone", first_person <= 2, "Neutral tone." if first_person <= 2 else "Remove I / me / my from bullets."),
    ]
    score = round(100 * sum(s["ok"] for s in sections) / len(sections))
    return {"score": score, "label": "Strong" if score >= 80 else "Average — may get overlooked" if score >= 55 else "Needs work",
            "sections": sections, "bullets": len(bullets), "quantified": len(quantified), "words": len(words),
            **({"plan": plan(r)} if with_plan else {})}


def apply_fixes(r: ParsedResume, edits: dict[str, str], *, verbs: bool, split: bool, trim_skills: bool) -> tuple[ParsedResume, list[str]]:
    """Wording-only fixes plus bullets the user rewrote themselves (edits: old bullet -> new text)."""
    r = r.model_copy(deep=True)
    changes: list[str] = []
    for e in r.experience:
        for field in ("achievements", "responsibilities"):
            out: list[str] = []
            for b in getattr(e, field):
                new = (edits.get(b) or "").strip() or b
                if new != b:
                    changes.append(f"Rewrote: {b[:60]}…")
                if verbs and (v := _rewrite_verb(new)):
                    new = v
                    changes.append(f"Stronger verb: {v[:60]}…")
                if split and len(new.split()) > 32:
                    out += _split(new)
                    changes.append(f"Split a long bullet ({len(new.split())} words)")
                else:
                    out.append(new)
            setattr(e, field, out)
    if trim_skills and len(r.skills) > 30:
        body = " ".join([*_bullets(r), *(h for p in r.projects for h in p.highlights), r.summary or ""]).lower()
        keep = [s for s in r.skills if s.lower() in body][:25]
        if len(keep) >= 8:
            changes.append(f"Skills trimmed from {len(r.skills)} to {len(keep)} (kept those your experience shows)")
            r.skills = keep
    return r, changes

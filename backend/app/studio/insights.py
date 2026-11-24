"""ATS Studio insights: score before/after with the concrete changes, JD keyword alignment, and the "missing but true?"
checklist. Nothing here changes the profile: skills reach the verified profile only through /studio/skills/confirm,
after the user ticks them.
"""

from app.jobs.matching import _skill_key, candidate_skills
from app.resumes import tailor
from app.schemas.profile import Profile
from app.schemas.resume import ParsedResume


def before_after(before: ParsedResume | None, after: ParsedResume, jd, after_report: dict, changes: list[str]) -> dict:
    """ATS score of the resume you'd have sent without Saige (your base resume) vs the tailored one, with a change list."""
    edits = [{"kind": "edit", "text": c} for c in changes]
    if before is None:
        return {"before": None, "after": after_report["score"], "delta": None, "items": edits}
    b = tailor.ats_report(before, jd)
    gained = [k for k in after_report["matched_keywords"] if k not in b["matched_keywords"]]
    lost = [k for k in b["matched_keywords"] if k not in after_report["matched_keywords"]]
    was = {x["check"]: x["passed"] for x in b["checks"]}
    fixed = [x["check"] for x in after_report["checks"] if x["passed"] and not was.get(x["check"], True)]
    items: list[dict] = []
    if gained:
        items.append({"kind": "keywords", "text": f"Now matches {len(gained)} more JD keyword(s): {', '.join(gained[:10])}", "items": gained})
    if lost:
        items.append({"kind": "warning", "text": f"No longer on the resume: {', '.join(lost[:6])}", "items": lost})
    if after_report["required_coverage"] != b["required_coverage"]:
        items.append({"kind": "coverage", "text": f"Required-skill coverage {b['required_coverage']}% to {after_report['required_coverage']}%"})
    if fixed:
        items.append({"kind": "structure", "text": f"ATS checks now passing: {', '.join(fixed)}", "items": fixed})
    return {"before": b["score"], "after": after_report["score"], "delta": after_report["score"] - b["score"],
            "required_before": b["required_coverage"], "required_after": after_report["required_coverage"], "items": items + edits}


def keyword_map(profile: Profile, parsed: ParsedResume, jd) -> list[dict]:
    """For each JD keyword: is it on the resume, spelled exactly like the JD, and is it in the verified profile?"""
    have = candidate_skills(profile)
    on = {_skill_key(s): s for s in parsed.skills}
    out = []
    for kw in list(dict.fromkeys(jd.required_skills + jd.preferred_skills)):
        k = _skill_key(kw)
        out.append({"keyword": kw, "required": kw in jd.required_skills, "verified": k in have, "on_resume": k in on,
                    "mirrored": on.get(k) == kw})
    return out


def checklist(profile: Profile, report: dict) -> list[dict]:
    """JD skills that aren't in the verified profile. The user ticks the ones they really have; only those are added."""
    have = candidate_skills(profile)
    out = []
    for kind, key in (("required", "missing_required"), ("preferred", "missing_preferred")):
        for s in report.get(key, []):
            if _skill_key(s) not in have:
                out.append({"skill": s, "kind": kind, "confirmed": False})
    return out

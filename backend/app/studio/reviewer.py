# ruff: noqa: E501
"""Recruiter review agent and the auto-improve loop for ATS Studio resumes.

Reviewer: screens a resume the way a recruiter reads it for this JD (must-haves, top third, clarity, quantified impact,
length, red flags) and returns shortlist / maybe / reject, the five fixes worth the most points, and rewritten bullets.
Deterministic rules always run; when an LLM key is configured it adds a short recruiter note that must pass the truth guard.

Auto-improve: generate -> score -> apply only safe fixes -> repeat (max 3 rounds, stops when the score stops improving or hits
100). Safe means: spell a verified skill the way the JD does, reorder, re-open weak bullets with an action verb using the
bullet's own words, add a summary built from verified facts. It never adds a skill or a number. When 100 isn't reachable
truthfully the result says "max truthful score" and lists exactly what the profile lacks, with the confirm-skill flow.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.agents.llm import get_provider
from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.jobs.jd_parser import analyze_jd
from app.profiles.experience import parse_month
from app.profiles.service import get_profile
from app.resumes import craft, tailor
from app.resumes import service as resumes
from app.schemas.profile import Profile
from app.schemas.resume import ParsedResume
from app.services.agent_runs import agent_run
from app.services.audit import log_action
from app.services.truth_guard import GeneratedClaims, validate_claims
from app.studio import insights, quality
from app.utils import utcnow

router = APIRouter(tags=["studio-review"])
SKILLS_FIRST = ["summary", "skills", "experience", "projects", "education", "certifications"]
MAX_ROUNDS = 3


# ------------------------------------------------------------------ recruiter review

def _gaps(r: ParsedResume) -> list[str]:
    """Employment gaps over 6 months between consecutive roles, read from the resume's own dates."""
    spans = []
    for e in r.experience:
        s = parse_month(e.start_date) if e.start_date else None
        en = parse_month(e.end_date) if e.end_date else None
        if s:
            spans.append((s, en if not e.is_current else None, e))
    spans.sort(key=lambda x: x[0])
    out = []
    for (_s1, e1, a), (s2, _e2, b) in zip(spans, spans[1:], strict=False):
        if e1 and (s2[0] * 12 + s2[1]) - (e1[0] * 12 + e1[1]) > 6:
            out.append(f"Gap of {(s2[0] * 12 + s2[1]) - (e1[0] * 12 + e1[1])} months between {a.company or 'a role'} and {b.company or 'the next role'}")
    return out


def _stuffing(r: ParsedResume, text: str) -> list[str]:
    flags = []
    if len(r.skills) > 40:
        flags.append(f"{len(r.skills)} skills listed: a long list reads as keyword stuffing. Keep the 20-30 that matter.")
    low = text.lower()
    for s in r.skills[:25]:
        if len(s) > 2 and low.count(s.lower()) > 8:
            flags.append(f"“{s}” appears {low.count(s.lower())} times.")
            break
    return flags


def review(r: ParsedResume, jd, profile: Profile | None = None, template: str = "modern", order: list[str] | None = None,
           headline: str | None = None) -> dict:
    rep = tailor.ats_report(r, jd)
    view = quality.six_second_view(r, jd, template, order, headline)
    bl = quality.check_resume(r)
    bullets = quality.bullets_of(r)
    quantified = sum(1 for b in bullets if craft.has_number(b["text"]))
    qshare = quantified / len(bullets) if bullets else 0.0
    gaps, stuffing = _gaps(r), _stuffing(r, tailor.resume_text(r))
    flags = [*gaps, *stuffing]
    if not (r.email and r.phone):
        flags.append("Contact details incomplete.")
    parts = {
        "must_haves": round(35 * rep["required_coverage"] / 100),
        "top_third": round(20 * (view["top_third_coverage"] if view["top_third_coverage"] is not None else 100) / 100),
        "clarity": round(15 * (bl["score"] if bl["score"] is not None else 70) / 100),
        "quantified_impact": round(10 * min(1.0, qshare / 0.4)),  # 40% of bullets with a real number is full marks
        "length": 10 if view["one_page"]["pages"] <= 1.15 else 6 if view["one_page"]["pages"] <= 2 else 2,
        "red_flags": max(0, 10 - 4 * len(flags)),
    }
    score = sum(parts.values())
    verdict = "shortlist" if score >= 75 and rep["required_coverage"] >= 60 else "reject" if score < 50 or rep["required_coverage"] < 30 else "maybe"

    fixes: list[dict] = []
    if rep["missing_required"]:
        fixes.append({"fix": f"Required by the JD but not in your verified profile: {', '.join(rep['missing_required'][:6])}", "points": round(35 * (
            len(rep["missing_required"]) / max(1, len(set(jd.required_skills)))) ), "how": "If you really have them, confirm them in the checklist; otherwise leave them off.",
            "kind": "confirm_skills"})
    lost = [h["keyword"] for h in view["heatmap"] if not h["in_top_third"] and h["total"]]
    if lost:
        fixes.append({"fix": f"Move these must-haves into the top third (summary or first skills): {', '.join(lost[:5])}",
                      "points": round(20 * len(lost) / max(1, len(view["heatmap"]))), "how": "Use the Skills-first section order.", "kind": "order"})
    if bl["weak"]:
        fixes.append({"fix": f"{bl['weak']} bullet(s) are weak (verb, outcome, length or passive voice)", "points": round(15 * bl["weak"] / max(1, bl["total"])),
                      "how": "Apply the rewrites below.", "kind": "bullets"})
    if bullets and qshare < 0.4:
        fixes.append({"fix": "Few bullets show a measurable result", "points": 10 - parts["quantified_impact"],
                      "how": "Add the real number to the bullets you know the result of. Saige won't invent one.", "kind": "metrics"})
    if view["one_page"]["pages"] > 1.15:
        fixes.append({"fix": view["one_page"]["hint"] or "Resume runs long", "points": 10 - parts["length"], "how": "Trim older bullets.", "kind": "length"})
    for fl in flags:
        fixes.append({"fix": fl, "points": 4, "how": "Gaps can't be hidden truthfully: add a one-line reason in your profile if you want." if "Gap" in fl else "Edit the resume.",
                      "kind": "flag"})
    fixes = [f for f in sorted(fixes, key=lambda f: -f["points"]) if f["points"] > 0][:5]
    rewrites = [{"where": i["where"], "original": i["original"], "rewrite": i["rewrite"], "ask": i["ask"], "flags": [f["code"] for f in i["flags"]]}
                for i in bl["items"] if i["flags"] and i["rewrite"]][:5]
    return {"verdict": verdict, "score": score, "parts": parts, "ats_score": rep["score"], "top_fixes": fixes, "rewrites": rewrites,
            "red_flags": flags, "top_third_coverage": view["top_third_coverage"], "note": None, "engine": "deterministic"}


class _Note(BaseModel):
    note: str = Field(description="Two sentences, recruiter voice, using only the provided findings")


async def llm_note(result: dict, profile: Profile, title: str, company: str) -> str | None:
    """Optional recruiter-voice summary of the findings; dropped unless the truth guard passes it."""
    provider = get_provider()
    if provider is None:
        return None
    facts = (f"Verdict: {result['verdict']} (score {result['score']}/100). Fixes: " + "; ".join(f["fix"] for f in result["top_fixes"]))
    try:
        out = await provider.extract(system="You are a recruiter. Summarise the review in two sentences. Use ONLY the findings given; add no skills, numbers or facts.",
                                     prompt=f"Role: {title} at {company}\n<findings>\n{facts}\n</findings>", schema=_Note)
    except Exception:  # noqa: BLE001 - the deterministic review stands on its own
        return None
    text = getattr(out, "note", None) if out else None
    if text and validate_claims(GeneratedClaims(text=text), profile).passed:
        result["engine"] = f"deterministic+{provider.name}"
        return text.strip()
    return None


# ------------------------------------------------------------------ auto-improve

def _safe_pass(parsed: ParsedResume, profile: Profile, jd, jd_text: str, title: str, matched: list[str]) -> tuple[ParsedResume, list[str]]:
    from app.studio.router import _surface_verified

    applied: list[str] = []
    out = _surface_verified(parsed, profile, jd, jd_text)
    if out.skills != parsed.skills:
        applied.append("Verified skills spelled and ordered the way the JD writes them")
    if not out.summary:
        s = tailor.template_summary(profile, title, matched, jd_text)
        if s:
            out = out.model_copy(update={"summary": s})
            applied.append("Added a summary built from your verified facts")
    fixed = 0
    exp = []
    for e in out.experience:
        def fix(items: list[str]) -> list[str]:
            nonlocal fixed
            res = []
            for b in items:
                nb = craft.condense(craft.strengthen(b))
                fixed += nb != b
                res.append(nb)
            return res
        exp.append(e.model_copy(update={"achievements": fix(e.achievements), "responsibilities": fix(e.responsibilities)}))
    if fixed:
        out = out.model_copy(update={"experience": exp})
        applied.append(f"Re-opened or trimmed {fixed} bullet(s) using your own words")
    return out, applied


def improve(parsed: ParsedResume, profile: Profile, jd, jd_text: str, title: str, template: str = "modern",
            order: list[str] | None = None) -> dict:
    matched = [s for s in jd.required_skills + jd.preferred_skills if s in tailor.resume_text(parsed) or s in parsed.skills]
    best, best_rep = parsed, tailor.ats_report(parsed, jd)
    start = best_rep["score"]
    rounds, applied_all = [], []
    for n in range(1, MAX_ROUNDS + 1):
        cand, applied = _safe_pass(best, profile, jd, jd_text, title, matched)
        rep = tailor.ats_report(cand, jd)
        bad = [v for v in tailor.validate_resume(cand, profile)["violations"]]
        if bad or not applied or rep["score"] < best_rep["score"]:
            rounds.append({"round": n, "score": best_rep["score"], "applied": [], "stopped": "no safe change left" if not bad else "failed truth check"})
            break
        gain = rep["score"] - best_rep["score"]
        best, best_rep = cand, rep
        applied_all += [a for a in applied if a not in applied_all]
        rounds.append({"round": n, "score": rep["score"], "applied": applied, "gain": gain})
        if rep["score"] >= 100 or (gain <= 0 and n > 1):
            break
    new_order = None
    if tailor.ats_report(best, jd)["score"] >= 0:
        base_cov = quality.six_second_view(best, jd, template, order)["top_third_coverage"]
        alt_cov = quality.six_second_view(best, jd, template, SKILLS_FIRST)["top_third_coverage"]
        if alt_cov is not None and base_cov is not None and alt_cov > base_cov:
            new_order = SKILLS_FIRST
            applied_all.append(f"Skills-first section order: must-haves in the top third {base_cov}% to {alt_cov}%")
    final = best_rep["score"]
    # what stops 100, honestly: skills the profile doesn't have, and checks that need the user's data
    would_be = None
    missing = best_rep["missing_required"] + best_rep["missing_preferred"]
    if missing:
        would_be = tailor.ats_report(best.model_copy(update={"skills": [*best.skills, *missing]}), jd)["score"]
    blockers = {"missing_skills": [{"skill": s, "kind": "required" if s in best_rep["missing_required"] else "preferred"} for s in missing],
                "failed_checks": [x["check"] for x in best_rep["checks"] if not x["passed"]]}
    return {"resume": best, "before": start, "after": final, "reached_100": final >= 100, "rounds": rounds, "applied": applied_all,
            "section_order": new_order, "max_truthful_score": final, "score_if_confirmed": would_be, "blockers": blockers}


async def _load(db: AsyncIOMotorDatabase, uid: str, resume_id: str):
    d = await resumes.get_owned(db, uid, resume_id)
    cur = await resumes.current_version(db, d)
    if not cur:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume has no content")
    return d, ParsedResume.model_validate(cur["parsed"]), analyze_jd(d.get("target_title") or "", d.get("jd_text") or "")


@router.get("/resumes/{resume_id}/review")
async def recruiter_review(resume_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    d, parsed, jd = await _load(db, uid, resume_id)
    profile = await get_profile(db, uid)
    async with agent_run(db, "recruiter_review", uid, {"resume_id": resume_id}) as run:
        out = review(parsed, jd, profile, d.get("template") or "modern", d.get("section_order"), (d.get("headline") or "").split(" · ")[0] or None)
        out["note"] = await llm_note(out, profile, d.get("target_title") or "", d.get("company") or "")
        run.output = {"verdict": out["verdict"], "score": out["score"]}
        run.action(f"Reviewed as a recruiter: {out['verdict']} ({out['score']}/100)")
    await log_action(db, user_id=uid, action="studio.recruiter_review", entity="resume", entity_id=resume_id,
                     details={"verdict": out["verdict"], "score": out["score"]})
    return out


@router.post("/resumes/{resume_id}/auto-improve")
async def auto_improve(resume_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Up to 3 rounds of safe fixes toward a higher ATS score. Saves a new version only when the score improves."""
    uid = user["_id"]
    d, parsed, jd = await _load(db, uid, resume_id)
    profile = await get_profile(db, uid)
    async with agent_run(db, "resume_auto_improve", uid, {"resume_id": resume_id}) as run:
        out = improve(parsed, profile, jd, d.get("jd_text") or "", d.get("target_title") or "", d.get("template") or "modern", d.get("section_order"))
        saved = False
        if out["resume"] != parsed and (out["after"] > out["before"] or out["section_order"]) and out["applied"]:
            new = out["resume"]
            await resumes.add_version(db, d, parsed=new, raw_text=tailor.resume_text(new), source="studio", changes=out["applied"],
                                      base_resume_id=d.get("base_resume_id"), job_id=d.get("job_id"))
            upd: dict = {"ats": tailor.ats_report(new, jd), "updated_at": utcnow(), "skill_checklist": insights.checklist(profile, tailor.ats_report(new, jd))}
            if out["section_order"]:
                upd["section_order"] = out["section_order"]
            await db[c.RESUMES].update_one({"_id": resume_id}, {"$set": upd})
            saved = True
        run.output = {"before": out["before"], "after": out["after"], "saved": saved}
        run.action(f"Auto-improve {out['before']} to {out['after']}")
    await log_action(db, user_id=uid, action="studio.auto_improve", entity="resume", entity_id=resume_id,
                     details={"before": out["before"], "after": out["after"], "saved": saved})
    out["resume"] = out["resume"].model_dump()
    return {**out, "saved": saved,
            "message": ("Reached 100." if out["reached_100"] else f"Max truthful score: {out['after']}. "
                        + ("Confirm the skills you really have to go higher." if out["blockers"]["missing_skills"] else ""))}

"""Profile Agent: analyse target-role JD trends and produce truthful platform improvements.

Every generated value is built only from the verified master profile and then passed through the
truth guard; anything that fails validation is never proposed. Skills the market wants but the
candidate has not verified are reported as learning gaps, never added to any profile.
"""

import re
from collections import Counter
from datetime import date, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import collections as c
from app.jobs.matching import candidate_skills
from app.schemas.platform import LinkedInProfile, NaukriProfile, SkillTrend
from app.schemas.profile import Profile
from app.services.skills_vocab import canonical, normalize_key
from app.services.truth_guard import GeneratedClaims, validate_claims
from app.utils import utcnow

TREND_WINDOW_DAYS = 30
MIN_JOBS_FOR_WINDOW = 5


def _key(s: str) -> str:
    return normalize_key(canonical(s))


async def skill_trends(db: AsyncIOMotorDatabase, user_id: str, profile: Profile) -> tuple[list[SkillTrend], list[dict]]:
    """Share of recent relevant JDs that ask for each skill (spec section 30)."""
    since = utcnow() - timedelta(days=TREND_WINDOW_DAYS)
    base = {"user_id": user_id, "status": {"$ne": "rejected"},
            "match.classification": {"$ne": "Not Relevant"}}
    jobs = await db[c.JOBS].find({**base, "created_at": {"$gte": since}}).to_list(length=1000)
    if len(jobs) < MIN_JOBS_FOR_WINDOW:
        jobs = await db[c.JOBS].find(base).sort("created_at", -1).to_list(length=1000)
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    for j in jobs:
        seen = set()
        for s in (j.get("analysis") or {}).get("skills", []):
            k = _key(s)
            if k not in seen:
                seen.add(k)
                counts[k] += 1
                display.setdefault(k, canonical(s))
    have = candidate_skills(profile)
    n = max(len(jobs), 1)
    trends = [SkillTrend(skill=display[k], pct=round(100 * v / n, 1), jobs=v, candidate_has=k in have)
              for k, v in counts.most_common(40)]
    return trends, jobs


def _verified_skills_by_demand(profile: Profile, trends: list[SkillTrend]) -> list[str]:
    """Candidate's own skills, most in-demand first, then the rest of their verified skills."""
    have = {_key(s): s for s in profile.skills.all()}
    for e in profile.knowledge.experience:
        for t in e.technologies:
            have.setdefault(_key(t), t)
    ordered = [t.skill for t in trends if t.candidate_has and _key(t.skill) in have]
    rest = [v for k, v in have.items() if k not in {_key(s) for s in ordered}]
    return ordered + rest


def _years_phrase(profile: Profile) -> str | None:
    yrs = profile.personal.total_experience_years
    if yrs is None or yrs < 1:
        return None
    return f"{int(yrs)}+ years"


def build_headline(profile: Profile, trends: list[SkillTrend], limit: int) -> str | None:
    title = profile.personal.current_designation or (profile.knowledge.experience[0].title
                                                     if profile.knowledge.experience else None)
    if not title:
        return None
    skills = _verified_skills_by_demand(profile, trends)[:6]
    parts = [title]
    yrs = _years_phrase(profile)
    if yrs:
        parts[0] = f"{title} ({yrs})"
    headline = " | ".join(parts + skills)
    while len(headline) > limit and skills:
        skills.pop()
        headline = " | ".join(parts + skills)
    targets = [t for t in profile.preferences.target_roles if t.lower() != title.lower()]
    if targets and len(headline) + len(targets[0]) + 12 <= limit:
        headline += f" | Open to {targets[0]} roles"
    return headline[:limit]


def build_summary(profile: Profile, trends: list[SkillTrend], limit: int) -> str | None:
    """Deterministic summary assembled only from verified knowledge-base text."""
    kb = profile.knowledge
    pieces: list[str] = []
    if kb.professional_summary:
        pieces.append(kb.professional_summary.strip())
    skills = _verified_skills_by_demand(profile, trends)[:10]
    if skills:
        pieces.append("Core skills: " + ", ".join(skills) + ".")
    wins = [a for e in kb.experience for a in e.achievements][:3]
    if wins:
        pieces.append("Highlights: " + " ".join(w.rstrip(".") + "." for w in wins))
    if kb.domains:
        pieces.append("Domains: " + ", ".join(kb.domains) + ".")
    if not pieces:
        return None
    text = " ".join(pieces)
    if len(text) > limit:
        text = text[: limit - 1].rsplit(" ", 1)[0] + "…"
    return text


def validate_text(text: str, profile: Profile, *, skills: list[str] | None = None,
                  titles: list[str] | None = None) -> tuple[bool, list[str]]:
    result = validate_claims(GeneratedClaims(text=text, skills=skills or [], titles=titles or []), profile)
    return result.passed, [f"{v.type}: {v.value}" for v in result.violations]


def _present(text: str, skill: str) -> bool:
    return re.search(r"(?<![A-Za-z0-9])" + re.escape(skill) + r"(?![A-Za-z0-9+#])", text, re.I) is not None


def keyword_alignment(platform_text: str, platform_skills: list[str], trends: list[SkillTrend]) -> tuple[int, list[str]]:
    """% of the top in-demand skills the candidate truly has that appear on the platform profile."""
    wanted = [t.skill for t in trends if t.candidate_has][:12]
    if not wanted:
        return 0, []
    listed = {_key(s) for s in platform_skills}
    missing = [s for s in wanted if _key(s) not in listed and not _present(platform_text, s)]
    return round(100 * (len(wanted) - len(missing)) / len(wanted)), missing


def completeness(snapshot: dict, fields: list[tuple[str, str]]) -> tuple[int, list[str]]:
    missing = [label for key, label in fields if snapshot.get(key) in (None, "", [], {})]
    return round(100 * (len(fields) - len(missing)) / len(fields)), missing


LINKEDIN_FIELDS = [("headline", "Headline"), ("about", "About"), ("current_title", "Current title"),
                   ("skills", "Skills"), ("experience", "Experience"), ("education", "Education"),
                   ("certifications", "Certifications"), ("profile_url", "Profile URL")]
NAUKRI_FIELDS = [("headline", "Resume headline"), ("summary", "Profile summary"), ("key_skills", "Key skills"),
                 ("current_designation", "Current designation"), ("total_experience_years", "Total experience"),
                 ("employment", "Employment"), ("education", "Education"),
                 ("preferred_locations", "Preferred locations"), ("expected_salary", "Expected salary"),
                 ("notice_period_days", "Notice period"), ("resume_updated_on", "Resume updated date")]


def linkedin_suggestions(profile: Profile, li: LinkedInProfile, trends: list[SkillTrend]) -> list[dict]:
    """Returns change proposals: {field, before, after, reason, confidence}."""
    out: list[dict] = []
    top = ", ".join(t.skill for t in trends if t.candidate_has)[:120] or "your verified skills"
    headline = build_headline(profile, trends, 220)
    if headline and headline != (li.headline or ""):
        out.append({"field": "headline", "before": li.headline, "after": headline,
                    "reason": f"Lead with your verified title and the skills recent target JDs ask for most ({top}).",
                    "confidence": 0.85})
    about = build_summary(profile, trends, 2600)
    # Leave a substantial About alone if it already mentions the top in-demand skills.
    about_is_strong = bool(li.about) and len(li.about or "") > 400 and all(
        _present(li.about or "", t.skill) for t in trends[:5] if t.candidate_has)
    if about and not about_is_strong:
        if about != (li.about or ""):
            out.append({"field": "about", "before": li.about, "after": about,
                        "reason": "About section built from your verified summary, achievements and in-demand skills.",
                        "confidence": 0.75})
    ordered = _verified_skills_by_demand(profile, trends)
    listed = {_key(s) for s in li.skills}
    to_add = [s for s in ordered if _key(s) not in listed][:20]
    if to_add:
        out.append({"field": "skills", "before": li.skills, "after": li.skills + to_add,
                    "reason": f"Add {len(to_add)} verified skill(s) recruiters search for; pin the top three: "
                              + ", ".join(ordered[:3]) + ".",
                    "confidence": 0.9})
    if profile.preferences.target_roles and set(map(str.lower, li.open_to_work.titles)) != set(
            map(str.lower, profile.preferences.target_roles)):
        out.append({"field": "open_to_work.titles", "before": li.open_to_work.titles,
                    "after": profile.preferences.target_roles[:5],
                    "reason": "Match Open-to-Work job titles to your target roles (visible to recruiters only if you choose).",
                    "confidence": 0.8})
    if profile.personal.current_designation and li.current_title and \
            li.current_title.lower() != profile.personal.current_designation.lower():
        out.append({"field": "current_title", "before": li.current_title, "after": profile.personal.current_designation,
                    "reason": "LinkedIn title differs from your verified current designation.", "confidence": 0.7})
    return out


def naukri_suggestions(profile: Profile, nk: NaukriProfile, trends: list[SkillTrend], today: date) -> list[dict]:
    out: list[dict] = []
    headline = build_headline(profile, trends, 250)
    if headline and headline != (nk.headline or ""):
        out.append({"field": "headline", "before": nk.headline, "after": headline,
                    "reason": "Naukri search weighs the resume headline heavily; lead with title + in-demand verified skills.",
                    "confidence": 0.85})
    summary = build_summary(profile, trends, 1000)
    if summary and summary != (nk.summary or ""):
        out.append({"field": "summary", "before": nk.summary, "after": summary,
                    "reason": "Profile summary from your verified experience, trimmed to Naukri's 1000-character limit.",
                    "confidence": 0.75})
    ordered = _verified_skills_by_demand(profile, trends)
    listed = {_key(s) for s in nk.key_skills}
    to_add = [s for s in ordered if _key(s) not in listed]
    if to_add:
        out.append({"field": "key_skills", "before": nk.key_skills, "after": (nk.key_skills + to_add)[:50],
                    "reason": f"Add {len(to_add)} verified key skill(s) that appear in recent target JDs.",
                    "confidence": 0.9})
    p = profile.personal
    if profile.preferences.preferred_locations and set(map(str.lower, nk.preferred_locations)) != set(
            map(str.lower, profile.preferences.preferred_locations)):
        out.append({"field": "preferred_locations", "before": nk.preferred_locations,
                    "after": profile.preferences.preferred_locations[:10],
                    "reason": "Keep Naukri preferred locations in sync with your master preferences.", "confidence": 0.8})
    if profile.preferences.target_roles and set(map(str.lower, nk.preferred_roles)) != set(
            map(str.lower, profile.preferences.target_roles)):
        out.append({"field": "preferred_roles", "before": nk.preferred_roles,
                    "after": profile.preferences.target_roles[:5],
                    "reason": "Preferred roles should match your target roles.", "confidence": 0.8})
    if p.notice_period_days is not None and nk.notice_period_days != p.notice_period_days:
        out.append({"field": "notice_period_days", "before": nk.notice_period_days, "after": p.notice_period_days,
                    "reason": "Notice period differs from your master profile.", "confidence": 0.9})
    if p.expected_ctc is not None and nk.expected_salary != p.expected_ctc:
        out.append({"field": "expected_salary", "before": nk.expected_salary, "after": p.expected_ctc,
                    "reason": "Expected salary differs from your master profile.", "confidence": 0.85})
    if p.total_experience_years is not None and nk.total_experience_years != p.total_experience_years:
        out.append({"field": "total_experience_years", "before": nk.total_experience_years,
                    "after": p.total_experience_years,
                    "reason": "Total experience differs from your master profile.", "confidence": 0.9})
    stale = True
    if nk.resume_updated_on:
        try:
            stale = (today - date.fromisoformat(nk.resume_updated_on)).days > 14
        except ValueError:
            stale = True
    if stale:
        out.append({"field": "resume_updated_on", "before": nk.resume_updated_on, "after": today.isoformat(),
                    "reason": "Recruiter searches favour recently updated profiles; re-upload your latest resume "
                              "(content unchanged is fine) to refresh the date.",
                    "confidence": 0.6})
    return out


def resume_suggestions(profile: Profile, resume_skills: list[str], trends: list[SkillTrend]) -> list[dict]:
    """Master-resume improvement suggestions (spec section 32) - never rewrites automatically."""
    listed = {_key(s) for s in resume_skills}
    to_add = [t.skill for t in trends if t.candidate_has and _key(t.skill) not in listed][:15]
    if not to_add:
        return []
    return [{"field": "skills", "before": resume_skills, "after": resume_skills + to_add,
             "reason": "Verified skills that recent target JDs ask for but your master resume doesn't list.",
             "confidence": 0.85}]


FRESHNESS_VARIANTS = ("headline", "key_skills", "summary")


def naukri_freshness_edit(profile: Profile, nk: NaukriProfile, trends: list[SkillTrend], day_index: int,
                          skip_fields: frozenset[str] = frozenset()) -> dict | None:
    """One small, truthful Naukri edit per day. Naukri ranks recently modified profiles higher, so
    a daily micro-change keeps the profile fresh. Variants rotate by day; every value is built only
    from verified profile data (the caller still runs the truth guard)."""
    ordered = _verified_skills_by_demand(profile, trends)
    for step in range(len(FRESHNESS_VARIANTS)):
        variant = FRESHNESS_VARIANTS[(day_index + step) % len(FRESHNESS_VARIANTS)]
        if variant in skip_fields:  # a suggestion for this field is already waiting for the user
            continue
        # Rotate which in-demand skills lead, so consecutive days produce different wording.
        k = day_index % max(1, min(len(trends), 6))
        rotated = trends[k:] + trends[:k]
        if variant == "headline":
            after = build_headline(profile, rotated, 250)
            before = nk.headline
            reason = "Daily freshness: headline re-ordered to lead with different in-demand verified skills."
        elif variant == "key_skills":
            listed = nk.key_skills or ordered
            verified = {_key(s) for s in ordered}
            keep = [s for s in listed if _key(s) in verified]
            if len(keep) < 2:
                continue
            j = day_index % len(keep)
            after = keep[j:] + keep[:j]
            before = nk.key_skills
            reason = "Daily freshness: key skills re-ordered (same verified skills, new order)."
        else:
            after = build_summary(profile, rotated, 1000)
            before = nk.summary
            reason = "Daily freshness: summary refreshed from your verified experience."
        if after and after != before:
            return {"field": variant, "before": before, "after": after, "reason": reason, "confidence": 0.7}
    return None

"""Discover jobs for the user's target roles across official job APIs (search, then choose).

Providers are public, documented job APIs meant for exactly this use (no keys needed):
- Himalayas (filters by the user's country, e.g. India),
- Remotive and Jobicy (remote jobs; results link back to the source as their terms ask),
- Arbeitnow,
- Adzuna (optional; only when ADZUNA_APP_ID / ADZUNA_APP_KEY are set),
plus company career pages on Greenhouse / Lever / Ashby (see feed.py).

LinkedIn, Naukri and Indeed are never fetched: their terms prohibit automated access. For those,
users capture a posting with the browser extension.

Search results are scored with the deterministic JD parser (fast, no AI cost) and are NOT saved
until the user picks them.
"""

import asyncio
import logging
import re

import httpx

from app.config import get_settings
from app.jobs.jd_parser import analyze_jd, html_to_text
from app.jobs.matching import compute_match
from app.schemas.job import JobIn, MatchWeights
from app.schemas.profile import Profile

logger = logging.getLogger("saige.discover")
USER_AGENT = "SaigeAI/0.1 (personal job search assistant)"
PER_PROVIDER = 40


def http_client() -> httpx.AsyncClient:
    """Factory (patched in tests)."""
    return httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT})


def _clean(text: str | None) -> str:
    return html_to_text(text or "").strip()


def _words(q: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9+#]+", q.lower()) if len(w) > 1]


# Titles in the same family count as a match: searching "SDET" also finds "QA Automation Engineer".
# Each family is (words that may appear in the query, words that must appear in the title). Generic words
# such as "automation" or "quality" count on the query side only, so "PLC Automation Engineer" or
# "Search Quality Engineer" don't match a QA search.
ROLE_FAMILIES: list[tuple[set[str], set[str]]] = [
    ({"qa", "sdet", "sdet1", "sdet2", "test", "tester", "testing", "quality", "automation", "qe"},
     {"qa", "sdet", "sdet1", "sdet2", "test", "tester", "testing", "qe"}),
    ({"developer", "software", "backend", "frontend", "fullstack", "full-stack", "programmer", "sde"},
     {"developer", "software", "backend", "frontend", "fullstack", "full-stack", "programmer", "sde"}),
    ({"data", "analyst", "analytics", "scientist", "bi"}, {"data", "analyst", "analytics", "scientist", "bi"}),
    ({"devops", "sre", "platform", "infrastructure", "cloud"}, {"devops", "sre", "platform", "infrastructure", "cloud"}),
    ({"product", "pm"}, {"product", "pm"}),
    ({"designer", "ux", "ui"}, {"designer", "ux", "ui"}),
]
STOP = {"engineer", "senior", "junior", "lead", "staff", "principal", "and", "the", "of", "in", "ii", "iii", "remote"}


def title_matches(title: str, query: str) -> bool:
    """The title has every meaningful query word, or shares a role family with the query."""
    t = set(_words(title))
    if "quality assurance" in title.lower() or "quality engineer" in title.lower():
        t.add("qa")
    words = {w for w in _words(query) if w not in STOP} or set(_words(query))
    if words and words <= t:
        return True
    if len(words) == 1 and any(w in title.lower() for w in words if len(w) > 3):
        return True
    return any(words & q and t & tt for q, tt in ROLE_FAMILIES)


async def remotive(client: httpx.AsyncClient, query: str, location: str | None, country: str | None = None) -> list[dict]:
    r = await client.get("https://remotive.com/api/remote-jobs", params={"search": query, "limit": PER_PROVIDER})
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", [])[:PER_PROVIDER]:
        out.append({"source": "remotive", "source_job_id": str(j.get("id")), "title": j.get("title", ""),
                    "company": j.get("company_name", ""), "location": j.get("candidate_required_location") or "Remote",
                    "remote": True, "url": j.get("url"), "posted": (j.get("publication_date") or "")[:10],
                    "description": _clean(j.get("description"))})
    return out


async def arbeitnow(client: httpx.AsyncClient, query: str, location: str | None, country: str | None = None) -> list[dict]:
    r = await client.get("https://www.arbeitnow.com/api/job-board-api")
    r.raise_for_status()
    out = []
    for j in r.json().get("data", []):
        if not title_matches(j.get("title", ""), query):
            continue
        out.append({"source": "arbeitnow", "source_job_id": j.get("slug"), "title": j.get("title", ""),
                    "company": j.get("company_name", ""), "location": j.get("location") or ("Remote" if j.get("remote") else None),
                    "remote": bool(j.get("remote")), "url": j.get("url"), "posted": None,
                    "description": _clean(j.get("description"))})
        if len(out) >= PER_PROVIDER:
            break
    return out


async def adzuna(client: httpx.AsyncClient, query: str, location: str | None, country: str | None = None) -> list[dict]:
    s = get_settings()
    if not (s.adzuna_app_id and s.adzuna_app_key):
        return []
    params = {"app_id": s.adzuna_app_id, "app_key": s.adzuna_app_key, "what": query,
              "results_per_page": PER_PROVIDER, "content-type": "application/json"}
    if location:
        params["where"] = location
    r = await client.get(f"https://api.adzuna.com/v1/api/jobs/{s.adzuna_country}/search/1", params=params)
    r.raise_for_status()
    out = []
    for j in r.json().get("results", []):
        out.append({"source": "adzuna", "source_job_id": str(j.get("id")), "title": _clean(j.get("title")),
                    "company": (j.get("company") or {}).get("display_name", ""),
                    "location": (j.get("location") or {}).get("display_name"), "remote": None,
                    "url": j.get("redirect_url"), "posted": (j.get("created") or "")[:10],
                    "description": _clean(j.get("description")),
                    "salary_min": j.get("salary_min"), "salary_max": j.get("salary_max")})
    return out


async def himalayas(client: httpx.AsyncClient, query: str, location: str | None, country: str | None = None) -> list[dict]:
    """Himalayas search API: remote-friendly jobs, filtered to the user's country when known."""
    out: list[dict] = []
    for offset in (0, 20):
        params = {"q": query, "offset": offset}
        if country:
            params["country"] = country
        r = await client.get("https://himalayas.app/jobs/api/search", params=params)
        r.raise_for_status()
        jobs = r.json().get("jobs", [])
        for j in jobs:
            where = ", ".join(j.get("locationRestrictions") or []) or "Remote (worldwide)"
            posted = j.get("pubDate")
            out.append({"source": "himalayas", "source_job_id": j.get("guid"), "title": j.get("title", ""),
                        "company": j.get("companyName", ""), "location": where, "remote": True,
                        "url": j.get("applicationLink") or j.get("guid"),
                        "posted": _epoch_date(posted), "employment_type": j.get("employmentType"),
                        "description": _clean(j.get("description") or j.get("excerpt")),
                        "salary_min": _num(j.get("minSalary")), "salary_max": _num(j.get("maxSalary"))})
        if len(jobs) < 20:
            break
    return out


async def jobicy(client: httpx.AsyncClient, query: str, location: str | None, country: str | None = None) -> list[dict]:
    tag = query[:50] if len(query) >= 3 else f"{query} engineer"
    r = await client.get("https://jobicy.com/api/v2/remote-jobs", params={"count": 50, "tag": tag})
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        types = j.get("jobType") or []
        out.append({"source": "jobicy", "source_job_id": str(j.get("id")), "title": _clean(j.get("jobTitle")),
                    "company": j.get("companyName", ""), "location": f"Remote · {j.get('jobGeo') or 'Anywhere'}", "remote": True,
                    "url": j.get("url"), "posted": (j.get("pubDate") or "")[:10],
                    "employment_type": types[0] if isinstance(types, list) and types else None,
                    "description": _clean(j.get("jobDescription") or j.get("jobExcerpt"))})
    return out


def _num(v) -> float | None:
    try:
        return float(v) if v not in (None, "", "None") else None
    except (TypeError, ValueError):
        return None


def _epoch_date(v) -> str | None:
    from datetime import UTC, datetime

    try:
        return datetime.fromtimestamp(int(v), tz=UTC).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


PROVIDERS = {"adzuna": adzuna, "himalayas": himalayas, "remotive": remotive, "jobicy": jobicy, "arbeitnow": arbeitnow}


def enabled_providers() -> list[str]:
    s = get_settings()
    return [p for p in PROVIDERS if p != "adzuna" or (s.adzuna_app_id and s.adzuna_app_key)]


def to_job_in(item: dict) -> JobIn:
    desc = item.get("description") or ""
    if len(desc) < 30:  # some APIs return short snippets; keep the posting usable
        desc = f"{item.get('title', '')} at {item.get('company', '')}. {desc} See the full posting for details.".strip()
    return JobIn(title=item["title"][:200], company=(item.get("company") or "Unknown company")[:200], description=desc[:60000],
                 location=item.get("location"), remote=item.get("remote"), application_url=item.get("url") or None,
                 salary_min=item.get("salary_min"), salary_max=item.get("salary_max"),
                 employment_type=(item.get("employment_type") or "")[:40] or None, posted_date=(item.get("posted") or "")[:40] or None,
                 source=item.get("source", "discover"), source_job_id=item.get("source_job_id"))


def score(item: dict, profile: Profile, weights: MatchWeights) -> dict | None:
    try:
        job_in = to_job_in(item)
    except ValueError:
        return None
    jd = analyze_jd(job_in.title, job_in.description)
    job = {"title": job_in.title, "company": job_in.company, "location": job_in.location, "remote": job_in.remote,
           "salary_min": job_in.salary_min, "salary_max": job_in.salary_max, "skills": jd.skills}
    m = compute_match(profile, job, jd, weights)
    return {**item, "description": job_in.description, "score": m.overall, "classification": m.classification,
            "matched_skills": m.matched_skills[:8], "missing_skills": m.missing_required_skills[:6],
            "exp_min": jd.experience_min, "exp_max": jd.experience_max, "seniority": jd.seniority,
            "employment_type": item.get("employment_type") or jd.employment_type}


async def _guarded(coro, seconds: float = 20):
    return await asyncio.wait_for(coro, seconds)


async def search(query: str, location: str | None, profile: Profile, weights: MatchWeights, country: str | None = None) -> dict:
    """Query every enabled provider concurrently; a failing provider is reported, not fatal."""
    names = enabled_providers()
    async with http_client() as client:
        results = await asyncio.gather(*(_guarded(PROVIDERS[n](client, query, location, country)) for n in names),
                                       return_exceptions=True)
    items, errors = [], {}
    for name, res in zip(names, results, strict=True):
        if isinstance(res, Exception):
            logger.warning("discover provider failed", extra={"provider": name, "error": str(res)})
            errors[name] = "unavailable right now"
            continue
        items.extend(res)
    seen, scored = set(), []
    for it in items:
        if it.get("source") != "adzuna" and not title_matches(it.get("title", ""), query):
            continue  # full-text search APIs also return unrelated roles
        key = (it.get("url") or "").split("?")[0] or f"{it['title']}|{it['company']}".lower()
        if key in seen or not it.get("title"):
            continue
        seen.add(key)
        s = score(it, profile, weights)
        if s:
            scored.append(s)
    scored.sort(key=lambda x: -x["score"])
    return {"query": query, "location": location, "providers": names, "errors": errors, "results": scored[:120]}

"""Discover jobs for the user's target roles across official job APIs (search, then choose).

Providers are public, documented job APIs meant for exactly this use:
- Remotive (remote jobs, no key; results link back to Remotive as its terms ask),
- Arbeitnow (no key),
- Adzuna (strong India coverage; needs a free app id/key: ADZUNA_APP_ID / ADZUNA_APP_KEY),
plus jobs already fetched from the company career boards the user follows (Greenhouse/Lever/Ashby).

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


def title_matches(title: str, query: str) -> bool:
    """At least one meaningful query word appears in the title (SDET, QA, automation, ...)."""
    t = title.lower()
    stop = {"engineer", "senior", "junior", "lead", "and", "the", "of", "in", "ii", "iii"}
    words = [w for w in _words(query) if w not in stop] or _words(query)
    return any(w in t for w in words)


async def remotive(client: httpx.AsyncClient, query: str, location: str | None) -> list[dict]:
    r = await client.get("https://remotive.com/api/remote-jobs", params={"search": query, "limit": PER_PROVIDER})
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", [])[:PER_PROVIDER]:
        out.append({"source": "remotive", "source_job_id": str(j.get("id")), "title": j.get("title", ""),
                    "company": j.get("company_name", ""), "location": j.get("candidate_required_location") or "Remote",
                    "remote": True, "url": j.get("url"), "posted": (j.get("publication_date") or "")[:10],
                    "description": _clean(j.get("description"))})
    return out


async def arbeitnow(client: httpx.AsyncClient, query: str, location: str | None) -> list[dict]:
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


async def adzuna(client: httpx.AsyncClient, query: str, location: str | None) -> list[dict]:
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


PROVIDERS = {"adzuna": adzuna, "remotive": remotive, "arbeitnow": arbeitnow}


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
            "matched_skills": m.matched_skills[:8], "missing_skills": m.missing_required_skills[:6]}


async def search(query: str, location: str | None, profile: Profile, weights: MatchWeights) -> dict:
    """Query every enabled provider concurrently; a failing provider is reported, not fatal."""
    names = enabled_providers()
    async with http_client() as client:
        results = await asyncio.gather(*(PROVIDERS[n](client, query, location) for n in names), return_exceptions=True)
    items, errors = [], {}
    for name, res in zip(names, results, strict=True):
        if isinstance(res, Exception):
            logger.warning("discover provider failed", extra={"provider": name, "error": str(res)})
            errors[name] = "unavailable right now"
            continue
        items.extend(res)
    seen, scored = set(), []
    for it in items:
        key = (it.get("url") or "").split("?")[0] or f"{it['title']}|{it['company']}".lower()
        if key in seen or not it.get("title"):
            continue
        seen.add(key)
        s = score(it, profile, weights)
        if s:
            scored.append(s)
    scored.sort(key=lambda x: -x["score"])
    return {"query": query, "location": location, "providers": names, "errors": errors, "results": scored[:120]}

"""Fetch openings from public careers APIs and normalise them to feed items.

Every fetcher takes the company, the user's roles and returns items shaped like the Jobs-for-you feed:
{source, source_job_id, title, company, company_id, location, remote, url, posted, description, employment_type}.
Only titles that match one of the user's roles are kept, and full descriptions are fetched for at most
DETAIL_LIMIT postings per company (the rest are scored on title and location only), so one scan stays polite
and fast even across a hundred companies.
"""

import asyncio
import re
from datetime import UTC, datetime, timedelta

import httpx

from app.careers.catalog import Company
from app.jobs import discover
from app.jobs.jd_parser import html_to_text

USER_AGENT = "SaigeAI/0.1 (personal job search assistant)"
DETAIL_LIMIT = 8
WORKDAY_PAGE = 20
WORKDAY_PAGES = 2
_ID = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_PATH = re.compile(r"^/job/[A-Za-z0-9_./%()-]{1,300}$")


def http_client() -> httpx.AsyncClient:
    """Factory (patched in tests)."""
    return httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                             follow_redirects=False, limits=httpx.Limits(max_connections=24))


def wanted(title: str, roles: list[str]) -> bool:
    return any(discover.title_matches(title or "", r) for r in roles)


def _today() -> datetime:
    return datetime.now(UTC)


def workday_posted(text: str | None) -> str | None:
    """'Posted Today' / 'Posted Yesterday' / 'Posted 3 Days Ago' / 'Posted 30+ Days Ago' -> ISO date (approx.)."""
    t = (text or "").lower()
    if "today" in t:
        days = 0
    elif "yesterday" in t:
        days = 1
    else:
        m = re.search(r"(\d+)\+?\s*day", t)
        if not m:
            return None
        days = int(m.group(1))
    return (_today() - timedelta(days=days)).date().isoformat()


def amazon_posted(text: str | None) -> str | None:
    try:
        return datetime.strptime(re.sub(r"\s+", " ", text or "").strip(), "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def _item(co: Company, **kw) -> dict:
    return {"company": co.name, "company_id": co.id, "remote": None, "employment_type": None, "description": "", **kw}


async def _json(resp_coro):
    resp = await resp_coro
    resp.raise_for_status()
    return resp.json()


# ------------------------------------------------------------------ Greenhouse / Lever / Ashby

async def greenhouse(client: httpx.AsyncClient, co: Company, roles: list[str]) -> list[dict]:
    base = f"https://boards-api.greenhouse.io/v1/boards/{co.board}/jobs"
    jobs = [j for j in (await _json(client.get(base))).get("jobs", []) if wanted(j.get("title", ""), roles)]
    details = await asyncio.gather(*(_json(client.get(f"{base}/{j['id']}")) for j in jobs[:DETAIL_LIMIT]), return_exceptions=True)
    content = {j["id"]: d.get("content") for j, d in zip(jobs, details, strict=False) if isinstance(d, dict)}
    return [_item(co, source="greenhouse", source_job_id=str(j["id"]), title=j.get("title", ""),
                  location=(j.get("location") or {}).get("name"), url=j.get("absolute_url"),
                  posted=(j.get("first_published") or j.get("updated_at") or "")[:10] or None,
                  description=html_to_text(content.get(j["id"]) or "")) for j in jobs]


async def lever(client: httpx.AsyncClient, co: Company, roles: list[str]) -> list[dict]:
    out = []
    for j in await _json(client.get(f"https://api.lever.co/v0/postings/{co.board}", params={"mode": "json"})):
        if not wanted(j.get("text", ""), roles):
            continue
        cats = j.get("categories") or {}
        desc = "\n".join([j.get("descriptionPlain") or "",
                          *(f"{b.get('text', '')}\n{html_to_text(b.get('content', ''))}" for b in j.get("lists", [])),
                          j.get("additionalPlain") or ""])
        out.append(_item(co, source="lever", source_job_id=str(j.get("id")), title=j.get("text", ""), location=cats.get("location"),
                         remote={"remote": True, "onsite": False}.get(j.get("workplaceType") or ""), url=j.get("hostedUrl"),
                         posted=discover._epoch_date((j.get("createdAt") or 0) // 1000), employment_type=cats.get("commitment"),
                         description=desc.strip()))
    return out


async def ashby(client: httpx.AsyncClient, co: Company, roles: list[str]) -> list[dict]:
    data = await _json(client.get(f"https://api.ashbyhq.com/posting-api/job-board/{co.board}"))
    return [_item(co, source="ashby", source_job_id=str(j.get("id")), title=j.get("title", ""), location=j.get("location"),
                  remote=j.get("isRemote"), url=j.get("jobUrl"), posted=(j.get("publishedAt") or "")[:10] or None,
                  employment_type=j.get("employmentType"),
                  description=j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml") or ""))
            for j in data.get("jobs", []) if j.get("isListed", True) and wanted(j.get("title", ""), roles)]


# ------------------------------------------------------------------ Workday

async def workday(client: httpx.AsyncClient, co: Company, roles: list[str]) -> list[dict]:
    if not (_ID.match(co.board) and _ID.match(co.wd_site) and re.fullmatch(r"wd\d{1,3}", co.wd_host)):
        raise ValueError("invalid workday tenant")
    host = f"https://{co.board}.{co.wd_host}.myworkdayjobs.com"
    api = f"{host}/wday/cxs/{co.board}/{co.wd_site}"
    seen: dict[str, dict] = {}
    for role in roles:
        for page in range(WORKDAY_PAGES):
            body = {"appliedFacets": {}, "limit": WORKDAY_PAGE, "offset": page * WORKDAY_PAGE, "searchText": role}
            data = await _json(client.post(f"{api}/jobs", json=body))
            posts = data.get("jobPostings") or []
            for p in posts:
                path = p.get("externalPath") or ""
                if _PATH.match(path) and path not in seen and wanted(p.get("title", ""), roles):
                    seen[path] = p
            if len(posts) < WORKDAY_PAGE:
                break
    paths = list(seen)
    details = await asyncio.gather(*(_json(client.get(f"{api}{p}")) for p in paths[:DETAIL_LIMIT]), return_exceptions=True)
    info = {p: (d.get("jobPostingInfo") or {}) for p, d in zip(paths, details, strict=False) if isinstance(d, dict)}
    out = []
    for path, p in seen.items():
        d = info.get(path, {})
        loc = d.get("location") or p.get("locationsText")
        remote = True if re.search(r"remote", f"{d.get('remoteType') or ''} {loc or ''}", re.I) else None
        out.append(_item(co, source="workday", source_job_id=(p.get("bulletFields") or [path.rsplit("_", 1)[-1]])[0],
                         title=p.get("title", ""), location=loc, remote=remote, url=d.get("externalUrl") or f"{host}/en-US/{co.wd_site}{path}",
                         posted=(d.get("startDate") or "")[:10] or workday_posted(p.get("postedOn")),
                         employment_type=d.get("timeType"), description=html_to_text(d.get("jobDescription") or "")))
    return out


# ------------------------------------------------------------------ Amazon Jobs

ISO3 = {"india": "IND", "united states": "USA", "usa": "USA", "united kingdom": "GBR", "uk": "GBR", "canada": "CAN",
        "germany": "DEU", "singapore": "SGP", "united arab emirates": "ARE", "uae": "ARE", "australia": "AUS", "ireland": "IRL",
        "netherlands": "NLD", "japan": "JPN", "poland": "POL", "spain": "ESP", "france": "FRA"}


async def amazon(client: httpx.AsyncClient, co: Company, roles: list[str], country: str | None = None) -> list[dict]:
    seen: dict[str, dict] = {}
    code = ISO3.get((country or "").strip().lower())
    for role in roles:
        params: dict = {"base_query": role, "result_limit": 100, "sort": "recent"}
        if code:
            params["normalized_country_code[]"] = code
        data = await _json(client.get("https://www.amazon.jobs/en/search.json", params=params))
        for j in data.get("jobs") or []:
            jid = str(j.get("id_icims") or j.get("id") or "")
            if jid and jid not in seen and wanted(j.get("title", ""), roles):
                seen[jid] = j
    out = []
    for jid, j in seen.items():
        desc = "\n\n".join(x for x in (
            html_to_text(j.get("description") or ""),
            "Basic qualifications\n" + html_to_text(j.get("basic_qualifications") or "") if j.get("basic_qualifications") else "",
            "Preferred qualifications\n" + html_to_text(j.get("preferred_qualifications") or "") if j.get("preferred_qualifications") else "",
        ) if x)
        out.append(_item(co, source="amazon", source_job_id=jid, title=j.get("title", ""),
                         location=j.get("normalized_location") or j.get("location"), url=f"https://www.amazon.jobs{j.get('job_path') or ''}",
                         posted=amazon_posted(j.get("posted_date")), employment_type=j.get("job_schedule_type"), description=desc,
                         team=j.get("company_name")))
    return out


FETCHERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby, "workday": workday, "amazon": amazon}


async def fetch(client: httpx.AsyncClient, co: Company, roles: list[str], country: str | None = None) -> list[dict]:
    if co.provider == "amazon":
        return await amazon(client, co, roles, country)
    return await FETCHERS[co.provider](client, co, roles)

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
from urllib.parse import quote

import httpx

from app.careers.catalog import Company
from app.jobs import discover
from app.jobs.jd_parser import html_to_text

USER_AGENT = "SaigeAI/0.1 (personal job search assistant)"
DETAIL_LIMIT = 6
WORKDAY_PAGE = 20  # Workday's max page size; results are relevance-ranked by searchText
WORKDAY_PAGES = 1
_ID = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_PATH = re.compile(r"^/job/[A-Za-z0-9_./%()-]{1,300}$")


def http_client() -> httpx.AsyncClient:
    """Factory (patched in tests)."""
    return httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                             follow_redirects=False, limits=httpx.Limits(max_connections=40))


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
    data = await _json(client.get(f"https://api.ashbyhq.com/posting-api/job-board/{co.board}?includeCompensation=true"))
    return [_item(co, source="ashby", source_job_id=str(j.get("id")), title=j.get("title", ""), location=j.get("location"),
                  remote=j.get("isRemote"), url=j.get("jobUrl"), posted=(j.get("publishedAt") or "")[:10] or None,
                  employment_type=j.get("employmentType"), comp_summary=(j.get("compensation") or {}).get("compensationTierSummary"),
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


# ------------------------------------------------------------------ SmartRecruiters (official public Posting API)

ISO2 = {"india": "in", "united states": "us", "usa": "us", "united kingdom": "gb", "uk": "gb", "canada": "ca", "germany": "de",
        "singapore": "sg", "united arab emirates": "ae", "uae": "ae", "australia": "au", "ireland": "ie", "netherlands": "nl"}


async def smartrecruiters(client: httpx.AsyncClient, co: Company, roles: list[str], country: str | None = None) -> list[dict]:
    if not _ID.match(co.board):
        raise ValueError("invalid SmartRecruiters company id")
    api = f"https://api.smartrecruiters.com/v1/companies/{co.board}/postings"
    code = ISO2.get((country or "").strip().lower())
    seen: dict[str, dict] = {}
    for role in roles:
        params: dict = {"q": role, "limit": 100}
        if code:
            params["country"] = code
        for p in (await _json(client.get(api, params=params))).get("content") or []:
            if p.get("id") and p["id"] not in seen and wanted(p.get("name", ""), roles):
                seen[p["id"]] = p
    ids = list(seen)
    details = await asyncio.gather(*(_json(client.get(f"{api}/{i}")) for i in ids[:DETAIL_LIMIT]), return_exceptions=True)
    text = {}
    for i, d in zip(ids, details, strict=False):
        if isinstance(d, dict):
            secs = ((d.get("jobAd") or {}).get("sections") or {})
            keys = ("jobDescription", "qualifications", "additionalInformation")
            text[i] = "\n\n".join(html_to_text((secs.get(k) or {}).get("text") or "") for k in keys)
    out = []
    for i, p in seen.items():
        loc = p.get("location") or {}
        fallback = ", ".join(x for x in (loc.get("city"), (loc.get("country") or "").upper()) if x)
        place = re.sub(r"(,\s*)+,", ",", loc.get("fullLocation") or "").strip(", ") or fallback
        out.append(_item(co, source="smartrecruiters", source_job_id=i, title=p.get("name", ""), location=place or None,
                         remote=True if loc.get("remote") else None, url=f"https://jobs.smartrecruiters.com/{co.board}/{i}",
                         posted=(p.get("releasedDate") or "")[:10] or None,
                         employment_type=(p.get("typeOfEmployment") or {}).get("label"), description=text.get(i, "").strip()))
    return out


# ------------------------------------------------------------------ SAP SuccessFactors career sites (public job RSS feed)

_RSS_ITEM = re.compile(r"<item>(.*?)</item>", re.S)


def _rss_tag(block: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{tag}>", block, re.S)
    return (m.group(1) if m else "").strip()


def rss_location(title: str) -> tuple[str, str | None]:
    """'HP Data Protector Backup (Mumbai, IND-27, IN, 400708)' -> ('HP Data Protector Backup', 'Mumbai, IN')."""
    m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", title)
    if not m:
        return title, None
    parts = [x.strip() for x in m.group(2).split(",") if x.strip() and not re.search(r"\d", x)]
    return m.group(1).strip(), ", ".join(parts) or None


async def successfactors(client: httpx.AsyncClient, co: Company, roles: list[str]) -> list[dict]:
    if not re.fullmatch(r"[a-z0-9.-]{4,80}", co.host):
        raise ValueError("invalid career site host")
    seen: dict[str, dict] = {}
    for role in roles:
        resp = await client.get(f"https://{co.host}/services/rss/job/", params={"locale": "en_US", "keywords": role},
                                headers={"Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.5"})
        resp.raise_for_status()
        for block in _RSS_ITEM.findall(resp.content.decode("utf-8", "replace")):
            raw_title = html_to_text(_rss_tag(block, "title"))
            link = html_to_text(_rss_tag(block, "link")).split("?")[0]
            title, loc = rss_location(raw_title)
            if not link.startswith(f"https://{co.host}/") or link in seen or not wanted(title, roles):
                continue
            try:
                posted = datetime.strptime(_rss_tag(block, "pubDate")[:16], "%a, %d %b %Y").date().isoformat()
            except ValueError:
                posted = None
            seen[link] = _item(co, source="successfactors", source_job_id=link.rstrip("/").rsplit("/", 1)[-1], title=title,
                               location=loc, url=link, posted=posted, description=html_to_text(_rss_tag(block, "description")))
    return list(seen.values())


# ------------------------------------------------------------------ Oracle Recruiting Cloud (public candidate-experience REST)

async def oracle(client: httpx.AsyncClient, co: Company, roles: list[str]) -> list[dict]:
    if not (re.fullmatch(r"[a-z0-9.-]{4,80}\.oraclecloud\.com", co.host) and _ID.match(co.site)):
        raise ValueError("invalid Oracle careers site")
    api = f"https://{co.host}/hcmRestApi/resources/latest"
    seen: dict[str, dict] = {}
    for role in roles:
        kw = quote(role.replace('"', ""), safe="")
        url = (f"{api}/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList"
               f"&finder=findReqs;siteNumber={co.site},limit=50,keyword=%22{kw}%22,sortBy=POSTING_DATES_DESC")
        items = (await _json(client.get(url))).get("items") or [{}]
        for r in items[0].get("requisitionList") or []:
            if r.get("Id") and r["Id"] not in seen and wanted(r.get("Title", ""), roles):
                seen[r["Id"]] = r
    ids = list(seen)

    async def detail(i: str) -> dict:
        d = await _json(client.get(f"{api}/recruitingCEJobRequisitionDetails?expand=all&onlyData=true"
                                   f"&finder=ById;Id=%22{quote(i, safe='')}%22,siteNumber={co.site}"))
        return (d.get("items") or [{}])[0]

    details = await asyncio.gather(*(detail(i) for i in ids[:DETAIL_LIMIT]), return_exceptions=True)
    keys = ("ExternalDescriptionStr", "ExternalResponsibilitiesStr", "ExternalQualificationsStr")
    text = {i: "\n\n".join(html_to_text(d.get(k) or "") for k in keys)
            for i, d in zip(ids, details, strict=False) if isinstance(d, dict)}
    return [_item(co, source="oracle", source_job_id=i, title=r.get("Title", ""), location=r.get("PrimaryLocation"),
                  remote=True if "remote" in (r.get("WorkplaceType") or "").lower() else None,
                  url=f"https://{co.host}/hcmUI/CandidateExperience/en/sites/{co.site}/job/{i}", posted=(r.get("PostedDate") or "")[:10] or None,
                  description=(text.get(i) or r.get("ShortDescriptionStr") or "").strip()) for i, r in seen.items()]


FETCHERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby, "workday": workday, "amazon": amazon,
            "successfactors": successfactors, "oracle": oracle}


async def fetch(client: httpx.AsyncClient, co: Company, roles: list[str], country: str | None = None) -> list[dict]:
    if co.provider == "amazon":
        return await amazon(client, co, roles, country)
    if co.provider == "smartrecruiters":
        return await smartrecruiters(client, co, roles, country)
    return await FETCHERS[co.provider](client, co, roles)


# ------------------------------------------------------------------ one posting's full description (read on demand)

async def describe(client: httpx.AsyncClient, co: Company, job: dict) -> str:
    """The full job description for one stored posting, from the same public API it came from ("" if unavailable)."""
    jid = str(job.get("source_job_id") or "")
    if co.provider == "greenhouse" and jid.isdigit():
        d = await _json(client.get(f"https://boards-api.greenhouse.io/v1/boards/{co.board}/jobs/{jid}"))
        return html_to_text(d.get("content") or "")
    if co.provider == "workday":
        m = re.search(r"(/job/[^?#]+)", job.get("url") or "")
        if m and _PATH.match(m.group(1)) and _ID.match(co.board) and _ID.match(co.wd_site):
            api = f"https://{co.board}.{co.wd_host}.myworkdayjobs.com/wday/cxs/{co.board}/{co.wd_site}"
            d = await _json(client.get(f"{api}{m.group(1)}"))
            return html_to_text((d.get("jobPostingInfo") or {}).get("jobDescription") or "")
    if co.provider == "smartrecruiters" and _ID.match(co.board) and re.fullmatch(r"[\w-]{1,40}", jid):
        d = await _json(client.get(f"https://api.smartrecruiters.com/v1/companies/{co.board}/postings/{jid}"))
        secs = (d.get("jobAd") or {}).get("sections") or {}
        return "\n\n".join(html_to_text((secs.get(k) or {}).get("text") or "")
                           for k in ("jobDescription", "qualifications", "additionalInformation")).strip()
    if co.provider == "oracle" and re.fullmatch(r"[\w-]{1,40}", jid):
        api = f"https://{co.host}/hcmRestApi/resources/latest"
        d = await _json(client.get(f"{api}/recruitingCEJobRequisitionDetails?expand=all&onlyData=true"
                                   f"&finder=ById;Id=%22{quote(jid, safe='')}%22,siteNumber={co.site}"))
        it = (d.get("items") or [{}])[0]
        return "\n\n".join(html_to_text(it.get(k) or "") for k in
                           ("ExternalDescriptionStr", "ExternalResponsibilitiesStr", "ExternalQualificationsStr")).strip()
    return ""

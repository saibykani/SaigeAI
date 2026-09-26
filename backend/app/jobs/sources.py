"""Permitted job sources (spec section 11).

Only official, public, unauthenticated job-board APIs that ATS vendors publish for exactly this
purpose are called: Greenhouse Job Board API, Lever Postings API and Ashby Posting API. Request
URLs are always built from fixed hosts plus a validated board id, never from user-supplied hosts
(no SSRF). Platforms that prohibit automated access (LinkedIn, Naukri, Indeed, Glassdoor, ...) are
never fetched; for those the user pastes the job description.
"""

import re
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx

from app.jobs.jd_parser import html_to_text
from app.schemas.job import JobIn

_BOARD = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
USER_AGENT = "SaigeAI/0.1 (personal job search assistant)"

MANUAL_ONLY_HOSTS = ("linkedin.com", "naukri.com", "indeed.", "glassdoor.", "foundit.", "monster",
                     "instahyre.com", "cutshort.io", "wellfound.com", "angel.co", "uplers.com")


class SourceError(Exception):
    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


def http_client() -> httpx.AsyncClient:
    """Factory (patched in tests)."""
    return httpx.AsyncClient(timeout=20, headers={"User-Agent": USER_AGENT}, follow_redirects=False)


def _check(value: str, pattern: re.Pattern[str], what: str) -> str:
    if not pattern.match(value):
        raise SourceError(f"Invalid {what}")
    return value


async def _get_json(client: httpx.AsyncClient, url: str):
    try:
        resp = await client.get(url)
    except httpx.HTTPError as exc:
        raise SourceError("Job board could not be reached", 502) from exc
    if resp.status_code == 404:
        raise SourceError("Job board or posting not found", 404)
    if resp.status_code >= 400:
        raise SourceError(f"Job board returned HTTP {resp.status_code}", 502)
    return resp.json()


def _iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):  # Lever: epoch milliseconds
        return datetime.fromtimestamp(value / 1000, tz=UTC).date().isoformat()
    return str(value)[:10]


# ------------------------------------------------------------------ Greenhouse

def _greenhouse_job(j: dict, company: str) -> JobIn:
    return JobIn(
        title=j["title"], company=company,
        description=html_to_text(j.get("content") or "")
        or f"{j['title']} at {company}. The job board provided no description.",
        location=(j.get("location") or {}).get("name"),
        application_url=j.get("absolute_url"),
        source="greenhouse", source_job_id=str(j["id"]),
        posted_date=_iso(j.get("first_published") or j.get("updated_at")),
    )


async def greenhouse_board(client: httpx.AsyncClient, board: str, company: str | None) -> list[JobIn]:
    _check(board, _BOARD, "Greenhouse board token")
    base = f"https://boards-api.greenhouse.io/v1/boards/{board}"
    if not company:
        company = (await _get_json(client, base)).get("name") or board
    data = await _get_json(client, f"{base}/jobs?content=true")
    return [_greenhouse_job(j, company) for j in data.get("jobs", [])]


async def greenhouse_job(client: httpx.AsyncClient, board: str, job_id: str) -> JobIn:
    _check(board, _BOARD, "Greenhouse board token")
    _check(job_id, _ID, "job id")
    base = f"https://boards-api.greenhouse.io/v1/boards/{board}"
    company = (await _get_json(client, base)).get("name") or board
    return _greenhouse_job(await _get_json(client, f"{base}/jobs/{job_id}"), company)


# ------------------------------------------------------------------ Lever

def _lever_job(j: dict, company: str) -> JobIn:
    parts = [j.get("descriptionPlain") or html_to_text(j.get("description") or "")]
    for block in j.get("lists", []):
        parts.append(f"\n{block.get('text', '')}\n{html_to_text(block.get('content', ''))}")
    parts.append(j.get("additionalPlain") or "")
    cats = j.get("categories") or {}
    salary = j.get("salaryRange") or {}
    return JobIn(
        title=j["text"], company=company, description="\n".join(p for p in parts if p).strip(),
        location=cats.get("location"), employment_type=cats.get("commitment"),
        remote={"remote": True, "onsite": False}.get(j.get("workplaceType") or ""),
        salary_min=salary.get("min"), salary_max=salary.get("max"), currency=salary.get("currency"),
        application_url=j.get("hostedUrl") or j.get("applyUrl"),
        source="lever", source_job_id=str(j["id"]), posted_date=_iso(j.get("createdAt")),
    )


async def lever_board(client: httpx.AsyncClient, board: str, company: str | None) -> list[JobIn]:
    _check(board, _BOARD, "Lever company id")
    data = await _get_json(client, f"https://api.lever.co/v0/postings/{board}?mode=json")
    return [_lever_job(j, company or board.title()) for j in data]


async def lever_job(client: httpx.AsyncClient, board: str, job_id: str) -> JobIn:
    _check(board, _BOARD, "Lever company id")
    _check(job_id, _ID, "job id")
    j = await _get_json(client, f"https://api.lever.co/v0/postings/{board}/{job_id}?mode=json")
    return _lever_job(j, board.title())


# ------------------------------------------------------------------ Ashby

def _ashby_job(j: dict, company: str) -> JobIn:
    comp = (j.get("compensation") or {}).get("summaryComponents") or []
    salary = next((c for c in comp if c.get("compensationType") == "Salary"), {})
    return JobIn(
        title=j["title"], company=company,
        description=j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml") or ""),
        location=j.get("location"), remote=j.get("isRemote"),
        employment_type=j.get("employmentType"),
        salary_min=salary.get("minValue"), salary_max=salary.get("maxValue"),
        currency=salary.get("currencyCode"),
        application_url=j.get("jobUrl") or j.get("applyUrl"),
        source="ashby", source_job_id=str(j["id"]), posted_date=_iso(j.get("publishedAt")),
    )


async def ashby_board(client: httpx.AsyncClient, board: str, company: str | None) -> list[JobIn]:
    _check(board, _BOARD, "Ashby job board name")
    data = await _get_json(
        client, f"https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true")
    return [_ashby_job(j, company or board.title()) for j in data.get("jobs", []) if j.get("isListed", True)]


BOARD_FETCHERS = {"greenhouse": greenhouse_board, "lever": lever_board, "ashby": ashby_board}


async def job_from_url(client: httpx.AsyncClient, url: str) -> JobIn:
    """Resolve a posting URL on a supported ATS to its official API record."""
    parts = urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.")
    segs = [s for s in parts.path.split("/") if s]
    if any(h in host for h in MANUAL_ONLY_HOSTS):
        raise SourceError(
            f"{host} does not permit automated access. Open the posting and paste its job "
            "description into 'Paste JD' instead.")
    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and len(segs) >= 3 and segs[1] == "jobs":
        return await greenhouse_job(client, segs[0], segs[2])
    if host == "jobs.lever.co" and len(segs) >= 2:
        return await lever_job(client, segs[0], segs[1])
    if host == "jobs.ashbyhq.com" and len(segs) >= 2:
        board, job_id = segs[0], segs[1]
        for job in await ashby_board(client, board, None):
            if job.source_job_id == job_id:
                return job
        raise SourceError("Posting not found on that Ashby board", 404)
    raise SourceError(
        "Automatic import supports Greenhouse, Lever and Ashby posting links. For other sites, "
        "paste the job description instead.")

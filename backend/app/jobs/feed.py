"""Jobs for you: every job for the user's target roles, fetched automatically for their country.

Sources (all public and permitted, no scraping):
- job APIs in discover.py (Himalayas with a country filter, Remotive, Jobicy, Arbeitnow, optional Adzuna),
- company career pages that publish through Greenhouse / Lever / Ashby (a curated list of companies
  hiring in India, plus any board the user follows),
- job-alert emails from LinkedIn, Naukri, Indeed and other portals that already arrive in the user's
  own Gmail (alerts.py). This is how LinkedIn/Naukri jobs appear without automating those sites.

The feed is cached per user (JOB_FEED) and rebuilt when older than FEED_TTL, or on demand. Each item is
annotated with where it is (in your country / remote / abroad), walk-in details, contact emails the
posting publishes, experience range and match score. Nothing becomes a tracked job until the user
saves it (or the auto-applier prepares it).
"""

import asyncio
import hashlib
import logging
import re
from datetime import timedelta

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import collections as c
from app.jobs import discover
from app.jobs.jd_parser import html_to_text
from app.profiles.service import get_profile
from app.schemas.job import MatchWeights
from app.schemas.profile import Profile
from app.utils import as_utc, utcnow

logger = logging.getLogger("saige.feed")
FEED_TTL = timedelta(minutes=5)
MAX_ITEMS = 400
DESC_KEEP = 6000
DETAIL_FETCHES_PER_BOARD = 6

SOURCE_LABEL = {
    "himalayas": "Himalayas", "remotive": "Remotive", "jobicy": "Jobicy", "arbeitnow": "Arbeitnow", "adzuna": "Adzuna",
    "greenhouse": "Career page", "lever": "Career page", "ashby": "Career page",
    "linkedin": "LinkedIn alert", "naukri": "Naukri alert", "indeed": "Indeed alert", "foundit": "Foundit alert",
    "glassdoor": "Glassdoor alert", "instahyre": "Instahyre alert", "hirist": "Hirist alert", "cutshort": "Cutshort alert",
    "wellfound": "Wellfound alert", "shine": "Shine alert", "iimjobs": "iimjobs alert", "timesjobs": "TimesJobs alert",
    "internshala": "Internshala alert", "apna": "apna alert",
}

# Companies whose public career boards list roles in India (verified to respond). Users add more in Jobs → Career pages.
CAREER_BOARDS: list[tuple[str, str, str]] = [
    ("greenhouse", "stripe", "Stripe"), ("greenhouse", "mongodb", "MongoDB"), ("greenhouse", "zscaler", "Zscaler"),
    ("greenhouse", "gitlab", "GitLab"), ("greenhouse", "elastic", "Elastic"), ("greenhouse", "twilio", "Twilio"),
    ("greenhouse", "datadog", "Datadog"), ("greenhouse", "groww", "Groww"), ("greenhouse", "hackerrank", "HackerRank"),
    ("greenhouse", "druva", "Druva"), ("greenhouse", "databricks", "Databricks"), ("greenhouse", "cloudflare", "Cloudflare"),
    ("lever", "meesho", "Meesho"), ("lever", "cred", "CRED"), ("lever", "mindtickle", "Mindtickle"),
    ("ashby", "atlan", "Atlan"), ("ashby", "confluent", "Confluent"),
]

COUNTRY_CITIES: dict[str, list[str]] = {
    "india": ["bengaluru", "bangalore", "hyderabad", "pune", "mumbai", "chennai", "delhi", "new delhi", "gurgaon",
              "gurugram", "noida", "kolkata", "ahmedabad", "kochi", "trivandrum", "thiruvananthapuram", "coimbatore",
              "jaipur", "chandigarh", "indore", "mohali", "vizag", "visakhapatnam", "nagpur", "bhubaneswar", "mysore",
              "mysuru", "vadodara", "lucknow", "ncr", "karnataka", "telangana", "maharashtra", "tamil nadu"],
    "united states": ["usa", "u.s.", "new york", "san francisco", "seattle", "austin", "boston", "chicago", "los angeles"],
    "united kingdom": ["uk", "london", "manchester", "edinburgh", "england", "scotland"],
    "canada": ["toronto", "vancouver", "montreal", "ottawa"],
    "germany": ["berlin", "munich", "hamburg", "frankfurt", "deutschland"],
    "singapore": ["singapore"],
    "united arab emirates": ["uae", "dubai", "abu dhabi"],
    "australia": ["sydney", "melbourne", "brisbane"],
}
REMOTE_RE = re.compile(r"\b(remote|anywhere|worldwide|global|work from home|wfh)\b", re.I)
OPEN_REGION_RE = re.compile(r"\b(anywhere|worldwide|global|apac|asia)\b", re.I)


# ------------------------------------------------------------------ annotations

def _country_words(country: str) -> list[str]:
    k = country.strip().lower()
    return [k, *COUNTRY_CITIES.get(k, [])]


def scope(location: str | None, remote: bool | None, country: str | None) -> str:
    """"country" (in the user's country), "remote" (remote and open to them) or "abroad"."""
    loc = (location or "").lower()
    if country and any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", loc) for w in _country_words(country)):
        return "country"
    is_remote = bool(remote) or bool(REMOTE_RE.search(loc))
    if is_remote:
        restricted = re.sub(r"\b(remote|work from home|wfh)\b|[·(),:-]", " ", loc).strip()
        if not restricted or OPEN_REGION_RE.search(loc) or not country:
            return "remote"
    return "abroad" if loc or not country else "remote"


WALKIN_RE = re.compile(r"\bwalk[\s-]?ins?\b", re.I)
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
DATE_RE = re.compile(rf"\b(\d{{1,2}}(?:st|nd|rd|th)?[\s\-]*{_MONTH}[\s,\-]*(?:\d{{4}})?|{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s*\d{{4}})?"
                     rf"|\d{{1,2}}[/\-.]\d{{1,2}}[/\-.]\d{{2,4}})\b", re.I)
TIME_RE = re.compile(r"\b\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm)\b(?:\s*(?:-|–|to)\s*\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm))?", re.I)
VENUE_RE = re.compile(r"(?im)^\s*(?:venue|address|walk[\s-]?in (?:venue|location|address)|location of (?:the )?(?:drive|interview))"
                      r"\s*[:\-–]\s*(.{6,200})$")


def walk_in(title: str, text: str) -> dict | None:
    """Walk-in drive details when the posting announces one."""
    blob = f"{title}\n{text or ''}"
    m = WALKIN_RE.search(blob)
    if not m:
        return None
    window = blob[max(0, m.start() - 300): m.end() + 900]
    d, t, v = DATE_RE.search(window), TIME_RE.search(window), VENUE_RE.search(blob)
    return {"date": d.group(0).strip() if d else None, "time": t.group(0).strip() if t else None,
            "venue": v.group(1).strip() if v else None}


def contact_emails(text: str) -> list[str]:
    from app.recruiters.service import EMAIL_RE, NON_PERSONAL

    out = []
    for addr in dict.fromkeys(EMAIL_RE.findall(text or "")):
        addr = addr.lower().rstrip(".")
        if not NON_PERSONAL.match(addr) and not addr.endswith((".png", ".jpg", ".gif")):
            out.append(addr)
    return out[:5]


def item_id(it: dict) -> str:
    key = (it.get("url") or "").split("?")[0] or f"{it.get('title')}|{it.get('company')}".lower()
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def annotate(it: dict, country: str | None) -> dict:
    desc = it.get("description") or ""
    it["id"] = item_id(it)
    it["source_label"] = SOURCE_LABEL.get(it.get("source", ""), (it.get("source") or "").title())
    it["scope"] = scope(it.get("location"), it.get("remote"), country)
    it["walk_in"] = walk_in(it.get("title", ""), desc)
    it["hr_emails"] = contact_emails(desc)
    from app.email.portal import phones

    it["hr_phones"] = phones(desc)
    it["apply_by_email"] = bool(it["hr_emails"]) and bool(re.search(r"(send|mail|email|share)\s+(your\s+)?(cv|resume|profile)", desc, re.I))
    it["snippet"] = re.sub(r"\s+", " ", desc)[:260]
    it["description"] = desc[:DESC_KEEP]
    return it


# ------------------------------------------------------------------ company career pages

async def _board_items(client: httpx.AsyncClient, provider: str, board: str, company: str, roles: list[str],
                       country: str | None) -> list[dict]:
    def wanted(title: str, location: str | None, remote: bool | None) -> bool:
        return any(discover.title_matches(title, r) for r in roles) and scope(location, remote, country) != "abroad"

    out: list[dict] = []
    if provider == "greenhouse":
        base = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
        r = await client.get(base)
        r.raise_for_status()
        picks = [j for j in r.json().get("jobs", []) if wanted(j.get("title", ""), (j.get("location") or {}).get("name"), None)]
        details = await asyncio.gather(*(client.get(f"{base}/{j['id']}") for j in picks[:DETAIL_FETCHES_PER_BOARD]),
                                       return_exceptions=True)
        content = {j["id"]: d.json().get("content") for j, d in zip(picks, details, strict=False)
                   if not isinstance(d, Exception) and d.status_code == 200}
        for j in picks:
            out.append({"source": "greenhouse", "source_job_id": str(j["id"]), "title": j.get("title", ""), "company": company,
                        "location": (j.get("location") or {}).get("name"), "remote": None, "url": j.get("absolute_url"),
                        "posted": (j.get("first_published") or j.get("updated_at") or "")[:10],
                        "description": html_to_text(content.get(j["id"]) or "")})
    elif provider == "lever":
        r = await client.get(f"https://api.lever.co/v0/postings/{board}", params={"mode": "json"})
        r.raise_for_status()
        for j in r.json():
            cats = j.get("categories") or {}
            remote = {"remote": True, "onsite": False}.get(j.get("workplaceType") or "")
            if not wanted(j.get("text", ""), cats.get("location"), remote):
                continue
            desc = "\n".join([j.get("descriptionPlain") or "", *(f"{b.get('text', '')}\n{html_to_text(b.get('content', ''))}"
                                                                 for b in j.get("lists", []))])
            out.append({"source": "lever", "source_job_id": j.get("id"), "title": j.get("text", ""), "company": company,
                        "location": cats.get("location"), "remote": remote, "url": j.get("hostedUrl"),
                        "posted": discover._epoch_date((j.get("createdAt") or 0) // 1000), "employment_type": cats.get("commitment"),
                        "description": desc.strip()})
    else:
        r = await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{board}")
        r.raise_for_status()
        for j in r.json().get("jobs", []):
            if not j.get("isListed", True) or not wanted(j.get("title", ""), j.get("location"), j.get("isRemote")):
                continue
            out.append({"source": "ashby", "source_job_id": j.get("id"), "title": j.get("title", ""), "company": company,
                        "location": j.get("location"), "remote": j.get("isRemote"), "url": j.get("jobUrl"),
                        "posted": (j.get("publishedAt") or "")[:10], "employment_type": j.get("employmentType"),
                        "description": j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml") or "")})
    return out


async def careers(client: httpx.AsyncClient, boards: list[tuple[str, str, str]], roles: list[str], country: str | None) -> list[dict]:
    res = await asyncio.gather(*(asyncio.wait_for(_board_items(client, p, b, n, roles, country), 20) for p, b, n in boards),
                               return_exceptions=True)
    out: list[dict] = []
    for (_, board, _), r in zip(boards, res, strict=True):
        if isinstance(r, Exception):
            logger.info("career board unavailable", extra={"board": board, "error": str(r)})
            continue
        out.extend(r)
    return out


# ------------------------------------------------------------------ build + cache

def roles_for(profile: Profile) -> list[str]:
    roles = [r for r in profile.preferences.target_roles if r.strip()][:3]
    if not roles and profile.personal.current_designation:
        roles = [profile.personal.current_designation]
    return roles


def country_for(profile: Profile) -> str | None:
    p = profile.personal
    if p.country:
        return p.country.strip()
    loc = f"{p.current_location or ''} {' '.join(profile.preferences.preferred_locations)}".lower()
    for country, cities in COUNTRY_CITIES.items():
        if country in loc or any(re.search(rf"(?<![a-z]){re.escape(ci)}(?![a-z])", loc) for ci in cities):
            return country.title()
    return None


async def build(db: AsyncIOMotorDatabase, uid: str, *, profile: Profile | None = None,
                weights: MatchWeights | None = None) -> dict:
    from app.jobs import alerts
    from app.jobs.service import get_weights

    profile = profile or await get_profile(db, uid)
    weights = weights or await get_weights(db, uid)
    roles, country = roles_for(profile), country_for(profile)
    doc = {"_id": uid, "user_id": uid, "roles": roles, "country": country, "built_at": utcnow(), "errors": {}, "items": []}
    if not roles:
        doc["errors"]["profile"] = "Add a target role in your profile so Saige knows what to look for."
        await db[c.JOB_FEED].replace_one({"_id": uid}, doc, upsert=True)
        return doc

    boards = list(CAREER_BOARDS)
    async for s in db[c.JOB_SOURCES].find({"user_id": uid}, {"provider": 1, "board": 1, "company_name": 1}):
        if (s["provider"], s["board"]) not in {(p, b) for p, b, _ in boards}:
            boards.append((s["provider"], s["board"], s.get("company_name") or s["board"].title()))

    names = discover.enabled_providers()
    calls: list[tuple[str, object]] = []
    async with discover.http_client() as client:
        for n in names:
            for r in (roles if n != "arbeitnow" else roles[:1]):
                calls.append((n, discover._guarded(discover.PROVIDERS[n](client, r, None, country))))
        calls.append(("career_pages", careers(client, boards, roles, country)))
        results = await asyncio.gather(*(co for _, co in calls), return_exceptions=True)
    raw: list[dict] = []
    for (name, _), res in zip(calls, results, strict=True):
        if isinstance(res, Exception):
            doc["errors"][name] = "unavailable right now"
            continue
        raw.extend(res)
    raw.extend(await alerts.recent_items(db, uid))

    from app.automation.service import get_settings_doc, is_blocked

    settings = await get_settings_doc(db, uid)
    seen: set[str] = set()
    items: list[dict] = []
    for it in raw:
        if not it.get("title") or is_blocked(settings, it.get("company")):
            continue
        from_alert = it.get("source") in alerts.PORTALS
        if not from_alert and it.get("source") != "adzuna" and not any(discover.title_matches(it["title"], r) for r in roles):
            continue
        key = item_id(it)
        if key in seen:
            continue
        seen.add(key)
        scored = discover.score(it, profile, weights)
        if scored:
            items.append(annotate(scored, country))
    items.sort(key=lambda x: (x["scope"] == "abroad", -x["score"]))
    doc["items"] = items[:MAX_ITEMS]
    for name in list(doc["errors"]):  # a provider that failed for one role but worked for another is fine
        if any(i.get("source") == name for i in items):
            doc["errors"].pop(name)
    await db[c.JOB_FEED].replace_one({"_id": uid}, doc, upsert=True)
    return doc


async def get(db: AsyncIOMotorDatabase, uid: str, *, refresh: bool = False) -> dict:
    doc = None if refresh else await db[c.JOB_FEED].find_one({"_id": uid})
    if not doc or utcnow() - as_utc(doc["built_at"]) > FEED_TTL:
        doc = await build(db, uid)
    return doc


async def mark_saved(db: AsyncIOMotorDatabase, uid: str, items: list[dict]) -> None:
    """Link feed items to jobs already in the user's list (by canonical URL)."""
    from app.jobs.dedupe import canonical_url

    keys = {canonical_url(i["url"]): i for i in items if i.get("url")}
    for i in items:
        i["saved_job_id"] = None
    if not keys:
        return
    async for j in db[c.JOBS].find({"user_id": uid, "sources.url_key": {"$in": list(keys)}}, {"sources": 1}):
        for s in j.get("sources", []):
            if s.get("url_key") in keys:
                keys[s["url_key"]]["saved_job_id"] = j["_id"]


def public(it: dict) -> dict:
    """Feed item without the long description (the list view only needs a snippet)."""
    return {k: v for k, v in it.items() if k != "description"}

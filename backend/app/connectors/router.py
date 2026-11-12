"""Extra integrations that need no passwords and no scraping.

- Calendar feed: a private, revocable iCal URL with your interviews and follow-up dates. Subscribe once in
  Google Calendar / Outlook / Apple Calendar ("From URL") and new interviews appear automatically.
- GitHub projects: import your PUBLIC repositories (GitHub's public REST API) as profile projects. They are
  your own repos, so nothing is invented; you pick which ones to add."""

import re
import secrets
from datetime import timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.profiles.service import get_profile, update_profile
from app.schemas.profile import KnowledgeBase, ProfileUpdate, Project
from app.services.agent_runs import agent_run
from app.services.audit import log_action
from app.utils import as_utc, utcnow

router = APIRouter(tags=["connectors"])
GITHUB = "https://api.github.com"


def github_client() -> httpx.AsyncClient:
    """Factory (patched in tests)."""
    return httpx.AsyncClient(timeout=12, headers={"Accept": "application/vnd.github+json", "User-Agent": "SaigeAI"})


# ------------------------------------------------------------------ calendar feed


@router.get("/connectors/calendar")
async def calendar_feed(request: Request, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    doc = await db[c.CALENDAR_FEEDS].find_one({"user_id": user["_id"]})
    if not doc:
        doc = {"_id": secrets.token_urlsafe(24), "user_id": user["_id"], "created_at": utcnow()}
        await db[c.CALENDAR_FEEDS].insert_one(doc)
    return {"url": f"{str(request.base_url).rstrip('/')}/api/calendar/{doc['_id']}.ics"}


@router.post("/connectors/calendar/rotate")
async def rotate_feed(request: Request, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """New private URL; the old one stops working (use it if the link was shared by mistake)."""
    await db[c.CALENDAR_FEEDS].delete_many({"user_id": user["_id"]})
    await log_action(db, user_id=user["_id"], action="calendar.feed_rotated", entity="calendar")
    return await calendar_feed(request, user, db)


def _esc(v: str) -> str:
    return v.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


@router.get("/calendar/{token}.ics")
async def calendar_ics(token: str, db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Public by secret token (calendar apps can't sign in). Holds only interview and follow-up times."""
    feed = await db[c.CALENDAR_FEEDS].find_one({"_id": token})
    if not feed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown calendar")
    uid, fmt, now = feed["user_id"], "%Y%m%dT%H%M%SZ", utcnow()
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Saige AI//Job search//EN", "X-WR-CALNAME:Saige AI interviews", "CALSCALE:GREGORIAN"]
    async for i in db[c.INTERVIEWS].find({"user_id": uid, "scheduled_at": {"$gte": now - timedelta(days=30)}}).limit(200):
        start = as_utc(i["scheduled_at"])
        end = start + timedelta(minutes=i.get("duration_minutes", 60))
        lines += ["BEGIN:VEVENT", f"UID:{i['_id']}@saige.ai", f"DTSTAMP:{now.strftime(fmt)}", f"DTSTART:{start.strftime(fmt)}",
                  f"DTEND:{end.strftime(fmt)}", "SUMMARY:" + _esc(f"Interview: {i.get('role') or ''} at {i.get('company') or ''}".strip())]
        if i.get("meeting_url"):
            lines += [f"LOCATION:{_esc(i['meeting_url'])}", f"URL:{i['meeting_url']}"]
        if i.get("round"):
            lines.append(f"DESCRIPTION:{_esc(i['round'])}")
        lines.append("END:VEVENT")
    async for a in db[c.APPLICATIONS].find({"user_id": uid, "next_followup_at": {"$gte": now - timedelta(days=7)}}).limit(200):
        d = as_utc(a["next_followup_at"]).strftime("%Y%m%d")
        job = await db[c.JOBS].find_one({"_id": a.get("job_id")}, {"title": 1, "company": 1}) or {}
        lines += ["BEGIN:VEVENT", f"UID:fu-{a['_id']}@saige.ai", f"DTSTAMP:{now.strftime(fmt)}", f"DTSTART;VALUE=DATE:{d}",
                  "SUMMARY:" + _esc(f"Follow up: {job.get('title') or 'application'} at {job.get('company') or ''}".strip()), "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return Response(content="\r\n".join(lines) + "\r\n", media_type="text/calendar; charset=utf-8",
                    headers={"Cache-Control": "private, max-age=900"})


# ------------------------------------------------------------------ GitHub projects


def _username(url: str | None) -> str | None:
    m = re.search(r"github\.com/([A-Za-z0-9-]{1,39})", url or "")
    return m.group(1) if m else None


async def _repos(username: str) -> list[dict]:
    async with github_client() as client:
        r = await client.get(f"{GITHUB}/users/{username}/repos", params={"per_page": 100, "sort": "pushed", "type": "owner"})
    if r.status_code == 404:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"GitHub user “{username}” not found")
    if r.status_code != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "GitHub is unavailable right now (rate limit or outage). Try again in a few minutes.")
    return [x for x in r.json() if not x.get("fork") and not x.get("archived")]


def _pretty(name: str) -> str:
    return re.sub(r"[-_]+", " ", name).strip().title() if (name.islower() or "-" in name or "_" in name) else name


def _key(name: str) -> str:
    return re.sub(r"\W", "", name.lower())


@router.get("/connectors/github/repos")
async def github_repos(username: str | None = Query(None, max_length=39), user: dict = Depends(get_current_user),
                       db: AsyncIOMotorDatabase = Depends(db_dep)):
    p = await get_profile(db, user["_id"])
    name = (username or _username(str(p.personal.github_url or "")) or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", name):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Type your GitHub username (or add your GitHub URL in Profile).")
    have = {_key(pr.name) for pr in p.knowledge.projects}
    return {"username": name, "repos": [
        {"name": x["name"], "description": x.get("description"), "language": x.get("language"), "topics": x.get("topics") or [],
         "stars": x.get("stargazers_count", 0), "url": x.get("html_url"), "pushed_at": x.get("pushed_at"),
         "in_profile": _key(_pretty(x["name"])) in have} for x in await _repos(name)]}


class GithubImportIn(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9-]{1,39}$")
    repos: list[str] = Field(min_length=1, max_length=20)


@router.post("/connectors/github/import")
async def github_import(body: GithubImportIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    wanted = {r.lower() for r in body.repos}
    added: list[str] = []
    async with agent_run(db, "github_import", uid, {"username": body.username, "repos": body.repos}) as run:
        repos = [x for x in await _repos(body.username) if x["name"].lower() in wanted]
        p = await get_profile(db, uid)
        have = {_key(pr.name) for pr in p.knowledge.projects}
        projects = list(p.knowledge.projects)
        for x in repos:
            nm = _pretty(x["name"])[:200]
            if _key(nm) in have:
                continue
            tech = [t for t in [x.get("language"), *(x.get("topics") or [])[:6]] if t]
            projects.append(Project(name=nm, description=x.get("description") or None, technologies=tech, url=x.get("html_url")))
            added.append(nm)
        if added:
            kb = KnowledgeBase(**{**p.knowledge.model_dump(), "projects": [pr.model_dump() for pr in projects]})
            await update_profile(db, uid, ProfileUpdate(knowledge=kb), source="github_import")
        run.output = {"added": len(added)}
    await log_action(db, user_id=uid, action="profile.github_imported", entity="profile", details={"added": added})
    return {"added": added, "skipped": [r for r in body.repos if _pretty(r) not in added]}


# ------------------------------------------------------------------ coding practice (LeetCode / HackerRank public profiles)

LC_QUERY = ("query($u:String!){matchedUser(username:$u){profile{ranking}submitStatsGlobal{acSubmissionNum{difficulty count}}"
            "tagProblemCounts{advanced{tagName tagSlug problemsSolved}intermediate{tagName tagSlug problemsSolved}"
            "fundamental{tagName tagSlug problemsSolved}}}}")
CORE_TOPICS = [("Array", "array"), ("String", "string"), ("Hash Table", "hash-table"), ("Two Pointers", "two-pointers"),
               ("Sliding Window", "sliding-window"), ("Linked List", "linked-list"), ("Stack", "stack"), ("Binary Search", "binary-search"),
               ("Tree", "tree"), ("Graph", "graph"), ("Dynamic Programming", "dynamic-programming"), ("SQL", "database")]


def coding_client() -> httpx.AsyncClient:
    """Factory (patched in tests)."""
    return httpx.AsyncClient(timeout=12, headers={"User-Agent": "SaigeAI", "Referer": "https://leetcode.com"})


async def _leetcode(username: str) -> dict:
    async with coding_client() as client:
        r = await client.post("https://leetcode.com/graphql", json={"query": LC_QUERY, "variables": {"u": username}})
    u = (r.json().get("data") or {}).get("matchedUser") if r.status_code == 200 else None
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"LeetCode user “{username}” not found (or the profile is private).")
    solved = {x["difficulty"]: x["count"] for x in u["submitStatsGlobal"]["acSubmissionNum"]}
    tags = {t["tagSlug"]: t["problemsSolved"] for grp in u["tagProblemCounts"].values() for t in grp}
    return {"username": username, "solved": solved.get("All", 0), "easy": solved.get("Easy", 0), "medium": solved.get("Medium", 0),
            "hard": solved.get("Hard", 0), "ranking": (u.get("profile") or {}).get("ranking"), "topics": tags}


async def _hackerrank(username: str) -> list[dict]:
    async with coding_client() as client:
        r = await client.get(f"https://www.hackerrank.com/rest/hackers/{username}/badges")
    if r.status_code != 200:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"HackerRank user “{username}” not found.")
    return [{"name": b.get("badge_name"), "stars": b.get("stars", 0)} for b in (r.json().get("models") or []) if b.get("badge_name")]


def coding_plan(stats: dict | None) -> dict | None:
    """What to practise next: weakest core topics first, with links to the topic's problem list."""
    if not stats or not stats.get("leetcode"):
        return None
    lc = stats["leetcode"]
    weak = sorted(CORE_TOPICS, key=lambda t: lc["topics"].get(t[1], 0))[:4]
    target = "Aim for 2 medium problems a day" if lc["medium"] < 100 else "Mix in 1 hard problem every other day"
    return {"leetcode": {k: lc[k] for k in ("username", "solved", "easy", "medium", "hard", "ranking")},
            "hackerrank": stats.get("hackerrank") or [],
            "practise": [{"topic": n, "solved": lc["topics"].get(s, 0), "url": f"https://leetcode.com/tag/{s}/"} for n, s in weak],
            "tip": target}


class CodingIn(BaseModel):
    leetcode: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,40}$")
    hackerrank: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.-]{1,40}$")


@router.put("/connectors/coding")
async def coding_connect(body: CodingIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Link public coding profiles (no password). Stats are fetched now and refreshed when you press Refresh."""
    if not body.leetcode and not body.hackerrank:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Type a LeetCode or HackerRank username.")
    stats = {"leetcode": await _leetcode(body.leetcode) if body.leetcode else None,
             "hackerrank": await _hackerrank(body.hackerrank) if body.hackerrank else None}
    await db[c.INTEGRATIONS].update_one({"user_id": user["_id"], "provider": "coding"},
                                        {"$set": {"user_id": user["_id"], "provider": "coding", "usernames": body.model_dump(), "stats": stats,
                                                  "updated_at": utcnow()}}, upsert=True)
    await log_action(db, user_id=user["_id"], action="integration.coding_linked", entity="integration", details=body.model_dump())
    return {"usernames": body.model_dump(), "plan": coding_plan(stats)}


@router.get("/connectors/coding")
async def coding_status(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    doc = await db[c.INTEGRATIONS].find_one({"user_id": user["_id"], "provider": "coding"}) or {}
    return {"usernames": doc.get("usernames") or {}, "plan": coding_plan(doc.get("stats")),
            "updated_at": doc["updated_at"].isoformat() if doc.get("updated_at") else None}

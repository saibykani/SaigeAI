"""Bring every project from the user's own uploaded resumes into the verified profile.

Resume imports used to keep only the projects of one resume, so a candidate with four projects across several
resumes saw one. These are the user's own documents, so their projects are verified content; nothing is invented.
"""

import re

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import collections as c
from app.schemas.profile import Profile, ProfileUpdate, Project


def key(name: str) -> str:
    """"Video Customer Identification Platform (VCIP)" and "Video Customer Identification Platform" are one project."""
    return re.sub(r"[^a-z0-9]+", "", re.sub(r"\(.*?\)", "", (name or "").lower()))


async def resume_projects(db: AsyncIOMotorDatabase, uid: str) -> list[dict]:
    out = []
    async for r in db[c.RESUMES].find({"user_id": uid, "kind": {"$ne": "ATS Resume"}, "status": {"$ne": "deleted"}},
                                      {"current_version_id": 1}):
        v = await db[c.RESUME_VERSIONS].find_one({"_id": r.get("current_version_id")}, {"parsed.projects": 1})
        out += ((v or {}).get("parsed") or {}).get("projects") or []
    return out


def merge(profile: Profile, found: list[dict]) -> list[Project] | None:
    """Profile projects plus any new ones (or new bullets) from resumes; None when nothing changes."""
    projects = [p.model_copy(deep=True) for p in profile.knowledge.projects]
    index = {key(p.name): p for p in projects}
    changed = False
    for f in found:
        name = (f.get("name") or "").strip()[:200]
        k = key(name)
        if not k:
            continue
        hl = [h for h in (f.get("highlights") or []) if h and h.strip()]
        tech = [t for t in (f.get("technologies") or []) if t and t.strip()]
        p = index.get(k)
        if p is None:
            p = Project(name=name, highlights=hl, technologies=tech)
            projects.append(p)
            index[k] = p
            changed = True
            continue
        if len(name) > len(p.name):  # keep the fuller name, e.g. with "(VCIP)"
            p.name, changed = name, True
        seen = {h.strip().lower() for h in p.highlights}
        for h in hl:
            if h.strip().lower() not in seen:
                p.highlights.append(h)
                seen.add(h.strip().lower())
                changed = True
        for t in tech:
            if t.lower() not in {x.lower() for x in p.technologies}:
                p.technologies.append(t)
                changed = True
    return projects if changed else None


async def sync(db: AsyncIOMotorDatabase, uid: str, profile: Profile) -> tuple[Profile, list[str]]:
    """Returns the (possibly updated) profile and the names of projects added."""
    from app.profiles.service import get_profile, update_profile

    merged = merge(profile, await resume_projects(db, uid))
    if not merged:
        return profile, []
    before = {key(p.name) for p in profile.knowledge.projects}
    knowledge = profile.knowledge.model_dump(mode="json")
    knowledge["projects"] = [p.model_dump(mode="json") for p in merged]
    await update_profile(db, uid, ProfileUpdate.model_validate({"knowledge": knowledge}), source="resume_import")
    return await get_profile(db, uid), [p.name for p in merged if key(p.name) not in before]

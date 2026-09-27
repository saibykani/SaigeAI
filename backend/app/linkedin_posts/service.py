"""The LinkedIn posting agent: writes the day's post, renders its image / carousel, publishes it through
LinkedIn's official API (when connected) and keeps a day-by-day record."""

from datetime import timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from app.database import collections as c
from app.linkedin_posts import client, content, render
from app.profiles.service import get_profile
from app.services import crypto
from app.services.audit import log_action
from app.services.notify import notify
from app.utils import as_utc, new_id, utcnow

FORMATS = ("image", "carousel", "text")


def post_out(d: dict) -> dict:
    return {"id": d["_id"], "date": d.get("date"), "series": d.get("series"), "theme": d.get("theme"), "skill": d.get("skill"),
            "title": d.get("title"), "text": d.get("text"), "format": d.get("format"), "status": d.get("status"),
            "url": d.get("url"), "share_url": client.share_url(d.get("text") or "") if d.get("status") != "published" else None,
            "engine": d.get("engine"), "error": d.get("error"), "stats": d.get("stats") or {},
            "created_at": d["created_at"].isoformat(), "published_at": d["published_at"].isoformat() if d.get("published_at") else None}


async def connection(db: AsyncIOMotorDatabase, uid: str) -> dict | None:
    conn = await db[c.INTEGRATIONS].find_one({"user_id": uid, "provider": "linkedin_api"})
    if conn and conn.get("expires_at") and as_utc(conn["expires_at"]) < utcnow():
        return None
    return conn


async def create(db: AsyncIOMotorDatabase, uid: str, s, *, local_date: str) -> dict:
    """Write the next post in the series (not published yet)."""
    profile = await get_profile(db, uid)
    day = await db[c.LINKEDIN_POSTS].count_documents({"user_id": uid})
    post = await content.write_post(profile, day, s)
    fmt = s.format if s.format != "auto" else FORMATS[day % len(FORMATS)]
    now = utcnow()
    keep = ("theme", "series", "skill", "title", "text", "points", "slides")
    doc = {"_id": new_id(), "user_id": uid, "date": local_date, **{k: post[k] for k in keep},
           "format": fmt, "engine": post.get("engine"), "status": "draft", "url": None, "urn": None, "error": None,
           "stats": {}, "created_at": now, "updated_at": now, "published_at": None}
    await db[c.LINKEDIN_POSTS].insert_one(doc)
    return doc


def media(doc: dict, name: str, role: str) -> tuple[bytes | None, bytes | None]:
    if doc.get("format") == "image":
        png = render.card(doc, name, role)
        return (png, None) if png else (None, render.carousel(doc, name, role, single=True))
    if doc.get("format") == "carousel":
        return None, render.carousel(doc, name, role)
    return None, None


async def publish(db: AsyncIOMotorDatabase, uid: str, doc: dict) -> dict:
    """Post it on LinkedIn (official API). Without a connection it's marked ready for one-click manual posting."""
    profile = await get_profile(db, uid)
    name, role = profile.personal.name or "", profile.personal.current_designation or ""
    conn = await connection(db, uid)
    now = utcnow()
    if not conn:
        await db[c.LINKEDIN_POSTS].update_one({"_id": doc["_id"]}, {"$set": {"status": "ready", "updated_at": now}})
        await notify(db, user_id=uid, kind="linkedin_post", title=f"LinkedIn post ready · {doc['series']}",
                     body="Connect LinkedIn in LinkedIn Posts to publish automatically, or tap to post it now.", link="/linkedin")
        return await db[c.LINKEDIN_POSTS].find_one({"_id": doc["_id"]})
    image, document = media(doc, name, role)
    try:
        urn = await client.publish(crypto.decrypt(conn["access_token_enc"]), conn["sub"], doc["text"], image=image,
                                   document=document, doc_title=doc.get("title") or "Carousel", alt=doc.get("title") or "")
    except client.LinkedInError as exc:
        await db[c.LINKEDIN_POSTS].update_one({"_id": doc["_id"]}, {"$set": {"status": "failed", "error": str(exc)[:300], "updated_at": now}})
        await notify(db, user_id=uid, kind="linkedin_post", title="LinkedIn post failed", body=str(exc)[:200], link="/linkedin")
        return await db[c.LINKEDIN_POSTS].find_one({"_id": doc["_id"]})
    url = f"https://www.linkedin.com/feed/update/{urn}/" if urn else None
    await db[c.LINKEDIN_POSTS].update_one({"_id": doc["_id"]}, {"$set": {"status": "published", "urn": urn, "url": url,
                                                                         "published_at": now, "error": None, "updated_at": now}})
    await log_action(db, user_id=uid, action="linkedin.posted", entity="linkedin_post", entity_id=doc["_id"],
                     details={"series": doc.get("series"), "format": doc.get("format")})
    await notify(db, user_id=uid, kind="linkedin_post", title=f"Posted on LinkedIn · {doc['series']}",
                 body=(doc.get("title") or "")[:120], link=url or "/linkedin")
    return await db[c.LINKEDIN_POSTS].find_one({"_id": doc["_id"]})


async def run_daily(db: AsyncIOMotorDatabase, uid: str, s, local_date: str) -> dict:
    lp = s.linkedin_posts
    if not lp.enabled:
        return {"skipped": "LinkedIn posting is off"}
    if await db[c.LINKEDIN_POSTS].find_one({"user_id": uid, "date": local_date, "status": {"$in": ["published", "ready"]}}):
        return {"skipped": "already posted today"}
    doc = await create(db, uid, lp, local_date=local_date)
    if lp.auto_publish:
        doc = await publish(db, uid, doc)
    else:
        await notify(db, user_id=uid, kind="linkedin_post", title=f"Today's LinkedIn post is ready to review · {doc['series']}",
                     link="/linkedin")
    return {"post_id": doc["_id"], "status": doc["status"], "series": doc.get("series"), "format": doc.get("format")}


async def streak(db: AsyncIOMotorDatabase, uid: str, today) -> int:
    days = {d["date"] async for d in db[c.LINKEDIN_POSTS].find({"user_id": uid, "status": "published"}, {"date": 1})}
    n, day = 0, today
    while day.isoformat() in days:
        n += 1
        day -= timedelta(days=1)
    return n


async def history(db: AsyncIOMotorDatabase, uid: str, limit: int = 60) -> list[dict]:
    return [post_out(d) async for d in db[c.LINKEDIN_POSTS].find({"user_id": uid}).sort("created_at", DESCENDING).limit(limit)]

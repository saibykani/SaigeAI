"""LinkedIn Posts: connect LinkedIn (official OAuth), daily posting settings, drafts, publishing, history."""

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.auth.deps import db_dep, get_current_user
from app.automation.service import get_settings_doc
from app.config import get_settings
from app.database import collections as c
from app.linkedin_posts import client, service
from app.profiles.service import get_profile
from app.services import crypto
from app.utils import new_id, utcnow

router = APIRouter(prefix="/linkedin", tags=["linkedin-posts"])


async def _post(db, uid: str, post_id: str) -> dict:
    d = await db[c.LINKEDIN_POSTS].find_one({"_id": post_id, "user_id": uid})
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    return d


@router.get("/status")
async def li_status(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    from app.scheduler.service import user_tz

    uid = user["_id"]
    s = await get_settings_doc(db, uid)
    conn = await service.connection(db, uid)
    today = utcnow().astimezone(user_tz(s)).date()
    published = await db[c.LINKEDIN_POSTS].count_documents({"user_id": uid, "status": "published"})
    return {"app_configured": client.enabled(), "connected": bool(conn), "name": (conn or {}).get("name"),
            "expires_at": conn["expires_at"].isoformat() if conn and conn.get("expires_at") else None,
            "settings": s.linkedin_posts.model_dump(), "streak": await service.streak(db, uid, today), "published": published}


@router.get("/connect")
async def li_connect(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    if not client.enabled():
        raise HTTPException(status.HTTP_409_CONFLICT, "LinkedIn posting isn't set up on the server yet (LINKEDIN_CLIENT_ID / "
                                                      "LINKEDIN_CLIENT_SECRET). Until then, posts are prepared for one-click posting.")
    state = secrets.token_urlsafe(24)
    await db[c.INTEGRATIONS].insert_one({"_id": new_id(), "user_id": user["_id"], "provider": "linkedin_oauth_state",
                                         "state": state, "created_at": utcnow()})
    return {"url": client.authorize_url(state)}


@router.get("/callback")
async def li_callback(code: str | None = None, state: str | None = None, error: str | None = None,
                      db: AsyncIOMotorDatabase = Depends(db_dep)):
    base = get_settings().frontend_url.rstrip("/")
    st = await db[c.INTEGRATIONS].find_one_and_delete({"provider": "linkedin_oauth_state", "state": state}) if state else None
    if error or not code or not st or utcnow() - st["created_at"].replace(tzinfo=utcnow().tzinfo) > timedelta(minutes=15):
        return RedirectResponse(f"{base}/linkedin?error=linkedin_denied", status_code=302)
    try:
        tok = await client.exchange(code)
    except client.LinkedInError:
        return RedirectResponse(f"{base}/linkedin?error=linkedin_failed", status_code=302)
    now = utcnow()
    await db[c.INTEGRATIONS].update_one(
        {"user_id": st["user_id"], "provider": "linkedin_api"},
        {"$set": {"access_token_enc": crypto.encrypt(tok["access_token"]), "sub": tok["sub"], "name": tok.get("name"),
                  "expires_at": now + timedelta(seconds=int(tok["expires_in"])), "updated_at": now},
         "$setOnInsert": {"_id": new_id(), "connected_at": now}}, upsert=True)
    return RedirectResponse(f"{base}/linkedin?connected=1", status_code=302)


@router.delete("/connection", status_code=204)
async def li_disconnect(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    await db[c.INTEGRATIONS].delete_many({"user_id": user["_id"], "provider": "linkedin_api"})
    return Response(status_code=204)


@router.get("/posts")
async def li_posts(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await service.history(db, user["_id"])


@router.post("/posts/generate", status_code=201)
async def li_generate(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    from app.scheduler.service import user_tz

    s = await get_settings_doc(db, user["_id"])
    day = utcnow().astimezone(user_tz(s)).date().isoformat()
    return service.post_out(await service.create(db, user["_id"], s.linkedin_posts, local_date=day))


@router.post("/posts/{post_id}/publish")
async def li_publish(post_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    d = await _post(db, user["_id"], post_id)
    if d["status"] == "published":
        raise HTTPException(status.HTTP_409_CONFLICT, "Already posted")
    return service.post_out(await service.publish(db, user["_id"], d))


class PostEdit(BaseModel):
    text: str = Field(min_length=5, max_length=2900)


@router.put("/posts/{post_id}")
async def li_edit(post_id: str, body: PostEdit, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    d = await _post(db, user["_id"], post_id)
    if d["status"] == "published":
        raise HTTPException(status.HTTP_409_CONFLICT, "Published posts can't be edited here")
    await db[c.LINKEDIN_POSTS].update_one({"_id": post_id}, {"$set": {"text": body.text, "updated_at": utcnow()}})
    return service.post_out(await _post(db, user["_id"], post_id))


class Stats(BaseModel):
    reactions: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    impressions: int | None = Field(default=None, ge=0)


@router.post("/posts/{post_id}/stats")
async def li_stats(post_id: str, body: Stats, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Record the numbers LinkedIn shows under the post (LinkedIn doesn't share them with apps)."""
    await _post(db, user["_id"], post_id)
    await db[c.LINKEDIN_POSTS].update_one({"_id": post_id}, {"$set": {"stats": body.model_dump(exclude_none=True), "updated_at": utcnow()}})
    return service.post_out(await _post(db, user["_id"], post_id))


@router.delete("/posts/{post_id}", status_code=204)
async def li_delete(post_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    await _post(db, user["_id"], post_id)
    await db[c.LINKEDIN_POSTS].delete_one({"_id": post_id})
    return Response(status_code=204)


@router.get("/posts/{post_id}/media")
async def li_media(post_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """The post's image (PNG) or carousel (PDF), for preview and download."""
    d = await _post(db, user["_id"], post_id)
    p = await get_profile(db, user["_id"])
    image, document = service.media(d, p.personal.name or "", p.personal.current_designation or "")
    if image:
        return Response(image, media_type="image/png")
    if document:
        return Response(document, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="saige-carousel-{d.get("date")}.pdf"'})
    raise HTTPException(status.HTTP_404_NOT_FOUND, "This post is text only")


class CommentsIn(BaseModel):
    post_text: str = Field(default="", max_length=3000)
    comments: list[dict] = Field(min_length=1, max_length=30)


def reply_to(author: str, comment: str, first: str) -> str:
    """A short, warm reply that never adds claims about the user."""
    who = (author or "").split()[0] if author else ""
    t = comment.lower()
    hi = f"Thanks {who}!" if who else "Thanks!"
    if "?" in comment:
        return f"{hi} Great question. Happy to share more here or in a DM."
    if any(w in t for w in ("congrat", "great", "nice", "awesome", "love", "helpful", "useful")):
        return f"{hi} Glad it was useful. More in this series soon."
    if any(w in t for w in ("disagree", "but ", "however")):
        return f"{hi} Fair point, appreciate the other view. What's worked best for you?"
    return f"{hi} Appreciate you reading and sharing your thoughts."


@router.post("/comment-replies")
async def li_comment_replies(body: CommentsIn, user: dict = Depends(get_current_user)):
    """Draft replies for comments on your post (the browser extension reads them from your post page)."""
    first = (user.get("name") or "").split(" ")[0]
    return {"replies": [{"author": x.get("author", ""), "comment": x.get("text", ""),
                         "reply": reply_to(x.get("author", ""), x.get("text", ""), first)} for x in body.comments]}

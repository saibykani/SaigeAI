"""Portfolio website builder (/api/portfolio): pick one of 26 templates, preview it with YOUR OWN profile, publish it
to a public URL (/p/<slug>). The public page renders live from the signed-in owner's verified profile, so it
updates when the profile changes. Email is shown only if allowed; phone is hidden unless the owner opts in."""

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.portfolio import data as pdata
from app.portfolio import templates as tpl
from app.profiles.service import get_profile
from app.services.audit import log_action
from app.services.notify import notify
from app.utils import utcnow

router = APIRouter(tags=["portfolio"])
RESERVED = {"admin", "api", "app", "login", "register", "help", "saige", "www", "p", "new", "settings", "about", "privacy", "terms"}
SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$")


def _suggest_slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "me").lower()).strip("-")[:40] or "me"
    return s if len(s) >= 3 else f"{s}-portfolio"


async def _settings(db: AsyncIOMotorDatabase, uid: str) -> dict:
    return await db[c.PORTFOLIOS].find_one({"_id": uid}) or {}


def _out(doc: dict, name: str) -> dict:
    return {"template": doc.get("template") or tpl.DEFAULT, "slug": doc.get("slug") or _suggest_slug(name), "published": bool(doc.get("published")),
            "tagline": doc.get("tagline") or "", "show_email": doc.get("show_email", True), "show_phone": bool(doc.get("show_phone")),
            "open_to_work": doc.get("open_to_work", True), "views": doc.get("views", 0),
            "published_at": doc["published_at"].isoformat() if doc.get("published_at") else None}


@router.get("/portfolio/templates")
async def templates():
    return [{"id": k, "name": v[0], "vibe": v[1], "colors": v[3]} for k, v in tpl.TEMPLATES.items()]


@router.get("/portfolio")
async def get_portfolio(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    p = await get_profile(db, user["_id"])
    return _out(await _settings(db, user["_id"]), p.personal.name or user.get("name") or "")


class PortfolioIn(BaseModel):
    template: str = Field(max_length=40)
    slug: str = Field(min_length=3, max_length=40)
    tagline: str = Field(default="", max_length=160)
    show_email: bool = True
    show_phone: bool = False
    open_to_work: bool = True


async def _save(db: AsyncIOMotorDatabase, uid: str, body: PortfolioIn) -> None:
    slug = body.slug.strip().lower()
    if not SLUG_RE.match(slug) or slug in RESERVED:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Use 3–40 lowercase letters, numbers and dashes (e.g. asha-rao).")
    if body.template not in tpl.TEMPLATES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown template")
    taken = await db[c.PORTFOLIOS].find_one({"slug": slug, "_id": {"$ne": uid}}, {"_id": 1})
    if taken:
        raise HTTPException(status.HTTP_409_CONFLICT, f"“{slug}” is taken. Try {slug}-{uid[-4:].lower()}.")
    await db[c.PORTFOLIOS].update_one({"_id": uid}, {"$set": {**body.model_dump(), "slug": slug, "user_id": uid, "updated_at": utcnow()}},
                                      upsert=True)


@router.put("/portfolio")
async def put_portfolio(body: PortfolioIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    await _save(db, user["_id"], body)
    return await get_portfolio(user, db)


@router.post("/portfolio/publish")
async def publish(body: PortfolioIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    p = await get_profile(db, uid)
    if not p.personal.name or not (p.knowledge.experience or p.knowledge.projects or p.skills.all()):
        raise HTTPException(status.HTTP_409_CONFLICT, "Add your name and at least your experience, projects or skills to your Profile first.")
    await _save(db, uid, body)
    await db[c.PORTFOLIOS].update_one({"_id": uid}, {"$set": {"published": True, "published_at": utcnow()}})
    await log_action(db, user_id=uid, action="portfolio.published", entity="portfolio", details={"slug": body.slug, "template": body.template})
    await notify(db, user_id=uid, kind="portfolio_published", title="Your portfolio is live", body=f"/p/{body.slug.lower()}", link="/portfolio")
    return await get_portfolio(user, db)


@router.post("/portfolio/unpublish")
async def unpublish(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    await db[c.PORTFOLIOS].update_one({"_id": user["_id"]}, {"$set": {"published": False}})
    await log_action(db, user_id=user["_id"], action="portfolio.unpublished", entity="portfolio")
    return await get_portfolio(user, db)


def _html(html: str) -> HTMLResponse:
    return HTMLResponse(html, headers={"X-Frame-Options": "SAMEORIGIN", "Cache-Control": "no-store",
                                       "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline' https://fonts.googleapis.com; "
                                                                  "font-src https://fonts.gstatic.com; img-src data: https:; frame-ancestors 'self'"})


@router.get("/portfolio/preview", response_class=HTMLResponse)
async def preview(template: str = Query(tpl.DEFAULT, max_length=40), tagline: str = Query("", max_length=160), show_email: bool = True,
                  show_phone: bool = False, open_to_work: bool = True, user: dict = Depends(get_current_user),
                  db: AsyncIOMotorDatabase = Depends(db_dep)):
    """The signed-in user's own portfolio in any template, before publishing."""
    d = pdata.build(await get_profile(db, user["_id"]), {"tagline": tagline, "show_email": show_email, "show_phone": show_phone,
                                                         "open_to_work": open_to_work})
    return _html(tpl.render(template, d))


@router.get("/portfolio/download")
async def download(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """index.html to host anywhere (GitHub Pages, Netlify)."""
    s = await _settings(db, user["_id"])
    html = tpl.render(s.get("template") or tpl.DEFAULT, pdata.build(await get_profile(db, user["_id"]), s))
    return Response(html, media_type="text/html", headers={"Content-Disposition": 'attachment; filename="index.html"'})


@router.get("/p/{slug}", response_class=HTMLResponse)
async def public_page(slug: str, db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Public portfolio: rendered live from the owner's profile (only while published)."""
    s = await db[c.PORTFOLIOS].find_one({"slug": slug.lower(), "published": True})
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Portfolio not found")
    await db[c.PORTFOLIOS].update_one({"_id": s["_id"]}, {"$inc": {"views": 1}})
    return _html(tpl.render(s.get("template") or tpl.DEFAULT, pdata.build(await get_profile(db, s["user_id"]), s)))

"""Browser extension API (Phase 9).

The extension authenticates with a personal access token (PAT) the user creates in Settings. A PAT
is stored only as a SHA-256 hash, can be revoked at any time, and works ONLY on the /ext endpoints
below (score, save, suggest answers). It can't read the profile, send anything or change settings.

The extension reads only the page the user is looking at, when they click it. It never submits
application forms: answers are suggestions the user inserts.
"""

import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field, HttpUrl
from pymongo import DESCENDING

from app.agents.jd_agent import analyze_job
from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.jobs import service as jobs
from app.jobs.dedupe import canonical_url
from app.jobs.matching import compute_match
from app.profiles.service import get_profile
from app.schemas.job import JobIn
from app.services.audit import log_action
from app.utils import new_id, utcnow

router = APIRouter(tags=["extension"])
_bearer = HTTPBearer(auto_error=False)

PAT_PREFIX = "saige_pat_"
MAX_TOKENS = 5


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def token_out(d: dict) -> dict:
    return {"id": d["_id"], "name": d["name"], "prefix": d["prefix"], "created_at": d["created_at"].isoformat(),
            "last_used_at": d["last_used_at"].isoformat() if d.get("last_used_at") else None}


class TokenIn(BaseModel):
    name: str = Field(default="Chrome extension", min_length=1, max_length=60)


class PageIn(BaseModel):
    url: HttpUrl | None = None
    title: str = Field(min_length=2, max_length=200)
    company: str = Field(default="", max_length=200)
    location: str | None = Field(default=None, max_length=200)
    text: str = Field(min_length=30, max_length=60000)


# ------------------------------------------------------------------ token management (signed-in web app)

@router.get("/auth/tokens")
async def list_tokens(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    docs = await db[c.API_TOKENS].find({"user_id": user["_id"], "revoked": False}).sort("created_at", DESCENDING).to_list(20)
    return [token_out(d) for d in docs]


@router.post("/auth/tokens", status_code=201)
async def create_token(body: TokenIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    if await db[c.API_TOKENS].count_documents({"user_id": user["_id"], "revoked": False}) >= MAX_TOKENS:
        raise HTTPException(status.HTTP_409_CONFLICT, f"You can have at most {MAX_TOKENS} active tokens. Revoke one first.")
    token = PAT_PREFIX + secrets.token_urlsafe(32)
    doc = {"_id": new_id(), "user_id": user["_id"], "name": body.name, "token_hash": _hash(token),
           "prefix": token[: len(PAT_PREFIX) + 4], "scopes": ["extension"], "revoked": False,
           "created_at": utcnow(), "last_used_at": None}
    await db[c.API_TOKENS].insert_one(doc)
    await log_action(db, user_id=user["_id"], action="api_token.created", entity="api_token", entity_id=doc["_id"],
                     details={"name": body.name})
    return {**token_out(doc), "token": token}  # shown once, never retrievable again


@router.delete("/auth/tokens/{token_id}", status_code=204)
async def revoke_token(token_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    res = await db[c.API_TOKENS].update_one({"_id": token_id, "user_id": user["_id"], "revoked": False},
                                            {"$set": {"revoked": True, "revoked_at": utcnow()}})
    if not res.matched_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token not found")
    await log_action(db, user_id=user["_id"], action="api_token.revoked", entity="api_token", entity_id=token_id)
    return Response(status_code=204)


# ------------------------------------------------------------------ extension endpoints (PAT only)

async def token_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
                     db: AsyncIOMotorDatabase = Depends(db_dep)) -> dict:
    bad = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or revoked extension token",
                        headers={"WWW-Authenticate": "Bearer"})
    if creds is None or not creds.credentials.startswith(PAT_PREFIX):
        raise bad
    tok = await db[c.API_TOKENS].find_one({"token_hash": _hash(creds.credentials), "revoked": False})
    if not tok:
        raise bad
    user = await db[c.USERS].find_one({"_id": tok["user_id"], "is_active": True})
    if not user:
        raise bad
    await db[c.API_TOKENS].update_one({"_id": tok["_id"]}, {"$set": {"last_used_at": utcnow()}})
    return user


def _job_in(page: PageIn) -> JobIn:
    return JobIn(title=page.title, company=page.company.strip() or "Unknown company", description=page.text,
                 location=page.location, application_url=page.url, source="extension")


async def _existing(db: AsyncIOMotorDatabase, uid: str, url: HttpUrl | None) -> dict | None:
    key = canonical_url(str(url)) if url else None
    return await db[c.JOBS].find_one({"user_id": uid, "sources.url_key": key}) if key else None


@router.get("/ext/me")
async def ext_me(user: dict = Depends(token_user)):
    return {"name": user.get("name"), "email": user["email"]}


@router.post("/ext/analyze")
async def ext_analyze(page: PageIn, user: dict = Depends(token_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Score the posting on screen against the verified profile, without saving anything."""
    uid = user["_id"]
    existing = await _existing(db, uid, page.url)
    if existing and existing.get("match"):
        m = existing["match"]
    else:
        job_in = _job_in(page)
        jd = await analyze_job(job_in.title, job_in.description)
        cand = jobs.normalize(job_in, jd, uid)
        m = compute_match(await get_profile(db, uid), cand, jd, await jobs.get_weights(db, uid)).model_dump()
    return {"score": m["overall"], "classification": m["classification"], "matched_skills": m["matched_skills"][:12],
            "missing_skills": m["missing_required_skills"][:8], "issues": m["issues"][:4],
            "saved_job_id": existing["_id"] if existing else None}


@router.post("/ext/save", status_code=201)
async def ext_save(page: PageIn, user: dict = Depends(token_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    job, created = await jobs.ingest(db, user["_id"], _job_in(page))
    return {"job_id": job["_id"], "created": created, "score": (job.get("match") or {}).get("overall"),
            "path": f"/jobs/{job['_id']}"}


@router.get("/ext/answers")
async def ext_answers(url: HttpUrl, user: dict = Depends(token_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Prepared answers for the application on this page, for the user to insert one by one."""
    job = await _existing(db, user["_id"], url)
    if not job:
        return {"job_id": None, "application_id": None, "answers": []}
    app = await db[c.APPLICATIONS].find_one({"user_id": user["_id"], "job_id": job["_id"]})
    if not app:
        return {"job_id": job["_id"], "application_id": None, "answers": []}
    answers = await db[c.APPLICATION_ANSWERS].find({"application_id": app["_id"]}).to_list(100)
    return {"job_id": job["_id"], "application_id": app["_id"],
            "answers": [{"question": a["question"], "answer": a.get("answer"), "confidence": a.get("confidence"),
                         "needs_review": a.get("sensitive", False) or a.get("status") == "REVIEW_REQUIRED"} for a in answers
                        if a.get("answer")]}

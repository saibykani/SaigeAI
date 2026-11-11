"""/api/ml: Saige learning (rate jobs, correct job types, train, status, training tasks)."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.auth.deps import db_dep, get_current_user
from app.careers import service as careers
from app.database import collections as c
from app.ml import service as ml
from app.services.rate_limit import RateLimiter

router = APIRouter(prefix="/ml", tags=["ml"])
train_limiter = RateLimiter(20, 3600)


class FeedbackIn(BaseModel):
    job_id: str = Field(max_length=200)
    rating: Literal["up", "down"] | None = None
    category: Literal["manual", "automation", "qa", "other"] | None = None


@router.post("/feedback")
async def feedback(body: FeedbackIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """👍 / 👎 a posting and/or correct its job type. Every few labels Saige retrains."""
    uid = user["_id"]
    job = await careers.get_owned(db, uid, body.job_id)
    patch: dict = {}
    if body.rating:
        patch["rating"] = body.rating
    if body.category:
        patch.update(category=body.category, category_src="user")
    if patch:
        await db[c.CAREER_JOBS].update_one({"_id": job["_id"]}, {"$set": patch})
        job = {**job, **patch}
    return await ml.record(db, uid, job, label=None if body.rating is None else int(body.rating == "up"), category=body.category)


@router.post("/train")
async def train(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    if not train_limiter.hit(f"ml:{user['_id']}"):
        raise HTTPException(429, "Saige has trained a lot this hour. Try again later.")
    return await ml.train(db, user["_id"], trigger="manual")


@router.get("/status")
async def status(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await ml.status(db, user["_id"])


@router.get("/tasks")
async def tasks(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return {"items": await ml.tasks(db, user["_id"])}

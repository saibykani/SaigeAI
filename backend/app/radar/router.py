"""/api/radar: today's best-fit jobs (feed + career portals) and a test digest to your own inbox."""

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.deps import db_dep, get_current_user
from app.radar import service
from app.services.rate_limit import RateLimiter

router = APIRouter(prefix="/radar", tags=["radar"])
digest_limiter = RateLimiter(5, 3600)


@router.get("")
async def get_radar(top: int = Query(service.DEFAULT_TOP, ge=1, le=service.MAX_TOP), user: dict = Depends(get_current_user),
                    db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await service.radar(db, user["_id"], top=top)


@router.post("/digest/test")
async def digest_test(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    if not digest_limiter.hit(f"radar:{user['_id']}"):
        raise HTTPException(429, "You've sent several test digests this hour. Try again later.")
    return await service.send_test_digest(db, user["_id"])

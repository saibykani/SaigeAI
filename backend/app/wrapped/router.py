"""Career Wrapped (/api/wrapped): read-only story data from the user's own records."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.deps import db_dep, get_current_user
from app.wrapped.service import build

router = APIRouter(prefix="/wrapped", tags=["wrapped"])


@router.get("")
async def wrapped(period: Literal["all", "month", "week"] = Query(default="all"),
                  user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await build(db, user["_id"], period)

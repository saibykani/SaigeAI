from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.deps import db_dep, get_current_user
from app.profiles import service
from app.schemas.profile import ProfileOut, ProfileUpdate
from app.services.truth_guard import GeneratedClaims, ValidationResult, validate_claims

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
async def get_profile(user: dict = Depends(get_current_user),
                      db: AsyncIOMotorDatabase = Depends(db_dep)):
    return service.to_out(await service.get_profile_doc(db, user["_id"]))


@router.put("", response_model=ProfileOut)
async def put_profile(body: ProfileUpdate, user: dict = Depends(get_current_user),
                      db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await service.update_profile(db, user["_id"], body)


@router.post("/validate-claims", response_model=ValidationResult)
async def validate(body: GeneratedClaims, user: dict = Depends(get_current_user),
                   db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Check generated content against the verified knowledge base (hallucination guard)."""
    return validate_claims(body, await service.get_profile(db, user["_id"]))

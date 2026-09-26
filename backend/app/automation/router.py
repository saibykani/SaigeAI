from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.deps import db_dep, get_current_user
from app.automation import service
from app.automation.service import AutomationSettings, AutomationSettingsUpdate

router = APIRouter(prefix="/automation", tags=["automation"])


@router.get("/status", response_model=AutomationSettings)
async def status(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await service.get_settings_doc(db, user["_id"])


@router.put("/settings", response_model=AutomationSettings)
async def update(body: AutomationSettingsUpdate, user: dict = Depends(get_current_user),
                 db: AsyncIOMotorDatabase = Depends(db_dep)):
    current = await service.get_settings_doc(db, user["_id"])
    merged = AutomationSettings.model_validate(
        {**current.model_dump(), **body.model_dump(exclude_none=True)})
    return await service.save(db, user["_id"], merged, "automation.settings_updated",
                              body.model_dump(exclude_none=True))


@router.post("/pause-all", response_model=AutomationSettings)
async def pause_all(user: dict = Depends(get_current_user),
                    db: AsyncIOMotorDatabase = Depends(db_dep)):
    s = await service.get_settings_doc(db, user["_id"])
    s.paused_all = True
    return await service.save(db, user["_id"], s, "automation.paused_all", {"paused_all": True})


@router.post("/resume-all", response_model=AutomationSettings)
async def resume_all(user: dict = Depends(get_current_user),
                     db: AsyncIOMotorDatabase = Depends(db_dep)):
    s = await service.get_settings_doc(db, user["_id"])
    s.paused_all = False
    return await service.save(db, user["_id"], s, "automation.resumed_all", {"paused_all": False})

"""Data export and deletion (spec section 46)."""

import json
from datetime import datetime

from fastapi import APIRouter, Cookie, Depends, Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from app.auth.deps import db_dep, get_current_user, require_csrf_header
from app.auth.service import REFRESH_COOKIE, clear_refresh_cookie
from app.database import collections as c

router = APIRouter(prefix="/privacy", tags=["privacy"])
audit_router = APIRouter(prefix="/audit", tags=["audit"])


def _jsonable(value):
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items() if k not in {"password_hash", "data"}}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return None
    return value


@router.get("/export")
async def export_my_data(user: dict = Depends(get_current_user),
                         db: AsyncIOMotorDatabase = Depends(db_dep)):
    data = {"user": _jsonable(user)}
    for coll in c.USER_SCOPED:
        if coll in c.EXPORT_EXCLUDED:
            continue
        data[coll] = _jsonable(await db[coll].find({"user_id": user["_id"]}).to_list(length=None))
    return Response(
        content=json.dumps(data, indent=2, default=str),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=saige-ai-export.json"},
    )


@router.delete("/account", status_code=204, dependencies=[Depends(require_csrf_header)])
async def delete_account(response: Response, user: dict = Depends(get_current_user),
                         db: AsyncIOMotorDatabase = Depends(db_dep),
                         saige_refresh: str | None = Cookie(default=None, alias=REFRESH_COOKIE)):
    for coll in c.USER_SCOPED:
        await db[coll].delete_many({"user_id": user["_id"]})
    await db[c.USERS].delete_one({"_id": user["_id"]})
    clear_refresh_cookie(response)
    response.status_code = 204
    return response


@router.delete("/profile-history", status_code=204)
async def delete_profile_history(user: dict = Depends(get_current_user),
                                 db: AsyncIOMotorDatabase = Depends(db_dep)):
    await db[c.PROFILE_CHANGES].delete_many({"user_id": user["_id"]})
    await db[c.AUDIT_LOGS].delete_many({"user_id": user["_id"], "action": "profile.updated"})
    return Response(status_code=204)


@audit_router.get("")
async def my_audit_log(limit: int = 100, user: dict = Depends(get_current_user),
                       db: AsyncIOMotorDatabase = Depends(db_dep)):
    docs = await db[c.AUDIT_LOGS].find({"user_id": user["_id"]}).sort(
        "timestamp", DESCENDING).to_list(length=min(max(limit, 1), 500))
    return [{"id": d["_id"], "action": d["action"], "entity": d.get("entity"),
             "entity_id": d.get("entity_id"), "details": _jsonable(d.get("details", {})),
             "timestamp": d["timestamp"].isoformat()} for d in docs]

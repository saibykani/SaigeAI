from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from app.auth.deps import db_dep, get_current_user
from app.automation.service import is_allowed
from app.database import collections as c
from app.profiles import sync_service as svc
from app.schemas.platform import ChangeEdit, LinkedInProfile, NaukriProfile
from app.services.agent_runs import agent_run
from app.services.notify import notify

router = APIRouter(tags=["profile-sync"])

MANUAL_REASON = ("{name} does not offer an API that lets third-party apps edit your profile, and "
                 "automating its website would break its terms. Copy the approved text into {name}, "
                 "then click 'Mark as updated'.")


@router.get("/profile/linkedin", response_model=LinkedInProfile)
async def get_linkedin(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await svc.get_snapshot(db, user["_id"], "linkedin")


@router.put("/profile/linkedin", response_model=LinkedInProfile)
async def put_linkedin(body: LinkedInProfile, user: dict = Depends(get_current_user),
                       db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await svc.save_snapshot(db, user["_id"], "linkedin", body)


@router.get("/profile/naukri", response_model=NaukriProfile)
async def get_naukri(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await svc.get_snapshot(db, user["_id"], "naukri")


@router.put("/profile/naukri", response_model=NaukriProfile)
async def put_naukri(body: NaukriProfile, user: dict = Depends(get_current_user),
                     db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await svc.save_snapshot(db, user["_id"], "naukri", body)


@router.post("/profile/{platform}/analyze")
async def analyze_platform(platform: Literal["linkedin", "naukri"], user: dict = Depends(get_current_user),
                           db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await svc.analyze(db, user["_id"], (platform,))


@router.post("/profile/{platform}/update")
async def update_platform(platform: Literal["linkedin", "naukri"], user: dict = Depends(get_current_user)):
    """Spec 27/28: update via official API where permitted. Neither platform permits it today."""
    name = {"linkedin": "LinkedIn", "naukri": "Naukri"}[platform]
    return {"status": "MANUAL_ACTION_REQUIRED", "action": f"COPY_TO_{platform.upper()}",
            "reason": MANUAL_REASON.format(name=name)}


# ------------------------------------------------------------------ profile sync agent

@router.post("/profile-sync/run")
async def run_profile_agent(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    if not await is_allowed(db, uid, "profile_updates"):
        raise HTTPException(status.HTTP_423_LOCKED, "Profile updates are paused. Resume them in Automation settings.")
    async with agent_run(db, "profile_agent", uid, {"trigger": "manual"}) as run:
        result = await svc.analyze(db, uid)
        cons = await svc.consistency(db, uid)
        created = sum((result.get(k) or {}).get("changes_created", 0) for k in ("linkedin", "naukri", "resume"))
        run.output = {"jobs_analyzed": result["jobs_analyzed"], "changes_created": created,
                      "consistency": cons["score"]}
        run.action(f"created {created} profile change(s)")
    pending = await db[c.PROFILE_CHANGES].count_documents({"user_id": uid, "approval_status": svc.PENDING})
    if created:
        await notify(db, user_id=uid, kind="profile_optimization",
                     title=f"Profile optimization ready: {created} new suggestion(s)",
                     body="Review and copy approved changes to LinkedIn and Naukri.", link="/profile-sync")
    return {**result, "consistency": cons, "pending_changes": pending}


@router.get("/profile-sync/overview")
async def overview(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    from app.profiles import optimizer as opt
    from app.profiles.service import get_profile

    profile = await get_profile(db, uid)
    trends, jobs = await opt.skill_trends(db, uid, profile)
    li = await svc.get_snapshot(db, uid, "linkedin")
    nk = await svc.get_snapshot(db, uid, "naukri")
    li_comp, li_missing = opt.completeness(li.model_dump(), opt.LINKEDIN_FIELDS)
    nk_comp, nk_missing = opt.completeness(nk.model_dump(), opt.NAUKRI_FIELDS)
    li_align, li_kw = opt.keyword_alignment(f"{li.headline or ''} {li.about or ''}", li.skills, trends)
    nk_align, nk_kw = opt.keyword_alignment(f"{nk.headline or ''} {nk.summary or ''}", nk.key_skills, trends)
    counts = {}
    for p in ("linkedin", "naukri", "resume"):
        counts[p] = await db[c.PROFILE_CHANGES].count_documents(
            {"user_id": uid, "platform": p, "approval_status": svc.PENDING})
    last = await db[c.AGENT_RUNS].find_one({"user_id": uid, "agent_name": "profile_agent"},
                                           sort=[("start_time", DESCENDING)])
    return {
        "jobs_analyzed": len(jobs),
        "trends": [t.model_dump() for t in trends],
        "linkedin": {"completeness": li_comp, "missing_fields": li_missing, "keyword_alignment": li_align,
                     "skills_to_add": li_kw, "pending_changes": counts["linkedin"]},
        "naukri": {"completeness": nk_comp, "missing_fields": nk_missing, "keyword_alignment": nk_align,
                   "skills_to_add": nk_kw, "pending_changes": counts["naukri"]},
        "resume": {"pending_changes": counts["resume"]},
        "consistency": await svc.consistency(db, uid),
        "last_run": last["start_time"].isoformat() if last else None,
    }


# ------------------------------------------------------------------ change control

@router.get("/profile-changes")
async def list_changes(platform: Literal["linkedin", "naukri", "resume"] | None = None,
                       approval_status: str | None = Query(None, alias="status"),
                       user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    q: dict = {"user_id": user["_id"]}
    if platform:
        q["platform"] = platform
    if approval_status:
        q["approval_status"] = approval_status
    docs = await db[c.PROFILE_CHANGES].find(q).sort("updated_at", DESCENDING).to_list(length=200)
    return [svc.change_out(d) for d in docs]


@router.post("/profile-changes/{change_id}/approve")
async def approve(change_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await svc.decide(db, user["_id"], change_id, "USER_APPROVED")


@router.post("/profile-changes/{change_id}/reject")
async def reject(change_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await svc.decide(db, user["_id"], change_id, "USER_REJECTED")


@router.put("/profile-changes/{change_id}")
async def edit(change_id: str, body: ChangeEdit, user: dict = Depends(get_current_user),
               db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await svc.edit_change(db, user["_id"], change_id, body.after)


@router.post("/profile-changes/{change_id}/applied")
async def applied(change_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await svc.mark_applied(db, user["_id"], change_id)

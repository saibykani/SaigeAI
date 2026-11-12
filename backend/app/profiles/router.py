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


@router.get("/setup-status")
async def setup_status(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """First-run gate: new users upload a resume before anything else."""
    from app.database import collections as c

    has_resume = bool(await db[c.RESUMES].find_one({"user_id": user["_id"], "kind": {"$ne": "ATS Resume"}}, {"_id": 1}))
    out = service.to_out(await service.get_profile_doc(db, user["_id"]))
    return {"has_resume": has_resume, "completeness": out["completeness"], "needs_setup": not has_resume and out["completeness"] < 40}


@router.post("/fill-from-resumes")
async def fill_from_resumes(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Fill EMPTY profile fields from every uploaded resume (newest first). Existing values are never overwritten."""
    from app.database import collections as c
    from app.resumes import service as resumes
    from app.schemas.resume import ParsedResume
    from app.services.agent_runs import agent_run
    from app.services.audit import log_action
    from app.studio import projects as project_sync

    uid = user["_id"]
    applied: list[str] = []
    async with agent_run(db, "profile_fill", uid, {}) as run:
        docs = await db[c.RESUMES].find({"user_id": uid, "kind": {"$ne": "ATS Resume"}}).sort("updated_at", -1).to_list(30)
        for d in docs:
            cur = await resumes.current_version(db, d)
            if cur and cur.get("parsed"):
                r = await resumes.import_to_profile(db, uid, ParsedResume.model_validate(cur["parsed"]))
                applied += r["applied"]
                run.action(f"{d.get('name')}: {len(r['applied'])} fields")
        _, added = await project_sync.sync(db, uid, await service.get_profile(db, uid))
        applied += [f"knowledge.projects: {n}" for n in added]
        run.output = {"resumes": len(docs), "filled": len(applied)}
    await log_action(db, user_id=uid, action="profile.filled_from_resumes", entity="profile", details={"filled": len(applied)})
    out = service.to_out(await service.get_profile_doc(db, uid))
    return {"resumes": len(docs), "applied": applied, "completeness": out["completeness"], "unknown_fields": out["unknown_fields"]}

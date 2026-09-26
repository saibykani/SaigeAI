from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from app.auth.deps import db_dep, get_current_user
from app.config import get_settings
from app.database import collections as c
from app.resumes import service
from app.resumes.extract import UnsupportedFile, detect_type, extract_text
from app.schemas.resume import (
    ImportResult,
    ParsedResume,
    ResumeCompare,
    ResumeDetail,
    ResumeOut,
    ResumeUpdate,
    ResumeVersionOut,
)
from app.services.audit import log_action
from app.services.rate_limit import upload_limiter
from app.utils import new_id, utcnow

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.get("", response_model=list[ResumeOut])
async def list_resumes(include_archived: bool = False, user: dict = Depends(get_current_user),
                       db: AsyncIOMotorDatabase = Depends(db_dep)):
    query: dict = {"user_id": user["_id"]}
    if not include_archived:
        query["status"] = "active"
    docs = await db[c.RESUMES].find(query).sort("updated_at", DESCENDING).to_list(length=200)
    return [service.resume_out(d) for d in docs]


@router.post("", response_model=ResumeDetail, status_code=201,
             dependencies=[Depends(upload_limiter.dependency("resume_upload"))])
async def upload_resume(
    file: UploadFile = File(...),
    name: str = Form(..., min_length=1, max_length=120),
    kind: str = Form("Master Resume", min_length=1, max_length=60),
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE,
                            f"File exceeds {get_settings().max_upload_mb} MB")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is empty")
    filename = (file.filename or "resume").replace("/", "_").replace("\\", "_")[:200]
    try:
        ftype = detect_type(filename, file.content_type, data)
        text = extract_text(ftype, data)
    except UnsupportedFile as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    resume = await service.create_from_upload(
        db, user["_id"], name=name, kind=kind, filename=filename,
        content_type=file.content_type or "application/octet-stream", data=data, text=text,
    )
    return await _detail(db, resume)


async def _detail(db: AsyncIOMotorDatabase, resume: dict) -> dict:
    cur = await service.current_version(db, resume)
    return {**service.resume_out(resume),
            "current_version": service.version_out(cur) if cur else None}


@router.get("/{resume_id}", response_model=ResumeDetail)
async def get_resume(resume_id: str, user: dict = Depends(get_current_user),
                     db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await _detail(db, await service.get_owned(db, user["_id"], resume_id))


@router.put("/{resume_id}", response_model=ResumeDetail)
async def update_resume(resume_id: str, body: ResumeUpdate, user: dict = Depends(get_current_user),
                        db: AsyncIOMotorDatabase = Depends(db_dep)):
    resume = await service.get_owned(db, user["_id"], resume_id)
    meta = {k: v for k, v in (("name", body.name), ("kind", body.kind)) if v is not None}
    if meta:
        await db[c.RESUMES].update_one({"_id": resume_id}, {"$set": {**meta, "updated_at": utcnow()}})
        resume.update(meta)
    if body.parsed is not None:
        cur = await service.current_version(db, resume)
        before = ParsedResume.model_validate(cur["parsed"]) if cur else ParsedResume()
        changes = service.describe_changes(before, body.parsed)
        if body.change_note:
            changes.insert(0, body.change_note)
        await service.add_version(db, resume, parsed=body.parsed,
                                  raw_text=cur.get("raw_text", "") if cur else "",
                                  source="edit", changes=changes)
    await log_action(db, user_id=user["_id"], action="resume.updated", entity="resume",
                     entity_id=resume_id, details={"meta": meta, "new_version": body.parsed is not None})
    return await _detail(db, await service.get_owned(db, user["_id"], resume_id))


@router.delete("/{resume_id}", status_code=204)
async def delete_resume(resume_id: str, user: dict = Depends(get_current_user),
                        db: AsyncIOMotorDatabase = Depends(db_dep)):
    resume = await service.get_owned(db, user["_id"], resume_id)
    await service.delete_resume(db, resume)
    await log_action(db, user_id=user["_id"], action="resume.deleted", entity="resume",
                     entity_id=resume_id, details={"name": resume["name"]})
    return Response(status_code=204)


@router.post("/{resume_id}/duplicate", response_model=ResumeDetail, status_code=201)
async def duplicate_resume(resume_id: str, name: str | None = Query(default=None, max_length=120),
                           kind: str | None = Query(default=None, max_length=60),
                           user: dict = Depends(get_current_user),
                           db: AsyncIOMotorDatabase = Depends(db_dep)):
    src = await service.get_owned(db, user["_id"], resume_id)
    cur = await service.current_version(db, src)
    now = utcnow()
    copy = {**src, "_id": new_id(), "name": name or f"{src['name']} (copy)",
            "kind": kind or src["kind"], "status": "active", "current_version_id": None,
            "version_count": 0, "created_at": now, "updated_at": now}
    await db[c.RESUMES].insert_one(copy)
    if cur:
        await service.add_version(db, copy, parsed=ParsedResume.model_validate(cur["parsed"]),
                                  raw_text=cur.get("raw_text", ""), source="duplicate",
                                  changes=[f"Duplicated from {src['name']} v{cur['version']}"],
                                  base_resume_id=src["_id"])
    await log_action(db, user_id=user["_id"], action="resume.duplicated", entity="resume",
                     entity_id=copy["_id"], details={"source_resume_id": resume_id})
    return await _detail(db, await service.get_owned(db, user["_id"], copy["_id"]))


async def _set_status(db, user, resume_id: str, new_status: str) -> dict:
    await service.get_owned(db, user["_id"], resume_id)
    await db[c.RESUMES].update_one({"_id": resume_id},
                                   {"$set": {"status": new_status, "updated_at": utcnow()}})
    await log_action(db, user_id=user["_id"], action=f"resume.{new_status}", entity="resume",
                     entity_id=resume_id)
    return await _detail(db, await service.get_owned(db, user["_id"], resume_id))


@router.post("/{resume_id}/archive", response_model=ResumeDetail)
async def archive(resume_id: str, user: dict = Depends(get_current_user),
                  db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await _set_status(db, user, resume_id, "archived")


@router.post("/{resume_id}/unarchive", response_model=ResumeDetail)
async def unarchive(resume_id: str, user: dict = Depends(get_current_user),
                    db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await _set_status(db, user, resume_id, "active")


@router.get("/{resume_id}/versions", response_model=list[ResumeVersionOut])
async def versions(resume_id: str, user: dict = Depends(get_current_user),
                   db: AsyncIOMotorDatabase = Depends(db_dep)):
    await service.get_owned(db, user["_id"], resume_id)
    return [service.version_out(v) for v in await service.list_versions(db, resume_id)]


@router.get("/{resume_id}/compare", response_model=ResumeCompare)
async def compare(resume_id: str, a: str, b: str, user: dict = Depends(get_current_user),
                  db: AsyncIOMotorDatabase = Depends(db_dep)):
    await service.get_owned(db, user["_id"], resume_id)
    va = await db[c.RESUME_VERSIONS].find_one({"_id": a, "resume_id": resume_id})
    vb = await db[c.RESUME_VERSIONS].find_one({"_id": b, "resume_id": resume_id})
    if not va or not vb:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    pa, pb = ParsedResume.model_validate(va["parsed"]), ParsedResume.model_validate(vb["parsed"])
    return ResumeCompare(
        a_version_id=a, b_version_id=b,
        skills_added=[s for s in pb.skills if s not in pa.skills],
        skills_removed=[s for s in pa.skills if s not in pb.skills],
        summary_changed=pa.summary != pb.summary,
        experience_count=(len(pa.experience), len(pb.experience)),
        projects_count=(len(pa.projects), len(pb.projects)),
        certifications_added=[x for x in pb.certifications if x not in pa.certifications],
        certifications_removed=[x for x in pa.certifications if x not in pb.certifications],
    )


@router.get("/{resume_id}/download")
async def download(resume_id: str, user: dict = Depends(get_current_user),
                   db: AsyncIOMotorDatabase = Depends(db_dep)):
    resume = await service.get_owned(db, user["_id"], resume_id)
    f = await db[c.RESUME_FILES].find_one({"_id": resume.get("file_id"), "user_id": user["_id"]})
    if not f:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Original file not available")
    return Response(
        content=bytes(f["data"]), media_type=f["content_type"],
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(f['filename'])}",
                 "X-Content-Type-Options": "nosniff"},
    )


@router.post("/{resume_id}/import-to-profile", response_model=ImportResult)
async def import_to_profile(resume_id: str, user: dict = Depends(get_current_user),
                            db: AsyncIOMotorDatabase = Depends(db_dep)):
    resume = await service.get_owned(db, user["_id"], resume_id)
    cur = await service.current_version(db, resume)
    if not cur:
        raise HTTPException(status.HTTP_409_CONFLICT, "Resume has no parsed content")
    return await service.import_to_profile(db, user["_id"], ParsedResume.model_validate(cur["parsed"]))

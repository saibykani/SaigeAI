from bson import Binary
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import ValidationError
from pymongo import DESCENDING

from app.database import collections as c
from app.profiles import service as profiles
from app.resumes.parser import parse_resume
from app.schemas.profile import (
    Certification,
    Education,
    Experience,
    PersonalInfo,
    ProfileUpdate,
    Project,
)
from app.schemas.resume import ParsedResume
from app.services.audit import log_action
from app.services.skills_vocab import category_of
from app.utils import new_id, utcnow


def _iso(dt) -> str:
    return dt.isoformat() if dt else ""


def resume_out(doc: dict) -> dict:
    return {
        "id": doc["_id"], "name": doc["name"], "kind": doc["kind"], "status": doc["status"],
        "filename": doc.get("filename"), "content_type": doc.get("content_type"),
        "size": doc.get("size"), "current_version_id": doc.get("current_version_id"),
        "version_count": doc.get("version_count", 0),
        "created_at": _iso(doc.get("created_at")), "updated_at": _iso(doc.get("updated_at")),
    }


def version_out(doc: dict) -> dict:
    return {
        "id": doc["_id"], "resume_id": doc["resume_id"], "version": doc["version"],
        "base_resume_id": doc.get("base_resume_id"), "job_id": doc.get("job_id"),
        "source": doc["source"], "changes": doc.get("changes", []), "parsed": doc["parsed"],
        "raw_text": doc.get("raw_text", ""), "created_at": _iso(doc.get("created_at")),
    }


async def get_owned(db: AsyncIOMotorDatabase, user_id: str, resume_id: str) -> dict:
    doc = await db[c.RESUMES].find_one({"_id": resume_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")
    return doc


async def add_version(
    db: AsyncIOMotorDatabase, resume: dict, *, parsed: ParsedResume, raw_text: str, source: str,
    changes: list[str], base_resume_id: str | None = None, job_id: str | None = None,
) -> dict:
    version = resume.get("version_count", 0) + 1
    doc = {
        "_id": new_id(), "resume_id": resume["_id"], "user_id": resume["user_id"],
        "version": version, "base_resume_id": base_resume_id, "job_id": job_id,
        "source": source, "changes": changes, "parsed": parsed.model_dump(mode="json"),
        "raw_text": raw_text, "created_at": utcnow(),
    }
    await db[c.RESUME_VERSIONS].insert_one(doc)
    await db[c.RESUMES].update_one(
        {"_id": resume["_id"]},
        {"$set": {"current_version_id": doc["_id"], "version_count": version,
                  "updated_at": utcnow()}},
    )
    return doc


async def create_from_upload(
    db: AsyncIOMotorDatabase, user_id: str, *, name: str, kind: str, filename: str,
    content_type: str, data: bytes, text: str,
) -> dict:
    now = utcnow()
    file_id = new_id()
    await db[c.RESUME_FILES].insert_one({
        "_id": file_id, "user_id": user_id, "filename": filename, "content_type": content_type,
        "size": len(data), "data": Binary(data), "created_at": now,
    })
    resume = {
        "_id": new_id(), "user_id": user_id, "name": name, "kind": kind, "status": "active",
        "file_id": file_id, "filename": filename, "content_type": content_type,
        "size": len(data), "current_version_id": None, "version_count": 0,
        "created_at": now, "updated_at": now,
    }
    await db[c.RESUMES].insert_one(resume)
    parsed = parse_resume(text)
    await add_version(db, resume, parsed=parsed, raw_text=text, source="upload",
                      changes=["Initial upload and parse"])
    await log_action(db, user_id=user_id, action="resume.uploaded", entity="resume",
                     entity_id=resume["_id"],
                     details={"filename": filename, "kind": kind, "warnings": parsed.warnings})
    return await db[c.RESUMES].find_one({"_id": resume["_id"]})


async def current_version(db: AsyncIOMotorDatabase, resume: dict) -> dict | None:
    if not resume.get("current_version_id"):
        return None
    return await db[c.RESUME_VERSIONS].find_one({"_id": resume["current_version_id"]})


async def list_versions(db: AsyncIOMotorDatabase, resume_id: str) -> list[dict]:
    cursor = db[c.RESUME_VERSIONS].find({"resume_id": resume_id}).sort("version", DESCENDING)
    return await cursor.to_list(length=500)


def describe_changes(before: ParsedResume, after: ParsedResume) -> list[str]:
    changes: list[str] = []
    added = [s for s in after.skills if s not in before.skills]
    removed = [s for s in before.skills if s not in after.skills]
    if added:
        changes.append(f"Skills added: {', '.join(added)}")
    if removed:
        changes.append(f"Skills removed: {', '.join(removed)}")
    if before.summary != after.summary:
        changes.append("Summary edited")
    for field in ("experience", "projects", "education", "certifications", "achievements"):
        if getattr(before, field) != getattr(after, field):
            changes.append(f"{field.capitalize()} edited")
    for field in ("name", "email", "phone"):
        if getattr(before, field) != getattr(after, field):
            changes.append(f"{field.capitalize()} edited")
    return changes or ["No content changes"]


async def delete_resume(db: AsyncIOMotorDatabase, resume: dict) -> None:
    await db[c.RESUME_VERSIONS].delete_many({"resume_id": resume["_id"]})
    if resume.get("file_id"):
        # Duplicates share the file; only remove it when no other resume references it.
        others = await db[c.RESUMES].count_documents(
            {"file_id": resume["file_id"], "_id": {"$ne": resume["_id"]}})
        if not others:
            await db[c.RESUME_FILES].delete_one({"_id": resume["file_id"]})
    await db[c.RESUMES].delete_one({"_id": resume["_id"]})


async def import_to_profile(db: AsyncIOMotorDatabase, user_id: str, parsed: ParsedResume) -> dict:
    """Merge parsed resume data into the master profile.

    The master profile is the source of truth: existing values are never overwritten, only
    empty fields are filled and list sections are extended with entries not already present.
    """
    profile = await profiles.get_profile(db, user_id)
    applied: list[str] = []
    skipped: list[str] = []

    personal = profile.personal
    for field, value in (("name", parsed.name), ("email", parsed.email), ("phone", parsed.phone),
                         ("linkedin_url", parsed.links.linkedin),
                         ("github_url", parsed.links.github),
                         ("portfolio_url", parsed.links.portfolio)):
        if not value:
            continue
        if getattr(personal, field) in (None, ""):
            try:
                personal = PersonalInfo.model_validate({**personal.model_dump(), field: value})
            except ValidationError:
                skipped.append(f"personal.{field} (parsed value '{value}' is not valid)")
                continue
            applied.append(f"personal.{field}")
        elif str(getattr(personal, field)).rstrip("/") != value.rstrip("/"):
            skipped.append(f"personal.{field} (profile already has a different verified value)")

    skills = profile.skills.model_copy(deep=True)
    known = {s.lower() for s in skills.all()}
    for s in parsed.skills:
        if s.lower() not in known:
            cat = category_of(s)
            getattr(skills, cat).append(s)
            known.add(s.lower())
            applied.append(f"skills.{cat}: {s}")

    kb = profile.knowledge.model_copy(deep=True)
    if parsed.summary and not kb.professional_summary:
        kb.professional_summary = parsed.summary
        applied.append("knowledge.professional_summary")

    existing_exp = {(e.company.lower(), e.title.lower()) for e in kb.experience}
    for e in parsed.experience:
        if not e.company or not e.title:
            skipped.append(f"experience from {e.start_date}: company/title unconfirmed")
            continue
        if (e.company.lower(), e.title.lower()) in existing_exp:
            continue
        kb.experience.append(Experience(
            company=e.company, title=e.title, location=e.location, start_date=e.start_date,
            end_date=e.end_date, is_current=e.is_current, responsibilities=e.responsibilities,
            achievements=e.achievements, technologies=e.technologies))
        applied.append(f"knowledge.experience: {e.title} @ {e.company}")

    existing_edu = {e.degree.lower() for e in kb.education}
    for ed in parsed.education:
        if ed.degree and ed.degree.lower() not in existing_edu:
            kb.education.append(Education(degree=ed.degree, institution=ed.institution,
                                          field=ed.field, start_year=ed.start_year,
                                          end_year=ed.end_year))
            applied.append(f"knowledge.education: {ed.degree}")

    existing_certs = {x.name.lower() for x in kb.certifications}
    for cert in parsed.certifications:
        if cert and cert.lower() not in existing_certs:
            kb.certifications.append(Certification(name=cert[:200]))
            applied.append(f"knowledge.certifications: {cert}")

    existing_proj = {p.name.lower() for p in kb.projects}
    for p in parsed.projects:
        if p.name.lower() not in existing_proj:
            kb.projects.append(Project(name=p.name, highlights=p.highlights,
                                       technologies=p.technologies))
            applied.append(f"knowledge.projects: {p.name}")

    # Build from full dumps: in-place list appends aren't tracked as "set" fields by Pydantic.
    update = ProfileUpdate.model_validate({
        "personal": personal.model_dump(mode="json"),
        "skills": skills.model_dump(mode="json"),
        "knowledge": kb.model_dump(mode="json"),
    })
    out = await profiles.update_profile(db, user_id, update, source="resume_import")
    return {"applied": applied, "skipped": skipped, "completeness": out["completeness"]}

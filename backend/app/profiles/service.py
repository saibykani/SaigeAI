from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import collections as c
from app.schemas.profile import Profile, ProfileUpdate
from app.services.audit import log_action
from app.utils import new_id, utcnow

# (dotted path, label) - fields that make a profile usable for matching and generation.
COMPLETENESS_FIELDS: list[tuple[str, str]] = [
    ("personal.name", "Name"),
    ("personal.email", "Email"),
    ("personal.phone", "Phone"),
    ("personal.current_location", "Current Location"),
    ("personal.current_designation", "Current Designation"),
    ("personal.total_experience_years", "Total Experience"),
    ("personal.notice_period_days", "Notice Period"),
    ("personal.expected_ctc", "Expected CTC"),
    ("skills", "Skills"),
    ("knowledge.professional_summary", "Professional Summary"),
    ("knowledge.experience", "Experience"),
    ("knowledge.education", "Education"),
    ("preferences.target_roles", "Target Roles"),
    ("preferences.preferred_locations", "Preferred Locations"),
]


def _get(data: dict, path: str) -> Any:
    cur: Any = data
    for part in path.split("."):
        cur = cur.get(part) if isinstance(cur, dict) else None
    return cur


def _is_empty(value: Any) -> bool:
    if isinstance(value, dict):  # e.g. skills: empty when every category is empty
        return all(_is_empty(v) for v in value.values())
    return value in (None, "", [])


def completeness(data: dict) -> tuple[int, list[str]]:
    unknown = [label for path, label in COMPLETENESS_FIELDS if _is_empty(_get(data, path))]
    score = round(100 * (len(COMPLETENESS_FIELDS) - len(unknown)) / len(COMPLETENESS_FIELDS))
    return score, unknown


def to_profile(doc: dict | None) -> Profile:
    if not doc:
        return Profile()
    return Profile.model_validate({k: doc.get(k, {}) for k in Profile.model_fields})


def to_out(doc: dict | None) -> dict:
    data = to_profile(doc).model_dump(mode="json")
    score, unknown = completeness(data)
    updated = doc.get("updated_at") if doc else None
    return {**data, "completeness": score, "unknown_fields": unknown,
            "updated_at": updated.isoformat() if updated else None}


async def get_profile_doc(db: AsyncIOMotorDatabase, user_id: str) -> dict | None:
    return await db[c.CANDIDATE_PROFILES].find_one({"user_id": user_id})


async def get_profile(db: AsyncIOMotorDatabase, user_id: str) -> Profile:
    return to_profile(await get_profile_doc(db, user_id))


def _diff(before: dict, after: dict, prefix: str = "") -> list[dict]:
    changes = []
    for key in sorted(set(before) | set(after)):
        b, a = before.get(key), after.get(key)
        path = f"{prefix}{key}"
        if isinstance(b, dict) and isinstance(a, dict):
            changes += _diff(b, a, f"{path}.")
        elif b != a:
            changes.append({"field": path, "before": b, "after": a})
    return changes


def _deep_merge(base: dict, patch: dict) -> dict:
    """Merge nested dicts; lists and scalars (including explicit nulls) replace."""
    out = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


async def update_profile(
    db: AsyncIOMotorDatabase, user_id: str, update: ProfileUpdate, *, source: str = "user"
) -> dict:
    existing = await get_profile_doc(db, user_id)
    before = to_profile(existing).model_dump(mode="json")
    # Only fields the caller actually sent are applied; an explicit null clears a field.
    patch = update.model_dump(mode="json", exclude_unset=True)
    after = _deep_merge(before, {k: v for k, v in patch.items() if v is not None})
    # Validate the merged result as a whole.
    after = Profile.model_validate(after).model_dump(mode="json")
    changes = _diff(before, after)
    now = utcnow()
    await db[c.CANDIDATE_PROFILES].update_one(
        {"user_id": user_id},
        {"$set": {**after, "updated_at": now},
         "$setOnInsert": {"_id": new_id(), "user_id": user_id, "created_at": now}},
        upsert=True,
    )
    if changes:
        await log_action(db, user_id=user_id, action="profile.updated", entity="candidate_profile",
                         details={"source": source, "changes": changes[:200]})
    return to_out(await get_profile_doc(db, user_id))

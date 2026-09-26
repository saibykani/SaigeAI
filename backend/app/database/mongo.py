"""MongoDB connection management (Motor)."""

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from app.database import collections as c

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def connect(uri: str, db_name: str) -> AsyncIOMotorDatabase:
    global _client, _db
    _client = AsyncIOMotorClient(uri, uuidRepresentation="standard", tz_aware=True)
    _db = _client[db_name]
    return _db


def set_db(db: AsyncIOMotorDatabase | None) -> None:
    """Inject a database (used by tests)."""
    global _db
    _db = db


def is_connected() -> bool:
    return _db is not None


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not initialised")
    return _db


def close() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db[c.USERS].create_index("email", unique=True)
    await db[c.USERS].create_index("google_sub", unique=True, sparse=True)
    await db[c.REFRESH_TOKENS].create_index("user_id")
    await db[c.REFRESH_TOKENS].create_index("family_id")
    await db[c.REFRESH_TOKENS].create_index("expires_at", expireAfterSeconds=0)
    await db[c.CANDIDATE_PROFILES].create_index("user_id", unique=True)
    await db[c.RESUMES].create_index([("user_id", ASCENDING), ("updated_at", DESCENDING)])
    await db[c.RESUME_VERSIONS].create_index([("resume_id", ASCENDING), ("version", DESCENDING)])
    await db[c.AUDIT_LOGS].create_index([("user_id", ASCENDING), ("timestamp", DESCENDING)])
    await db[c.NOTIFICATIONS].create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db[c.JOBS].create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db[c.APPLICATIONS].create_index([("user_id", ASCENDING), ("status", ASCENDING)])
    await db[c.SYSTEM_SETTINGS].create_index("user_id", unique=True)
    logger.info("MongoDB indexes ensured")

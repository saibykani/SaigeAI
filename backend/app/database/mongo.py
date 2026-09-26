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
    # Short server-selection timeout: fail fast (and visibly) instead of hanging requests
    # for 30s when the database is unreachable, e.g. an Atlas IP access-list block.
    _client = AsyncIOMotorClient(uri, uuidRepresentation="standard", tz_aware=True,
                                 serverSelectionTimeoutMS=8000, connectTimeoutMS=8000)
    _db = _client[db_name]
    return _db


def set_db(db: AsyncIOMotorDatabase | None) -> None:
    """Inject a database (used by tests)."""
    global _db
    _db = db


def is_connected() -> bool:
    return _db is not None


def get_db() -> AsyncIOMotorDatabase:
    # Connect lazily: serverless runtimes (e.g. Vercel) may not run the ASGI lifespan hook.
    if _db is None:
        from app.config import get_settings

        s = get_settings()
        connect(s.mongodb_uri, s.mongodb_db)
    return _db  # type: ignore[return-value]


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
    await db[c.JOBS].create_index([("user_id", ASCENDING), ("company_key", ASCENDING)])
    await db[c.JOBS].create_index([("user_id", ASCENDING), ("match.overall", DESCENDING)])
    await db[c.JOBS].create_index([("user_id", ASCENDING), ("sources.url_key", ASCENDING)])
    await db[c.JOB_SOURCES].create_index([("user_id", ASCENDING), ("provider", ASCENDING),
                                          ("board", ASCENDING)], unique=True)
    await db[c.AGENT_RUNS].create_index([("user_id", ASCENDING), ("start_time", DESCENDING)])
    await db[c.APPLICATIONS].create_index([("user_id", ASCENDING), ("status", ASCENDING)])
    await db[c.SYSTEM_SETTINGS].create_index("user_id", unique=True)
    logger.info("MongoDB indexes ensured")

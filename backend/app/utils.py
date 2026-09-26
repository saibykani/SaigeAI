"""Small shared helpers."""

import uuid
from datetime import UTC, datetime


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


def start_of_today() -> datetime:
    return utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


def as_utc(dt: datetime) -> datetime:
    """Mongo drivers/mocks may return naive datetimes; treat them as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)

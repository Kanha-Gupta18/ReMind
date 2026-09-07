"""Shared helpers for every ORM model."""

from datetime import datetime, timezone
from uuid import uuid4


def new_id() -> str:
    """Every table uses a UUID string as its primary key."""
    return str(uuid4())


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp for PostgreSQL timestamptz columns."""
    return datetime.now(timezone.utc)

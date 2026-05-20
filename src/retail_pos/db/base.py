"""SQLAlchemy declarative base and shared mixins.

All ORM models inherit from :class:`Base`. Tables that need to be synced to the
cloud should also include :class:`TimestampMixin` and :class:`SyncMixin`, which
provide the ``created_at`` / ``updated_at`` and ``synced`` columns used by the
sync engine.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


def generate_uuid() -> str:
    """Generate a new UUID4 string.

    UUIDs are stored as 36-char strings to keep SQLite portable and to make
    debugging easier. They are generated locally so each terminal can create
    rows offline without coordinating with the server.
    """
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""

    pass


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` columns.

    ``updated_at`` is used by the sync engine for last-write-wins conflict
    resolution.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )


class SyncMixin:
    """Adds the ``synced`` flag used by the cloud sync engine.

    ``False`` means the row has local changes that have not yet been uploaded.
    The sync worker scans for ``synced=False`` rows and pushes them to the
    server.
    """

    synced: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

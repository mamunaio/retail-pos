"""User model: cashiers and admins who log in to the POS terminal."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from retail_pos.db.base import Base, SyncMixin, TimestampMixin, generate_uuid


class UserRole(StrEnum):
    """Allowed roles for a user."""

    ADMIN = "admin"
    CASHIER = "cashier"


class User(Base, TimestampMixin, SyncMixin):
    """A person who logs in to the POS.

    Authentication uses a numeric PIN (4-6 digits) to keep cashier login fast.
    The PIN is stored as a bcrypt hash in :attr:`pin_hash`.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=UserRole.CASHIER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id!s} username={self.username!r} role={self.role!r}>"

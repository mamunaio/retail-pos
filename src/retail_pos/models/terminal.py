"""Terminal model: a physical POS machine in the shop."""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from retail_pos.db.base import Base, SyncMixin, TimestampMixin, generate_uuid


class Terminal(Base, TimestampMixin, SyncMixin):
    """A single POS workstation.

    ``device_fingerprint`` will hold a hash of MAC + CPU ID once license
    enforcement is implemented. Storing the column now avoids a future schema
    migration.
    """

    __tablename__ = "terminals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    terminal_code: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    device_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Terminal id={self.id!s} code={self.terminal_code!r}>"

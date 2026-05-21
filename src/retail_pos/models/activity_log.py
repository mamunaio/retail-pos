"""Activity log model for audit trail."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retail_pos.db.base import Base, TimestampMixin, generate_uuid


class ActivityType(StrEnum):
    """Types of activities to log."""

    # User activities
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"

    # Product activities
    PRODUCT_CREATED = "product_created"
    PRODUCT_UPDATED = "product_updated"
    PRODUCT_DELETED = "product_deleted"

    # Inventory activities
    STOCK_ADJUSTED = "stock_adjusted"
    STOCK_LOW_ALERT = "stock_low_alert"

    # Sales activities
    SALE_CREATED = "sale_created"
    SALE_CANCELLED = "sale_cancelled"
    SALE_REFUNDED = "sale_refunded"

    # System activities
    SYSTEM_ERROR = "system_error"
    SYSTEM_WARNING = "system_warning"


class ActivityLog(Base, TimestampMixin):
    """Activity log for audit trail.

    Records all significant actions in the system for security and debugging.
    """

    __tablename__ = "activity_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    terminal_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("terminals.id", ondelete="SET NULL"), nullable=True
    )

    # Resource information
    resource_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Type of resource (product, sale, etc.)"
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True, comment="ID of the affected resource"
    )

    # Activity details
    description: Mapped[str] = mapped_column(Text, nullable=False)
    extra_data: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="JSON string with additional data"
    )

    # IP and user agent for security
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")  # type: ignore[name-defined]
    terminal: Mapped["Terminal"] = relationship("Terminal")  # type: ignore[name-defined]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ActivityLog {self.activity_type} by user={self.user_id}>"

"""Customer model for customer relationship management."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retail_pos.db.base import Base, SyncMixin, TimestampMixin, generate_uuid


class Customer(Base, TimestampMixin, SyncMixin):
    """Customer information for CRM and loyalty programs.

    Stores customer details, contact information, and loyalty points.
    """

    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    customer_code: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True, comment="Unique customer code"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Loyalty program
    loyalty_points: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    total_purchases: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), comment="Lifetime purchase value"
    )
    purchase_count: Mapped[int] = mapped_column(
        default=0, nullable=False, comment="Total number of purchases"
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    sales: Mapped[list["Sale"]] = relationship(  # type: ignore[name-defined]
        "Sale", back_populates="customer", foreign_keys="Sale.customer_id"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Customer id={self.id!s} code={self.customer_code!r} name={self.name!r}>"

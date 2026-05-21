"""Supplier model for purchase management."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retail_pos.db.base import Base, SyncMixin, TimestampMixin, generate_uuid


class Supplier(Base, TimestampMixin, SyncMixin):
    """Supplier information for purchase management.

    Stores supplier details, contact information, and payment terms.
    """

    __tablename__ = "suppliers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    supplier_code: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True, comment="Unique supplier code"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    company_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Business details
    contact_person: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="e.g., Net 30, COD, etc."
    )
    credit_limit: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )

    # Statistics
    total_purchases: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), comment="Lifetime purchase value"
    )
    purchase_count: Mapped[int] = mapped_column(
        default=0, nullable=False, comment="Total number of purchases"
    )
    outstanding_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), comment="Unpaid amount"
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    purchases: Mapped[list["Purchase"]] = relationship(  # type: ignore[name-defined]
        "Purchase", back_populates="supplier", foreign_keys="Purchase.supplier_id"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Supplier id={self.id!s} code={self.supplier_code!r} name={self.name!r}>"

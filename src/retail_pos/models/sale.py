"""Sale model: a single transaction from start to completion or void."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retail_pos.db.base import Base, SyncMixin, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from retail_pos.models.payment import Payment
    from retail_pos.models.sale_item import SaleItem


class SaleStatus(StrEnum):
    """The lifecycle of a sale.

    Allowed transitions:
        DRAFT  -> HELD     (cashier paused to serve another customer)
        DRAFT  -> COMPLETED (payment(s) cover total, stock deducted)
        DRAFT  -> VOID     (cancelled before payment)
        HELD   -> DRAFT    (resumed)
        HELD   -> VOID     (abandoned permanently)

    Once COMPLETED or VOID, a sale is immutable.
    """

    DRAFT = "draft"
    HELD = "held"
    COMPLETED = "completed"
    VOID = "void"


class Sale(Base, TimestampMixin, SyncMixin):
    """The header row for one POS transaction.

    Money invariants (enforced by the service layer, see ``services.sales``):
        line_total      = (unit_price * quantity) - line_discount   (per item)
        subtotal        = SUM(line_total) over all items
        total_amount    = subtotal - cart_discount
        amount_paid     = SUM(payments.amount)
        change_amount   = amount_tendered - total_amount  (only when COMPLETED)
        amount_paid     >= total_amount                   (when COMPLETED)
    """

    __tablename__ = "sales"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    # Who and where
    terminal_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("terminals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cashier_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Customer is intentionally a free string id, not a FK, because the
    # customers table doesn't exist yet. When it lands the column becomes a
    # real FK without losing data.
    customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Money snapshot (filled progressively by the service)
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    cart_discount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    amount_tendered: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    change_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SaleStatus.DRAFT, index=True
    )
    receipt_number: Mapped[str | None] = mapped_column(
        String(40), nullable=True, unique=True, index=True
    )
    void_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    voided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Eager-loaded children: when we load a Sale we almost always want its
    # items and payments, so a SELECT IN load avoids the N+1 problem.
    items: Mapped[list["SaleItem"]] = relationship(
        "SaleItem",
        back_populates="sale",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="SaleItem.created_at",
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="sale",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Payment.created_at",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Sale id={self.id!s} status={self.status!r} "
            f"total={self.total_amount}>"
        )

"""Payment model: how a sale was paid for."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retail_pos.db.base import Base, SyncMixin, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from retail_pos.models.sale import Sale


class PaymentMethod(StrEnum):
    """Allowed payment instruments.

    Add new entries here as MFS providers / card processors are integrated.
    Avoid renaming existing values - they are persisted in receipts.
    """

    CASH = "cash"
    CARD = "card"
    BKASH = "bkash"
    NAGAD = "nagad"
    OTHER = "other"


class Payment(Base, TimestampMixin, SyncMixin):
    """One tender against a sale.

    A single sale can have multiple payments (split tender, e.g. partial
    cash + partial bKash). The sum of ``amount`` across all payment rows of
    a sale must be at least the sale's ``total_amount`` for the sale to
    transition to ``COMPLETED``.
    """

    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    sale_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sales.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # Provider transaction id, last-4 of card, etc. Free-form for MVP.
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)

    sale: Mapped["Sale"] = relationship("Sale", back_populates="payments")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Payment sale_id={self.sale_id!s} method={self.method!r} "
            f"amount={self.amount}>"
        )

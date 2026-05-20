"""Stock movement model: append-only audit log of inventory changes."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from retail_pos.db.base import Base, SyncMixin, TimestampMixin, generate_uuid


class MovementType(StrEnum):
    """Reasons a stock level can change.

    The set is intentionally small for the MVP. Each value pairs with a
    real-world business event so reports can group movements meaningfully.
    """

    INITIAL = "initial"        # opening balance / first stock count
    PURCHASE = "purchase"      # received from supplier
    SALE = "sale"              # sold to a customer (delta is negative)
    RETURN = "return"          # customer returned an item (delta is positive)
    ADJUSTMENT = "adjustment"  # manual fix (damage, theft, count correction)


class StockMovement(Base, TimestampMixin, SyncMixin):
    """One entry in the immutable history of stock changes for a product.

    ``quantity_delta`` is signed: positive numbers add to stock, negative
    numbers remove. A running sum of all deltas for a given ``product_id``
    must equal the current :class:`Inventory.quantity` (modulo any
    in-flight transactions). This invariant is what makes the system
    auditable.

    ``reference_id`` / ``reference_type`` link back to the source
    transaction (e.g. a sale id or purchase id) so a stock change can be
    traced to the operational event that caused it.
    """

    __tablename__ = "stock_movements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    product_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    reference_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reference_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<StockMovement product_id={self.product_id!s} "
            f"type={self.movement_type!r} delta={self.quantity_delta}>"
        )

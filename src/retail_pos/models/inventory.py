"""Inventory model: current stock-on-hand for each product."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retail_pos.db.base import Base, SyncMixin, TimestampMixin, generate_uuid


class Inventory(Base, TimestampMixin, SyncMixin):
    """The current quantity-on-hand of a single product.

    There is at most one inventory row per product (enforced by UNIQUE on
    ``product_id``). Stock changes are applied through the inventory service,
    which always writes a corresponding :class:`StockMovement` audit row in
    the same transaction so the running total can be reconciled against the
    movement history.

    Notes:
      * Quantities use ``Decimal`` because some products are sold by weight
        (kg, gram). Using ``Integer`` would silently truncate fractional
        sales of e.g. rice.
      * Stock can legitimately go negative when a sale is recorded before
        the corresponding purchase is captured. Higher-level services may
        enforce stricter rules on top of this.
    """

    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint("product_id", name="uq_inventory_product"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    product_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=Decimal("0.000")
    )
    reorder_level: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=Decimal("0.000")
    )

    product = relationship("Product", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Inventory product_id={self.product_id!s} "
            f"quantity={self.quantity} reorder_level={self.reorder_level}>"
        )

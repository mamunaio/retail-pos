"""Inventory models: stock tracking and movement history."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retail_pos.db.base import Base, SyncMixin, TimestampMixin, generate_uuid


class StockMovementType(StrEnum):
    """Types of stock movements."""

    INITIAL = "initial"  # Initial stock entry
    PURCHASE = "purchase"  # Stock received from supplier
    SALE = "sale"  # Stock sold to customer
    ADJUSTMENT = "adjustment"  # Manual stock adjustment (damage, theft, etc.)
    RETURN = "return"  # Customer return


class Inventory(Base, TimestampMixin, SyncMixin):
    """Current stock level for each product.

    This table maintains the current quantity available for each product.
    One row per product. Updated whenever stock moves in or out.
    """

    __tablename__ = "inventory"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    reorder_level: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("10.00")
    )
    low_stock_alert: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="inventory")  # type: ignore[name-defined]
    movements: Mapped[list["StockMovement"]] = relationship(
        "StockMovement", back_populates="inventory", cascade="all, delete-orphan"
    )

    @property
    def is_low_stock(self) -> bool:
        """Check if current stock is below reorder level."""
        return self.low_stock_alert and self.quantity <= self.reorder_level

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Inventory product_id={self.product_id!r} quantity={self.quantity}>"


class StockMovement(Base, TimestampMixin, SyncMixin):
    """History of all stock movements (in/out/adjustments).

    Every time stock changes, a record is created here. This provides a full
    audit trail of inventory changes.
    """

    __tablename__ = "stock_movements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    inventory_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inventory.id", ondelete="CASCADE"), nullable=False, index=True
    )
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    quantity_change: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Positive for stock in, negative for stock out"
    )
    quantity_after: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Stock level after this movement"
    )
    reference_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        comment="ID of related record (sale_id, purchase_id, etc.)",
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    inventory: Mapped["Inventory"] = relationship("Inventory", back_populates="movements")
    user: Mapped["User"] = relationship("User")  # type: ignore[name-defined]

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<StockMovement id={self.id!s} type={self.movement_type!r} "
            f"change={self.quantity_change}>"
        )

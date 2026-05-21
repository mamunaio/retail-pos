"""Purchase models for inventory procurement."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retail_pos.db.base import Base, SyncMixin, TimestampMixin, generate_uuid


class PurchaseStatus(str, Enum):
    """Purchase order status."""

    DRAFT = "draft"  # Order being prepared
    ORDERED = "ordered"  # Order placed with supplier
    RECEIVED = "received"  # Goods received
    CANCELLED = "cancelled"  # Order cancelled


class PaymentStatus(str, Enum):
    """Payment status for purchases."""

    UNPAID = "unpaid"
    PARTIAL = "partial"
    PAID = "paid"


class Purchase(Base, TimestampMixin, SyncMixin):
    """Purchase order for inventory procurement.

    Tracks purchase orders from suppliers including items, costs, and payment.
    """

    __tablename__ = "purchases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    purchase_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True, comment="e.g., PO-20240521-0001"
    )

    # Supplier information
    supplier_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("suppliers.id"), nullable=False, index=True
    )

    # Purchase details
    purchase_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    expected_delivery_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Financial
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, comment="Sum of all items"
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    shipping_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, comment="Final amount to pay"
    )
    paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PurchaseStatus.DRAFT.value, index=True
    )
    payment_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PaymentStatus.UNPAID.value, index=True
    )

    # Additional info
    reference_number: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Supplier's invoice/reference number"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # User tracking
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    received_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    # Relationships
    supplier: Mapped["Supplier"] = relationship(  # type: ignore[name-defined]
        "Supplier", back_populates="purchases", foreign_keys=[supplier_id]
    )
    items: Mapped[list["PurchaseItem"]] = relationship(
        "PurchaseItem", back_populates="purchase", cascade="all, delete-orphan"
    )
    creator: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[created_by]
    )
    receiver: Mapped["User | None"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[received_by]
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Purchase id={self.id!s} number={self.purchase_number!r} status={self.status!r}>"


class PurchaseItem(Base, TimestampMixin):
    """Individual item in a purchase order."""

    __tablename__ = "purchase_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    purchase_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("purchases.id"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id"), nullable=False, index=True
    )

    # Quantities
    quantity_ordered: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Quantity ordered"
    )
    quantity_received: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00"), comment="Quantity received"
    )

    # Pricing
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Cost per unit"
    )
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, comment="quantity * unit_cost"
    )

    # Additional info
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    purchase: Mapped["Purchase"] = relationship("Purchase", back_populates="items")
    product: Mapped["Product"] = relationship("Product")  # type: ignore[name-defined]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PurchaseItem id={self.id!s} product_id={self.product_id!s} qty={self.quantity_ordered}>"

"""Sale models: invoices, line items, and payments."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retail_pos.db.base import Base, SyncMixin, TimestampMixin, generate_uuid


class PaymentMethod(StrEnum):
    """Payment methods accepted."""

    CASH = "cash"
    CARD = "card"
    MOBILE = "mobile"  # bKash, Nagad, etc.
    MIXED = "mixed"  # Multiple payment methods


class SaleStatus(StrEnum):
    """Sale status."""

    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Sale(Base, TimestampMixin, SyncMixin):
    """A sale transaction (invoice).

    Represents a complete sale with multiple line items and payment information.
    """

    __tablename__ = "sales"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    invoice_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    terminal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("terminals.id", ondelete="RESTRICT"), nullable=False
    )
    cashier_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    customer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Amounts
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Sum of all line items before tax"
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Final amount to pay"
    )

    # Payment
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    change_given: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SaleStatus.COMPLETED, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    terminal: Mapped["Terminal"] = relationship("Terminal")  # type: ignore[name-defined]
    cashier: Mapped["User"] = relationship("User")  # type: ignore[name-defined]
    customer: Mapped["Customer"] = relationship(  # type: ignore[name-defined]
        "Customer", back_populates="sales", foreign_keys="Sale.customer_id"
    )
    items: Mapped[list["SaleItem"]] = relationship(
        "SaleItem", back_populates="sale", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Sale id={self.id!s} invoice={self.invoice_number!r} total={self.total_amount}>"


class SaleItem(Base, TimestampMixin, SyncMixin):
    """A line item in a sale (one product).

    Each row represents one product in the sale with its quantity and price.
    """

    __tablename__ = "sale_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    sale_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )

    # Product snapshot (in case product details change later)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_barcode: Mapped[str] = mapped_column(String(50), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Price per unit at time of sale"
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Total for this line (qty × price - discount + tax)"
    )

    # Relationships
    sale: Mapped["Sale"] = relationship("Sale", back_populates="items")
    product: Mapped["Product"] = relationship("Product")  # type: ignore[name-defined]

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<SaleItem id={self.id!s} product={self.product_name!r} "
            f"qty={self.quantity} total={self.line_total}>"
        )

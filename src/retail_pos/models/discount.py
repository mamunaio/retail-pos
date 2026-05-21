"""Discount and promotion models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retail_pos.db.base import Base, SyncMixin, TimestampMixin, generate_uuid


class DiscountType(str, Enum):
    """Types of discounts."""

    PERCENTAGE = "percentage"  # Percentage off (e.g., 10% off)
    FIXED_AMOUNT = "fixed_amount"  # Fixed amount off (e.g., ৳50 off)
    BUY_X_GET_Y = "buy_x_get_y"  # Buy X get Y free


class DiscountScope(str, Enum):
    """Scope of discount application."""

    ORDER = "order"  # Apply to entire order
    CATEGORY = "category"  # Apply to specific category
    PRODUCT = "product"  # Apply to specific products


class Discount(Base, TimestampMixin, SyncMixin):
    """Discount and promotion configuration.

    Supports various discount types, automatic application, and promo codes.
    """

    __tablename__ = "discounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True, comment="Discount/Promo code"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Discount configuration
    discount_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="percentage, fixed_amount, buy_x_get_y"
    )
    discount_scope: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="order, category, product"
    )

    # Discount values
    discount_value: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Percentage or fixed amount"
    )
    max_discount_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True, comment="Maximum discount amount (for percentage)"
    )

    # Buy X Get Y configuration
    buy_quantity: Mapped[int | None] = mapped_column(
        nullable=True, comment="Buy X quantity (for buy_x_get_y)"
    )
    get_quantity: Mapped[int | None] = mapped_column(
        nullable=True, comment="Get Y quantity free (for buy_x_get_y)"
    )

    # Minimum requirements
    min_purchase_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00"), comment="Minimum order amount"
    )
    min_quantity: Mapped[int] = mapped_column(
        default=0, nullable=False, comment="Minimum quantity required"
    )

    # Scope filters
    category: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Category for category-scoped discounts"
    )
    product_ids: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Comma-separated product IDs for product-scoped discounts"
    )

    # Validity period
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Usage limits
    usage_limit: Mapped[int | None] = mapped_column(
        nullable=True, comment="Total usage limit (null = unlimited)"
    )
    usage_limit_per_customer: Mapped[int | None] = mapped_column(
        nullable=True, comment="Usage limit per customer (null = unlimited)"
    )
    usage_count: Mapped[int] = mapped_column(
        default=0, nullable=False, comment="Current usage count"
    )

    # Behavior
    is_automatic: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="Auto-apply without code"
    )
    requires_code: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="Requires promo code"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_stackable: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="Can combine with other discounts"
    )

    # Priority (higher = applied first)
    priority: Mapped[int] = mapped_column(default=0, nullable=False)

    # Metadata
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # type: ignore[name-defined]
    usage_logs: Mapped[list["DiscountUsage"]] = relationship(
        "DiscountUsage", back_populates="discount", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Discount id={self.id!s} code={self.code!r} type={self.discount_type!r}>"

    def is_valid(self, check_time: datetime | None = None) -> bool:
        """Check if discount is currently valid.

        Args:
            check_time: Time to check validity (defaults to now)

        Returns:
            True if discount is valid
        """
        if not self.is_active:
            return False

        check_time = check_time or datetime.now()

        if check_time < self.valid_from:
            return False

        if self.valid_until and check_time > self.valid_until:
            return False

        if self.usage_limit and self.usage_count >= self.usage_limit:
            return False

        return True


class DiscountUsage(Base, TimestampMixin):
    """Track discount usage history."""

    __tablename__ = "discount_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    discount_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("discounts.id"), nullable=False, index=True
    )
    sale_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sales.id"), nullable=False, index=True
    )
    customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=True, index=True
    )

    # Discount details at time of use
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Actual discount amount applied"
    )
    original_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Amount before discount"
    )

    # Relationships
    discount: Mapped["Discount"] = relationship("Discount", back_populates="usage_logs")
    sale: Mapped["Sale"] = relationship("Sale")  # type: ignore[name-defined]
    customer: Mapped["Customer | None"] = relationship("Customer")  # type: ignore[name-defined]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DiscountUsage id={self.id!s} discount_id={self.discount_id!s} amount={self.discount_amount}>"

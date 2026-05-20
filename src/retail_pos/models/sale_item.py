"""SaleItem model: one line on a receipt."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retail_pos.db.base import Base, SyncMixin, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from retail_pos.models.sale import Sale


class SaleItem(Base, TimestampMixin, SyncMixin):
    """One product line on a sale.

    Several columns are *snapshots* of the related ``Product`` row at the
    moment the line was added (``product_name``, ``barcode_snapshot``,
    ``unit``, ``unit_price``, ``tax_rate``). This is critical for two reasons:

      1. **Receipt accuracy.** A receipt printed last month must still show
         the price the customer paid, even if the product has been renamed
         or repriced since.
      2. **Auditability.** Reconciling sales to inventory must work even if
         a product is later deactivated.

    ``line_total`` is also persisted (rather than computed on read) so the
    sum-of-line-totals invariant on ``Sale`` can be enforced cheaply.
    """

    __tablename__ = "sale_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    sale_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sales.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Product snapshot at the time of sale
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    barcode_snapshot: Mapped[str] = mapped_column(String(50), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )

    # Line-specific values
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    sale: Mapped["Sale"] = relationship("Sale", back_populates="items")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<SaleItem sale_id={self.sale_id!s} product={self.product_name!r} "
            f"qty={self.quantity} total={self.line_total}>"
        )

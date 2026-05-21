"""Product model: items that can be sold."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retail_pos.db.base import Base, SyncMixin, TimestampMixin, generate_uuid


class ProductUnit(StrEnum):
    """Allowed units for a product."""

    PIECE = "pcs"
    KILOGRAM = "kg"
    LITER = "liter"
    GRAM = "g"
    METER = "m"


class Product(Base, TimestampMixin, SyncMixin):
    """An item available for sale.

    ``category`` is a free-form string for the MVP. It will be normalized into
    a separate ``categories`` table when the catalog grows.

    Note: never hard-delete products that have been sold. Set
    :attr:`is_active` to ``False`` instead, otherwise historical sale records
    will lose their product reference.
    """

    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    barcode: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default=ProductUnit.PIECE)
    cost_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    selling_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    inventory: Mapped["Inventory"] = relationship(  # type: ignore[name-defined]
        "Inventory", back_populates="product", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product id={self.id!s} barcode={self.barcode!r} name={self.name!r}>"

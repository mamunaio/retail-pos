"""Seed sample data for local development.

Creates:
  - 1 admin user (username ``admin``, PIN ``1234``)
  - 1 cashier user (username ``cashier1``, PIN ``0000``)
  - 1 terminal (``POS-01``)
  - A handful of sample products, each with an opening stock balance and a
    reorder level so the inventory and low-stock features have something to
    show.

Safe to run multiple times: existing rows (matched by their unique key) are
skipped, and inventory is only initialised for products that don't yet have
any stock movement recorded.

Usage:
    python -m scripts.seed
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from retail_pos.db import session_scope
from retail_pos.models import (
    MovementType,
    Product,
    ProductUnit,
    StockMovement,
    Terminal,
    User,
    UserRole,
)
from retail_pos.services.inventory import record_initial_stock, set_reorder_level
from retail_pos.utils.security import hash_pin


def _get_or_create_user(
    db: Session, *, username: str, pin: str, full_name: str, role: UserRole
) -> User:
    existing = db.scalar(select(User).where(User.username == username))
    if existing is not None:
        return existing
    user = User(
        username=username,
        pin_hash=hash_pin(pin),
        full_name=full_name,
        role=role,
    )
    db.add(user)
    return user


def _get_or_create_terminal(db: Session, *, terminal_code: str, name: str) -> Terminal:
    existing = db.scalar(select(Terminal).where(Terminal.terminal_code == terminal_code))
    if existing is not None:
        return existing
    terminal = Terminal(terminal_code=terminal_code, name=name)
    db.add(terminal)
    return terminal


def _get_or_create_product(
    db: Session,
    *,
    barcode: str,
    name: str,
    category: str,
    unit: ProductUnit,
    cost_price: Decimal,
    selling_price: Decimal,
) -> Product:
    existing = db.scalar(select(Product).where(Product.barcode == barcode))
    if existing is not None:
        return existing
    product = Product(
        barcode=barcode,
        name=name,
        category=category,
        unit=unit,
        cost_price=cost_price,
        selling_price=selling_price,
    )
    db.add(product)
    return product


SAMPLE_PRODUCTS: list[dict[str, object]] = [
    {
        "barcode": "8901234567890",
        "name": "Pran Mango Juice 250ml",
        "category": "Beverages",
        "unit": ProductUnit.PIECE,
        "cost_price": Decimal("18.00"),
        "selling_price": Decimal("25.00"),
        "initial_stock": Decimal("48"),
        "reorder_level": Decimal("12"),
    },
    {
        "barcode": "8901234567891",
        "name": "Coca-Cola 500ml",
        "category": "Beverages",
        "unit": ProductUnit.PIECE,
        "cost_price": Decimal("32.00"),
        "selling_price": Decimal("40.00"),
        "initial_stock": Decimal("24"),
        "reorder_level": Decimal("6"),
    },
    {
        "barcode": "8901234567892",
        "name": "Miniket Rice (loose)",
        "category": "Grocery",
        "unit": ProductUnit.KILOGRAM,
        "cost_price": Decimal("65.00"),
        "selling_price": Decimal("75.00"),
        "initial_stock": Decimal("100.000"),
        "reorder_level": Decimal("20.000"),
    },
    {
        "barcode": "8901234567893",
        "name": "Soybean Oil 1L",
        "category": "Grocery",
        "unit": ProductUnit.PIECE,
        "cost_price": Decimal("165.00"),
        "selling_price": Decimal("185.00"),
        "initial_stock": Decimal("30"),
        "reorder_level": Decimal("8"),
    },
    {
        "barcode": "8901234567894",
        "name": "Lux Soap 100g",
        "category": "Toiletries",
        "unit": ProductUnit.PIECE,
        "cost_price": Decimal("45.00"),
        "selling_price": Decimal("55.00"),
        "initial_stock": Decimal("60"),
        "reorder_level": Decimal("15"),
    },
]


def _has_movements(db: Session, product: Product) -> bool:
    return db.scalar(
        select(StockMovement.id).where(StockMovement.product_id == product.id).limit(1)
    ) is not None


def seed() -> None:
    """Populate the local database with development sample data."""
    with session_scope() as db:
        admin = _get_or_create_user(
            db,
            username="admin",
            pin="1234",
            full_name="Shop Admin",
            role=UserRole.ADMIN,
        )
        _get_or_create_user(
            db,
            username="cashier1",
            pin="0000",
            full_name="Cashier One",
            role=UserRole.CASHIER,
        )

        _get_or_create_terminal(db, terminal_code="POS-01", name="Front Counter")

        # Flush so the admin user has an id we can attribute opening stock to.
        db.flush()

        for item in SAMPLE_PRODUCTS:
            initial_stock = item.pop("initial_stock")  # type: ignore[arg-type]
            reorder_level = item.pop("reorder_level")  # type: ignore[arg-type]
            product = _get_or_create_product(db, **item)  # type: ignore[arg-type]
            db.flush()

            # Only seed inventory for products we haven't seeded before. This
            # keeps repeated seed runs idempotent (no duplicate INITIAL rows).
            if not _has_movements(db, product):
                set_reorder_level(db, product, reorder_level)
                record_initial_stock(
                    db,
                    product,
                    initial_stock,
                    user_id=admin.id,
                    notes="Opening stock from seed script",
                )

    print("Seed complete:")
    print("  - admin    / PIN 1234")
    print("  - cashier1 / PIN 0000")
    print("  - terminal POS-01")
    print(f"  - {len(SAMPLE_PRODUCTS)} sample products with opening stock + reorder levels")


if __name__ == "__main__":
    seed()

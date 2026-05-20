"""Smoke tests verifying the core models can be created and queried."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from retail_pos.models import Product, ProductUnit, Terminal, User, UserRole
from retail_pos.utils.security import hash_pin, verify_pin


def test_create_user_with_pin(db_session: Session) -> None:
    user = User(
        username="admin",
        pin_hash=hash_pin("1234"),
        full_name="Shop Admin",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    db_session.commit()

    fetched = db_session.scalar(select(User).where(User.username == "admin"))
    assert fetched is not None
    assert fetched.full_name == "Shop Admin"
    assert fetched.role == UserRole.ADMIN
    assert fetched.is_active is True
    assert fetched.synced is False  # newly created rows are not yet synced
    assert fetched.id  # auto-generated UUID
    assert verify_pin("1234", fetched.pin_hash) is True
    assert verify_pin("9999", fetched.pin_hash) is False


def test_create_terminal(db_session: Session) -> None:
    terminal = Terminal(terminal_code="POS-01", name="Front Counter")
    db_session.add(terminal)
    db_session.commit()

    fetched = db_session.scalar(
        select(Terminal).where(Terminal.terminal_code == "POS-01")
    )
    assert fetched is not None
    assert fetched.name == "Front Counter"
    assert fetched.is_active is True
    assert fetched.device_fingerprint is None


def test_create_product(db_session: Session) -> None:
    product = Product(
        barcode="8901234567890",
        name="Pran Mango Juice 250ml",
        category="Beverages",
        unit=ProductUnit.PIECE,
        cost_price=Decimal("18.00"),
        selling_price=Decimal("25.00"),
    )
    db_session.add(product)
    db_session.commit()

    fetched = db_session.scalar(
        select(Product).where(Product.barcode == "8901234567890")
    )
    assert fetched is not None
    assert fetched.name == "Pran Mango Juice 250ml"
    assert fetched.selling_price == Decimal("25.00")
    assert fetched.tax_rate == Decimal("0.00")
    assert fetched.is_active is True

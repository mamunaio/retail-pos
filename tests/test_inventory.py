"""Tests for the inventory service."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from retail_pos.models import Inventory, MovementType, Product, StockMovement
from retail_pos.services.inventory import (
    MAX_PAGE_SIZE,
    InvalidMovementError,
    adjust_stock,
    count_movements,
    get_inventory,
    get_stock,
    list_movements,
    low_stock_products,
    record_initial_stock,
    set_reorder_level,
)
from retail_pos.services.products import create_product, deactivate_product


# --- Helpers ------------------------------------------------------------------


def _make_product(
    db: Session, *, barcode: str = "P-001", name: str = "Test Product"
) -> Product:
    p = create_product(
        db,
        barcode=barcode,
        name=name,
        selling_price=Decimal("100.00"),
        cost_price=Decimal("70.00"),
    )
    db.commit()
    return p


def _movements_for(db: Session, product_id: str) -> list[StockMovement]:
    return list(
        db.scalars(
            select(StockMovement)
            .where(StockMovement.product_id == product_id)
            .order_by(StockMovement.created_at)
        )
    )


# --- get_stock / get_inventory ------------------------------------------------


def test_get_stock_returns_zero_when_no_row(db_session: Session) -> None:
    product = _make_product(db_session)

    assert get_stock(db_session, product.id) == Decimal("0.000")
    assert get_inventory(db_session, product.id) is None


# --- adjust_stock -------------------------------------------------------------


def test_adjust_stock_creates_inventory_row_on_first_call(db_session: Session) -> None:
    product = _make_product(db_session)

    movement = adjust_stock(
        db_session, product, 50, movement_type=MovementType.PURCHASE
    )
    db_session.commit()

    inv = get_inventory(db_session, product.id)
    assert inv is not None
    assert inv.quantity == Decimal("50")
    assert movement.quantity_delta == Decimal("50")
    assert movement.movement_type == MovementType.PURCHASE


def test_adjust_stock_accumulates(db_session: Session) -> None:
    product = _make_product(db_session)

    adjust_stock(db_session, product, 100, movement_type=MovementType.PURCHASE)
    adjust_stock(db_session, product, -10, movement_type=MovementType.SALE)
    adjust_stock(db_session, product, 2, movement_type=MovementType.RETURN)
    db_session.commit()

    assert get_stock(db_session, product.id) == Decimal("92")


def test_adjust_stock_invariant_running_sum_equals_current(
    db_session: Session,
) -> None:
    """The running sum of all movements must reconcile to current Inventory.quantity."""
    product = _make_product(db_session)
    deltas = [Decimal("100"), Decimal("-15.5"), Decimal("3"), Decimal("-1.5")]
    for delta in deltas:
        adjust_stock(
            db_session, product, delta, movement_type=MovementType.ADJUSTMENT
        )
    db_session.commit()

    movements = _movements_for(db_session, product.id)
    assert sum((m.quantity_delta for m in movements), Decimal("0")) == get_stock(
        db_session, product.id
    )


def test_adjust_stock_allows_negative_balance(db_session: Session) -> None:
    """Stock may go negative; higher-level services decide whether to block this."""
    product = _make_product(db_session)

    adjust_stock(db_session, product, -5, movement_type=MovementType.SALE)
    db_session.commit()

    assert get_stock(db_session, product.id) == Decimal("-5")


def test_adjust_stock_supports_decimal_quantities(db_session: Session) -> None:
    """Weight-priced items (rice, oil) must accept fractional deltas."""
    product = _make_product(db_session)

    adjust_stock(db_session, product, "10.500", movement_type=MovementType.PURCHASE)
    adjust_stock(db_session, product, "-2.250", movement_type=MovementType.SALE)
    db_session.commit()

    assert get_stock(db_session, product.id) == Decimal("8.250")


def test_adjust_stock_rejects_zero_delta(db_session: Session) -> None:
    product = _make_product(db_session)

    with pytest.raises(InvalidMovementError, match="zero"):
        adjust_stock(db_session, product, 0, movement_type=MovementType.ADJUSTMENT)


def test_adjust_stock_rejects_unknown_movement_type(db_session: Session) -> None:
    product = _make_product(db_session)

    with pytest.raises(InvalidMovementError, match="movement_type"):
        adjust_stock(db_session, product, 5, movement_type="hocus_pocus")


def test_adjust_stock_records_user_and_reference(db_session: Session) -> None:
    product = _make_product(db_session)

    movement = adjust_stock(
        db_session,
        product,
        -3,
        movement_type=MovementType.SALE,
        user_id="user-123",
        reference_id="sale-xyz",
        reference_type="sale",
        notes="  Counter sale  ",  # whitespace gets trimmed
    )
    db_session.commit()

    assert movement.user_id == "user-123"
    assert movement.reference_id == "sale-xyz"
    assert movement.reference_type == "sale"
    assert movement.notes == "Counter sale"


def test_adjust_stock_empty_notes_become_none(db_session: Session) -> None:
    product = _make_product(db_session)

    movement = adjust_stock(
        db_session,
        product,
        1,
        movement_type=MovementType.ADJUSTMENT,
        notes="   ",
    )
    db_session.commit()

    assert movement.notes is None


# --- record_initial_stock -----------------------------------------------------


def test_record_initial_stock_uses_initial_movement_type(db_session: Session) -> None:
    product = _make_product(db_session)

    movement = record_initial_stock(
        db_session, product, 200, user_id="admin-1", notes="Opening stock count"
    )
    db_session.commit()

    assert movement.movement_type == MovementType.INITIAL
    assert movement.quantity_delta == Decimal("200")
    assert get_stock(db_session, product.id) == Decimal("200")


# --- set_reorder_level --------------------------------------------------------


def test_set_reorder_level_creates_inventory_if_missing(db_session: Session) -> None:
    product = _make_product(db_session)

    inv = set_reorder_level(db_session, product, 10)
    db_session.commit()

    assert inv.reorder_level == Decimal("10")
    assert inv.quantity == Decimal("0")


def test_set_reorder_level_updates_existing(db_session: Session) -> None:
    product = _make_product(db_session)
    adjust_stock(db_session, product, 50, movement_type=MovementType.PURCHASE)
    set_reorder_level(db_session, product, 5)
    db_session.commit()

    inv = get_inventory(db_session, product.id)
    assert inv is not None
    assert inv.reorder_level == Decimal("5")
    assert inv.quantity == Decimal("50")  # quantity untouched


def test_set_reorder_level_rejects_negative(db_session: Session) -> None:
    product = _make_product(db_session)

    with pytest.raises(InvalidMovementError, match="reorder_level"):
        set_reorder_level(db_session, product, -1)


# --- low_stock_products -------------------------------------------------------


def test_low_stock_products_returns_items_at_or_below_threshold(
    db_session: Session,
) -> None:
    p1 = _make_product(db_session, barcode="L-1", name="Apple")
    p2 = _make_product(db_session, barcode="L-2", name="Banana")
    p3 = _make_product(db_session, barcode="L-3", name="Cucumber")

    set_reorder_level(db_session, p1, 10)
    set_reorder_level(db_session, p2, 10)
    set_reorder_level(db_session, p3, 10)
    adjust_stock(db_session, p1, 20, movement_type=MovementType.PURCHASE)  # plenty
    adjust_stock(db_session, p2, 10, movement_type=MovementType.PURCHASE)  # at threshold
    adjust_stock(db_session, p3, 3, movement_type=MovementType.PURCHASE)   # low
    db_session.commit()

    results = low_stock_products(db_session)
    names = {product.name for product, _ in results}

    assert names == {"Banana", "Cucumber"}


def test_low_stock_excludes_zero_threshold_by_default(db_session: Session) -> None:
    """Products without a configured reorder level shouldn't fire alerts by default."""
    product = _make_product(db_session)
    # Inventory exists but reorder_level remains 0.
    adjust_stock(db_session, product, 5, movement_type=MovementType.PURCHASE)
    db_session.commit()

    assert low_stock_products(db_session) == []
    assert len(low_stock_products(db_session, include_zero_threshold=True)) == 1


def test_low_stock_excludes_inactive_products(db_session: Session) -> None:
    product = _make_product(db_session)
    set_reorder_level(db_session, product, 10)
    adjust_stock(db_session, product, 1, movement_type=MovementType.PURCHASE)
    deactivate_product(db_session, product)
    db_session.commit()

    assert low_stock_products(db_session) == []


# --- list_movements / count_movements -----------------------------------------


def test_list_movements_orders_newest_first(db_session: Session) -> None:
    product = _make_product(db_session)
    for i in range(3):
        adjust_stock(
            db_session,
            product,
            10 + i,
            movement_type=MovementType.PURCHASE,
            notes=f"batch {i}",
        )
        db_session.commit()

    movements = list_movements(db_session, product_id=product.id)
    notes = [m.notes for m in movements]
    # Newest first means batch 2, batch 1, batch 0.
    assert notes == ["batch 2", "batch 1", "batch 0"]


def test_list_movements_filters_by_type(db_session: Session) -> None:
    product = _make_product(db_session)
    adjust_stock(db_session, product, 10, movement_type=MovementType.PURCHASE)
    adjust_stock(db_session, product, -2, movement_type=MovementType.SALE)
    adjust_stock(db_session, product, 1, movement_type=MovementType.RETURN)
    db_session.commit()

    sales = list_movements(
        db_session, product_id=product.id, movement_type=MovementType.SALE
    )
    assert len(sales) == 1
    assert sales[0].quantity_delta == Decimal("-2")


def test_count_movements(db_session: Session) -> None:
    p1 = _make_product(db_session, barcode="C-1")
    p2 = _make_product(db_session, barcode="C-2")
    adjust_stock(db_session, p1, 1, movement_type=MovementType.PURCHASE)
    adjust_stock(db_session, p1, -1, movement_type=MovementType.SALE)
    adjust_stock(db_session, p2, 1, movement_type=MovementType.PURCHASE)
    db_session.commit()

    assert count_movements(db_session) == 3
    assert count_movements(db_session, product_id=p1.id) == 2
    assert count_movements(db_session, movement_type=MovementType.SALE) == 1


def test_list_movements_pagination(db_session: Session) -> None:
    product = _make_product(db_session)
    for _ in range(7):
        adjust_stock(db_session, product, 1, movement_type=MovementType.PURCHASE)
    db_session.commit()

    page1 = list_movements(db_session, product_id=product.id, limit=3, offset=0)
    page2 = list_movements(db_session, product_id=product.id, limit=3, offset=3)
    page3 = list_movements(db_session, product_id=product.id, limit=3, offset=6)

    assert len(page1) == 3
    assert len(page2) == 3
    assert len(page3) == 1


def test_list_movements_rejects_invalid_pagination(db_session: Session) -> None:
    with pytest.raises(ValueError):
        list_movements(db_session, limit=0)
    with pytest.raises(ValueError):
        list_movements(db_session, offset=-1)
    with pytest.raises(ValueError):
        list_movements(db_session, limit=MAX_PAGE_SIZE + 1)


# --- Inventory <-> Product link -----------------------------------------------


def test_inventory_eagerly_loads_product(db_session: Session) -> None:
    product = _make_product(db_session, name="Eager Loaded")
    adjust_stock(db_session, product, 1, movement_type=MovementType.PURCHASE)
    db_session.commit()

    inv = db_session.scalar(
        select(Inventory).where(Inventory.product_id == product.id)
    )
    assert inv is not None
    assert inv.product.name == "Eager Loaded"

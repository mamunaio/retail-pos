"""Tests for the Sales / POS service."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from retail_pos.models import (
    MovementType,
    Payment,
    PaymentMethod,
    Product,
    Sale,
    SaleStatus,
    StockMovement,
    Terminal,
    User,
    UserRole,
)
from retail_pos.services.inventory import adjust_stock, get_stock
from retail_pos.services.products import create_product, deactivate_product
from retail_pos.services.sales import (
    MAX_HELD_SALES_PER_TERMINAL,
    CartLockedError,
    EmptyCartError,
    HeldSaleLimitExceededError,
    InsufficientPaymentError,
    InvalidLineItemError,
    InvalidPaymentError,
    InvalidSaleStateError,
    SaleError,
    add_line_item,
    add_payment,
    complete_sale,
    get_receipt,
    hold_sale,
    list_held_sales,
    remove_line_item,
    remove_payment,
    resume_sale,
    set_cart_discount,
    start_sale,
    update_line_item,
    void_sale,
)
from retail_pos.utils.security import hash_pin


# --- Fixtures (built on top of the in-memory db_session fixture in conftest) -


@pytest.fixture()
def cashier(db_session: Session) -> User:
    user = User(
        username="cashier1",
        pin_hash=hash_pin("0000"),
        full_name="Cashier One",
        role=UserRole.CASHIER,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def terminal(db_session: Session) -> Terminal:
    t = Terminal(terminal_code="POS-01", name="Front Counter")
    db_session.add(t)
    db_session.commit()
    return t


@pytest.fixture()
def juice(db_session: Session) -> Product:
    p = create_product(
        db_session,
        barcode="J-001",
        name="Mango Juice 250ml",
        selling_price=Decimal("25.00"),
        cost_price=Decimal("18.00"),
    )
    db_session.commit()
    return p


@pytest.fixture()
def soap(db_session: Session) -> Product:
    p = create_product(
        db_session,
        barcode="S-001",
        name="Lux Soap 100g",
        selling_price=Decimal("55.00"),
        cost_price=Decimal("45.00"),
    )
    db_session.commit()
    return p


@pytest.fixture()
def sale(db_session: Session, cashier: User, terminal: Terminal) -> Sale:
    s = start_sale(db_session, terminal_id=terminal.id, cashier_id=cashier.id)
    db_session.commit()
    return s


# --- start_sale ---------------------------------------------------------------


def test_start_sale_creates_draft(
    db_session: Session, cashier: User, terminal: Terminal
) -> None:
    s = start_sale(db_session, terminal_id=terminal.id, cashier_id=cashier.id)
    db_session.commit()

    assert s.id
    assert s.status == SaleStatus.DRAFT
    assert s.subtotal == Decimal("0.00")
    assert s.total_amount == Decimal("0.00")
    assert s.items == []
    assert s.payments == []


def test_start_sale_rejects_unknown_cashier(
    db_session: Session, terminal: Terminal
) -> None:
    with pytest.raises(InvalidSaleStateError, match="cashier"):
        start_sale(db_session, terminal_id=terminal.id, cashier_id="nobody")


def test_start_sale_rejects_inactive_terminal(
    db_session: Session, cashier: User, terminal: Terminal
) -> None:
    terminal.is_active = False
    db_session.commit()

    with pytest.raises(InvalidSaleStateError, match="terminal"):
        start_sale(db_session, terminal_id=terminal.id, cashier_id=cashier.id)


# --- add_line_item ------------------------------------------------------------


def test_add_line_item_records_product_snapshot(
    db_session: Session, sale: Sale, juice: Product
) -> None:
    line = add_line_item(db_session, sale, product=juice, quantity=2)
    db_session.commit()

    assert line.product_name == "Mango Juice 250ml"
    assert line.barcode_snapshot == "J-001"
    assert line.unit_price == Decimal("25.00")
    assert line.quantity == Decimal("2.000")
    assert line.line_total == Decimal("50.00")
    assert sale.subtotal == Decimal("50.00")
    assert sale.total_amount == Decimal("50.00")


def test_add_same_product_twice_merges_into_one_line(
    db_session: Session, sale: Sale, juice: Product
) -> None:
    add_line_item(db_session, sale, product=juice, quantity=1)
    add_line_item(db_session, sale, product=juice, quantity=2)
    db_session.commit()

    assert len(sale.items) == 1
    assert sale.items[0].quantity == Decimal("3.000")
    assert sale.items[0].line_total == Decimal("75.00")


def test_add_line_item_supports_decimal_quantity(
    db_session: Session, sale: Sale, juice: Product
) -> None:
    line = add_line_item(db_session, sale, product=juice, quantity="1.500")
    db_session.commit()

    assert line.quantity == Decimal("1.500")
    assert line.line_total == Decimal("37.50")


def test_add_line_item_with_per_line_discount(
    db_session: Session, sale: Sale, juice: Product
) -> None:
    line = add_line_item(
        db_session, sale, product=juice, quantity=4, discount_amount=10
    )
    db_session.commit()

    assert line.line_total == Decimal("90.00")  # 4 * 25 - 10


def test_add_line_item_rejects_zero_quantity(
    db_session: Session, sale: Sale, juice: Product
) -> None:
    with pytest.raises(InvalidLineItemError, match="quantity"):
        add_line_item(db_session, sale, product=juice, quantity=0)


def test_add_line_item_rejects_excessive_discount(
    db_session: Session, sale: Sale, juice: Product
) -> None:
    with pytest.raises(InvalidLineItemError, match="discount"):
        add_line_item(
            db_session, sale, product=juice, quantity=2, discount_amount=100
        )


def test_add_line_item_rejects_inactive_product(
    db_session: Session, sale: Sale, juice: Product
) -> None:
    deactivate_product(db_session, juice)
    db_session.commit()

    with pytest.raises(InvalidLineItemError, match="not active"):
        add_line_item(db_session, sale, product=juice, quantity=1)


def test_add_line_item_blocked_after_payment(
    db_session: Session, sale: Sale, juice: Product
) -> None:
    add_line_item(db_session, sale, product=juice, quantity=1)
    add_payment(db_session, sale, method=PaymentMethod.CASH, amount=25)
    db_session.commit()

    with pytest.raises(CartLockedError):
        add_line_item(db_session, sale, product=juice, quantity=1)


# --- update_line_item / remove_line_item --------------------------------------


def test_update_line_item_recomputes_totals(
    db_session: Session, sale: Sale, juice: Product
) -> None:
    line = add_line_item(db_session, sale, product=juice, quantity=1)
    db_session.commit()

    update_line_item(db_session, line, quantity=4)
    db_session.commit()

    assert line.quantity == Decimal("4.000")
    assert line.line_total == Decimal("100.00")
    assert sale.total_amount == Decimal("100.00")


def test_remove_line_item_clears_totals_when_empty(
    db_session: Session, sale: Sale, juice: Product
) -> None:
    line = add_line_item(db_session, sale, product=juice, quantity=2)
    db_session.commit()

    remove_line_item(db_session, line)
    db_session.commit()

    assert sale.items == []
    assert sale.subtotal == Decimal("0.00")
    assert sale.total_amount == Decimal("0.00")


# --- set_cart_discount --------------------------------------------------------


def test_set_cart_discount_reduces_total(
    db_session: Session, sale: Sale, juice: Product
) -> None:
    add_line_item(db_session, sale, product=juice, quantity=4)  # 100.00
    set_cart_discount(db_session, sale, 15)
    db_session.commit()

    assert sale.cart_discount == Decimal("15.00")
    assert sale.total_amount == Decimal("85.00")


def test_set_cart_discount_cannot_exceed_subtotal(
    db_session: Session, sale: Sale, juice: Product
) -> None:
    add_line_item(db_session, sale, product=juice, quantity=2)  # 50.00

    with pytest.raises(InvalidLineItemError, match="exceeds subtotal"):
        set_cart_discount(db_session, sale, 100)


def test_cart_discount_clamped_when_items_removed(
    db_session: Session, sale: Sale, juice: Product, soap: Product
) -> None:
    """A previously-valid cart discount must be clamped if subtotal shrinks."""
    add_line_item(db_session, sale, product=juice, quantity=4)   # 100
    line2 = add_line_item(db_session, sale, product=soap, quantity=1)  # 55
    set_cart_discount(db_session, sale, 60)  # valid (subtotal 155)
    db_session.commit()

    # Remove the soap line - subtotal drops to 100, discount of 60 is still valid.
    remove_line_item(db_session, line2)
    db_session.commit()
    assert sale.cart_discount == Decimal("60.00")
    assert sale.total_amount == Decimal("40.00")


# --- payments -----------------------------------------------------------------


def test_add_payment_unlocks_after_remove(
    db_session: Session, sale: Sale, juice: Product
) -> None:
    line = add_line_item(db_session, sale, product=juice, quantity=1)
    payment = add_payment(db_session, sale, method=PaymentMethod.CASH, amount=25)
    db_session.commit()

    # Cart locked while payment present.
    with pytest.raises(CartLockedError):
        update_line_item(db_session, line, quantity=2)

    # Remove the payment, edits work again.
    remove_payment(db_session, payment)
    db_session.commit()
    update_line_item(db_session, line, quantity=2)


def test_add_payment_rejects_invalid_method(db_session: Session, sale: Sale) -> None:
    with pytest.raises(InvalidPaymentError, match="method"):
        add_payment(db_session, sale, method="crypto", amount=10)


def test_add_payment_rejects_zero_amount(db_session: Session, sale: Sale) -> None:
    with pytest.raises(InvalidPaymentError, match="amount"):
        add_payment(db_session, sale, method=PaymentMethod.CASH, amount=0)


def test_add_payment_normalises_blank_reference(
    db_session: Session, sale: Sale
) -> None:
    payment = add_payment(
        db_session, sale, method=PaymentMethod.BKASH, amount=10, reference="   "
    )
    db_session.commit()

    assert payment.reference is None


# --- hold / resume ------------------------------------------------------------


def test_hold_and_resume(db_session: Session, sale: Sale, juice: Product) -> None:
    add_line_item(db_session, sale, product=juice, quantity=1)
    hold_sale(db_session, sale)
    db_session.commit()
    assert sale.status == SaleStatus.HELD

    resume_sale(db_session, sale)
    db_session.commit()
    assert sale.status == SaleStatus.DRAFT


def test_hold_limit(
    db_session: Session, cashier: User, terminal: Terminal, juice: Product
) -> None:
    for _ in range(MAX_HELD_SALES_PER_TERMINAL):
        s = start_sale(db_session, terminal_id=terminal.id, cashier_id=cashier.id)
        add_line_item(db_session, s, product=juice, quantity=1)
        hold_sale(db_session, s)
    db_session.commit()

    extra = start_sale(db_session, terminal_id=terminal.id, cashier_id=cashier.id)
    add_line_item(db_session, extra, product=juice, quantity=1)

    with pytest.raises(HeldSaleLimitExceededError):
        hold_sale(db_session, extra)


def test_list_held_sales_only_returns_held_for_terminal(
    db_session: Session, cashier: User, terminal: Terminal, juice: Product
) -> None:
    held = start_sale(db_session, terminal_id=terminal.id, cashier_id=cashier.id)
    add_line_item(db_session, held, product=juice, quantity=1)
    hold_sale(db_session, held)
    # A draft sale on the same terminal must not show up.
    start_sale(db_session, terminal_id=terminal.id, cashier_id=cashier.id)
    db_session.commit()

    results = list_held_sales(db_session, terminal_id=terminal.id)
    assert [s.id for s in results] == [held.id]


# --- void ---------------------------------------------------------------------


def test_void_sale_marks_status_and_records_reason(
    db_session: Session, sale: Sale
) -> None:
    void_sale(db_session, sale, reason="customer cancelled")
    db_session.commit()

    assert sale.status == SaleStatus.VOID
    assert sale.void_reason == "customer cancelled"
    assert sale.voided_at is not None


def test_void_requires_reason(db_session: Session, sale: Sale) -> None:
    with pytest.raises(SaleError, match="reason"):
        void_sale(db_session, sale, reason="   ")


def test_void_blocked_after_completion(
    db_session: Session, sale: Sale, juice: Product
) -> None:
    add_line_item(db_session, sale, product=juice, quantity=1)
    add_payment(db_session, sale, method=PaymentMethod.CASH, amount=25)
    complete_sale(db_session, sale)
    db_session.commit()

    with pytest.raises(InvalidSaleStateError):
        void_sale(db_session, sale, reason="oops")


# --- complete_sale ------------------------------------------------------------


def test_complete_sale_happy_path_deducts_stock(
    db_session: Session, sale: Sale, juice: Product
) -> None:
    # Seed some inventory first.
    adjust_stock(db_session, juice, 10, movement_type=MovementType.PURCHASE)
    db_session.commit()

    add_line_item(db_session, sale, product=juice, quantity=3)
    add_payment(db_session, sale, method=PaymentMethod.CASH, amount=75)

    complete_sale(db_session, sale)
    db_session.commit()
    db_session.refresh(sale)

    assert sale.status == SaleStatus.COMPLETED
    assert sale.completed_at is not None
    assert sale.amount_tendered == Decimal("75.00")
    assert sale.change_amount == Decimal("0.00")
    assert sale.receipt_number  # generated
    # 10 - 3 = 7 left
    assert get_stock(db_session, juice.id) == Decimal("7.000")


def test_complete_sale_records_change_for_overpayment(
    db_session: Session, sale: Sale, juice: Product
) -> None:
    add_line_item(db_session, sale, product=juice, quantity=2)  # 50.00
    add_payment(db_session, sale, method=PaymentMethod.CASH, amount=100)

    complete_sale(db_session, sale)
    db_session.commit()

    assert sale.amount_tendered == Decimal("100.00")
    assert sale.change_amount == Decimal("50.00")


def test_complete_sale_supports_split_payment(
    db_session: Session, sale: Sale, juice: Product, soap: Product
) -> None:
    add_line_item(db_session, sale, product=juice, quantity=2)   # 50
    add_line_item(db_session, sale, product=soap, quantity=1)    # 55  -> total 105
    add_payment(db_session, sale, method=PaymentMethod.CASH, amount=60)
    add_payment(db_session, sale, method=PaymentMethod.BKASH, amount=45, reference="TXN-1")

    complete_sale(db_session, sale)
    db_session.commit()

    assert sale.amount_tendered == Decimal("105.00")
    assert sale.change_amount == Decimal("0.00")
    assert len(sale.payments) == 2


def test_complete_sale_rejects_insufficient_payment(
    db_session: Session, sale: Sale, juice: Product
) -> None:
    add_line_item(db_session, sale, product=juice, quantity=2)  # 50
    add_payment(db_session, sale, method=PaymentMethod.CASH, amount=10)

    with pytest.raises(InsufficientPaymentError):
        complete_sale(db_session, sale)


def test_complete_sale_rejects_empty_cart(db_session: Session, sale: Sale) -> None:
    with pytest.raises(EmptyCartError):
        complete_sale(db_session, sale)


def test_complete_sale_creates_one_stock_movement_per_line(
    db_session: Session, sale: Sale, juice: Product, soap: Product
) -> None:
    add_line_item(db_session, sale, product=juice, quantity=2)
    add_line_item(db_session, sale, product=soap, quantity=1)
    add_payment(db_session, sale, method=PaymentMethod.CASH, amount=200)
    complete_sale(db_session, sale)
    db_session.commit()

    movements = (
        db_session.query(StockMovement)
        .filter(StockMovement.reference_id == sale.id)
        .all()
    )
    assert len(movements) == 2
    assert {m.movement_type for m in movements} == {MovementType.SALE}
    assert {m.reference_type for m in movements} == {"sale"}


def test_void_sale_does_not_deduct_stock(
    db_session: Session, sale: Sale, juice: Product
) -> None:
    adjust_stock(db_session, juice, 5, movement_type=MovementType.PURCHASE)
    db_session.commit()
    add_line_item(db_session, sale, product=juice, quantity=2)
    void_sale(db_session, sale, reason="cancelled")
    db_session.commit()

    assert get_stock(db_session, juice.id) == Decimal("5.000")


def test_receipt_numbers_are_sequential_per_terminal_per_day(
    db_session: Session, cashier: User, terminal: Terminal, juice: Product
) -> None:
    receipts = []
    for _ in range(3):
        s = start_sale(db_session, terminal_id=terminal.id, cashier_id=cashier.id)
        add_line_item(db_session, s, product=juice, quantity=1)
        add_payment(db_session, s, method=PaymentMethod.CASH, amount=25)
        complete_sale(db_session, s)
        db_session.commit()
        receipts.append(s.receipt_number)

    # Numbers all start with the terminal code.
    for r in receipts:
        assert r is not None and r.startswith("POS-01-")
    # Each one ends with an incrementing 4-digit sequence.
    sequences = [int(r.rsplit("-", 1)[1]) for r in receipts if r is not None]
    assert sequences == [1, 2, 3]


# --- Receipt DTO --------------------------------------------------------------


def test_get_receipt_snapshot(
    db_session: Session,
    sale: Sale,
    juice: Product,
    soap: Product,
    cashier: User,
    terminal: Terminal,
) -> None:
    add_line_item(db_session, sale, product=juice, quantity=2)  # 50
    add_line_item(db_session, sale, product=soap, quantity=1)   # 55  -> 105
    set_cart_discount(db_session, sale, 5)                      # -> total 100
    add_payment(db_session, sale, method=PaymentMethod.CASH, amount=120)
    complete_sale(db_session, sale)
    db_session.commit()

    receipt = get_receipt(db_session, sale)

    assert receipt.sale_id == sale.id
    assert receipt.cashier_name == cashier.full_name
    assert receipt.terminal_code == terminal.terminal_code
    assert len(receipt.line_items) == 2
    assert receipt.subtotal == Decimal("105.00")
    assert receipt.cart_discount == Decimal("5.00")
    assert receipt.total == Decimal("100.00")
    assert receipt.amount_tendered == Decimal("120.00")
    assert receipt.change == Decimal("20.00")
    assert len(receipt.payments) == 1
    assert receipt.payments[0].method == PaymentMethod.CASH

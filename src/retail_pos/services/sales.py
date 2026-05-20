"""Sales / POS service: cart state machine, payments, receipts.

A sale moves through these states:

    DRAFT  --hold--> HELD  --resume--> DRAFT
    DRAFT  --void--> VOID
    HELD   --void--> VOID
    DRAFT  --complete--> COMPLETED   (deducts stock, freezes the sale)

Cart edits (line items, cart discount) are only allowed in DRAFT and only
when no payments have been recorded yet. Once any payment is added, the
cart is implicitly locked - the cashier must remove the payment to make
further changes. This avoids the need for an explicit "completing" state
while still preventing item edits during checkout.

Public API:
    start_sale(db, *, terminal_id, cashier_id, customer_id=None) -> Sale
    add_line_item(db, sale, *, product, quantity, discount_amount=0) -> SaleItem
    update_line_item(db, line, *, quantity=..., discount_amount=...) -> SaleItem
    remove_line_item(db, line) -> None
    set_cart_discount(db, sale, amount) -> Sale
    add_payment(db, sale, *, method, amount, reference=None) -> Payment
    remove_payment(db, payment) -> None
    hold_sale(db, sale) -> Sale
    resume_sale(db, sale) -> Sale
    list_held_sales(db, *, terminal_id, limit=50, offset=0) -> list[Sale]
    void_sale(db, sale, *, reason) -> Sale
    complete_sale(db, sale) -> Sale
    get_receipt(db, sale) -> SaleReceipt
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Final

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from retail_pos.models.payment import Payment, PaymentMethod
from retail_pos.models.product import Product
from retail_pos.models.sale import Sale, SaleStatus
from retail_pos.models.sale_item import SaleItem
from retail_pos.models.stock_movement import MovementType
from retail_pos.models.terminal import Terminal
from retail_pos.models.user import User
from retail_pos.services.inventory import adjust_stock

# --- Constants ----------------------------------------------------------------

DEFAULT_PAGE_SIZE: Final[int] = 50
MAX_PAGE_SIZE: Final[int] = 500
MAX_HELD_SALES_PER_TERMINAL: Final[int] = 5
ZERO: Final[Decimal] = Decimal("0.00")


# --- Exceptions ---------------------------------------------------------------


class SaleError(Exception):
    """Base class for Sales-service errors."""


class InvalidSaleStateError(SaleError):
    """Operation not permitted in the sale's current status."""


class CartLockedError(SaleError):
    """Cart cannot be modified because the sale already has payments recorded."""


class EmptyCartError(SaleError):
    """Cannot complete a sale with no line items."""


class InsufficientPaymentError(SaleError):
    """Total payments do not cover the sale total."""


class HeldSaleLimitExceededError(SaleError):
    """Terminal already has the maximum number of held sales."""


class InvalidLineItemError(SaleError):
    """A line item value (quantity, discount) failed validation."""


class InvalidPaymentError(SaleError):
    """A payment amount or method failed validation."""


# --- Receipt DTO --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReceiptLine:
    """One line as it should appear on a printed receipt."""

    product_name: str
    barcode: str
    unit: str
    quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    line_total: Decimal


@dataclass(frozen=True, slots=True)
class ReceiptPayment:
    """One tender breakdown line on a receipt."""

    method: str
    amount: Decimal
    reference: str | None


@dataclass(frozen=True, slots=True)
class SaleReceipt:
    """An immutable, UI-printable snapshot of a completed sale.

    Returned by :func:`complete_sale` and :func:`get_receipt`. The DTO is
    decoupled from the ORM rows so the printer / receipt cache can hold it
    without keeping a database session alive.
    """

    sale_id: str
    receipt_number: str | None
    completed_at: datetime | None
    cashier_name: str
    terminal_code: str
    customer_id: str | None
    line_items: tuple[ReceiptLine, ...]
    subtotal: Decimal
    cart_discount: Decimal
    total: Decimal
    payments: tuple[ReceiptPayment, ...]
    amount_tendered: Decimal
    change: Decimal


# --- Helpers ------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _to_decimal(value: Decimal | int | float | str, *, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (ValueError, ArithmeticError) as exc:
        raise InvalidLineItemError(f"{field} is not a valid number") from exc


def _money(value: Decimal | int | float | str, *, field: str) -> Decimal:
    """Normalise to a money Decimal (2 places, non-negative)."""
    amount = _to_decimal(value, field=field)
    if amount < 0:
        raise InvalidLineItemError(f"{field} must not be negative")
    # Quantize to 2 dp to avoid surprises like 0.1 + 0.2 != 0.3 in totals.
    return amount.quantize(Decimal("0.01"))


def _quantity(value: Decimal | int | float | str) -> Decimal:
    qty = _to_decimal(value, field="quantity")
    if qty <= 0:
        raise InvalidLineItemError("quantity must be greater than zero")
    return qty.quantize(Decimal("0.001"))


def _validate_payment_method(method: str) -> str:
    valid = {m.value for m in PaymentMethod}
    if method not in valid:
        raise InvalidPaymentError(
            f"method must be one of {sorted(valid)}, got {method!r}"
        )
    return method


def _require_status(sale: Sale, *expected: str) -> None:
    if sale.status not in expected:
        raise InvalidSaleStateError(
            f"operation requires status in {sorted(expected)}, current={sale.status!r}"
        )


def _require_cart_unlocked(sale: Sale) -> None:
    """Block cart edits once a payment has been recorded."""
    if sale.payments:
        raise CartLockedError(
            "cart is locked because the sale has recorded payments; "
            "remove the payments first"
        )


def _calc_line_total(unit_price: Decimal, quantity: Decimal, discount: Decimal) -> Decimal:
    """Compute ``(unit_price * quantity) - discount``, clamped to >= 0."""
    gross = (unit_price * quantity).quantize(Decimal("0.01"))
    line_total = (gross - discount).quantize(Decimal("0.01"))
    if line_total < 0:
        raise InvalidLineItemError(
            "discount_amount must not exceed unit_price * quantity"
        )
    return line_total


def _recalc_sale_totals(sale: Sale) -> None:
    """Refresh ``subtotal`` and ``total_amount`` from the current line items."""
    subtotal = sum((item.line_total for item in sale.items), ZERO)
    sale.subtotal = subtotal.quantize(Decimal("0.01"))
    if sale.cart_discount > sale.subtotal:
        # If a previous cart discount no longer fits the (smaller) subtotal,
        # clamp it down rather than leave the sale with negative total.
        sale.cart_discount = sale.subtotal
    sale.total_amount = (sale.subtotal - sale.cart_discount).quantize(Decimal("0.01"))
    sale.synced = False


def _amount_paid(sale: Sale) -> Decimal:
    return sum((p.amount for p in sale.payments), ZERO).quantize(Decimal("0.01"))


# --- Receipt number generation ------------------------------------------------


def _generate_receipt_number(db: Session, terminal: Terminal, when: datetime) -> str:
    """Build a daily-sequenced receipt number per terminal.

    Format: ``{terminal_code}-{YYYYMMDD}-{NNNN}``. Sequence is 1-based and
    counts the existing COMPLETED sales for this terminal on this date.
    """
    day: date = when.astimezone(UTC).date()
    day_start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    day_end = datetime(day.year, day.month, day.day, 23, 59, 59, 999999, tzinfo=UTC)

    existing = (
        db.scalar(
            select(func.count(Sale.id)).where(
                and_(
                    Sale.terminal_id == terminal.id,
                    Sale.status == SaleStatus.COMPLETED,
                    Sale.completed_at >= day_start,
                    Sale.completed_at <= day_end,
                )
            )
        )
        or 0
    )
    sequence = existing + 1
    return f"{terminal.terminal_code}-{day:%Y%m%d}-{sequence:04d}"


# --- Public API: create / cart -----------------------------------------------


def start_sale(
    db: Session,
    *,
    terminal_id: str,
    cashier_id: str,
    customer_id: str | None = None,
) -> Sale:
    """Create a new DRAFT sale on the given terminal.

    Validates that ``terminal_id`` and ``cashier_id`` reference real, active
    rows. Inactive cashiers / terminals cannot start sales.
    """
    terminal = db.get(Terminal, terminal_id)
    if terminal is None or not terminal.is_active:
        raise InvalidSaleStateError(f"unknown or inactive terminal: {terminal_id!r}")
    cashier = db.get(User, cashier_id)
    if cashier is None or not cashier.is_active:
        raise InvalidSaleStateError(f"unknown or inactive cashier: {cashier_id!r}")

    sale = Sale(
        terminal_id=terminal_id,
        cashier_id=cashier_id,
        customer_id=customer_id,
        status=SaleStatus.DRAFT,
    )
    db.add(sale)
    db.flush()
    return sale


def add_line_item(
    db: Session,
    sale: Sale,
    *,
    product: Product,
    quantity: Decimal | int | float | str = 1,
    discount_amount: Decimal | int | float | str = 0,
) -> SaleItem:
    """Add a product to the cart (or increment an existing line of the same product).

    Adding the same product twice merges quantities into one line; this is
    what cashiers expect when scanning a barcode multiple times.

    Raises:
        InvalidSaleStateError: sale is not in DRAFT.
        CartLockedError: payments already recorded on this sale.
        InvalidLineItemError: product inactive, bad quantity, or discount too high.
    """
    _require_status(sale, SaleStatus.DRAFT)
    _require_cart_unlocked(sale)
    if not product.is_active:
        raise InvalidLineItemError(
            f"product {product.barcode!r} is not active and cannot be sold"
        )

    qty = _quantity(quantity)
    discount = _money(discount_amount, field="discount_amount")

    # Merge into an existing line if the same product is already on the cart.
    existing = next((it for it in sale.items if it.product_id == product.id), None)
    if existing is not None:
        new_quantity = (existing.quantity + qty).quantize(Decimal("0.001"))
        new_discount = (existing.discount_amount + discount).quantize(Decimal("0.01"))
        existing.quantity = new_quantity
        existing.discount_amount = new_discount
        existing.line_total = _calc_line_total(
            existing.unit_price, new_quantity, new_discount
        )
        existing.synced = False
        _recalc_sale_totals(sale)
        db.flush()
        return existing

    line_total = _calc_line_total(product.selling_price, qty, discount)
    item = SaleItem(
        sale_id=sale.id,
        product_id=product.id,
        product_name=product.name,
        barcode_snapshot=product.barcode,
        unit=product.unit,
        unit_price=product.selling_price,
        tax_rate=product.tax_rate,
        quantity=qty,
        discount_amount=discount,
        line_total=line_total,
    )
    db.add(item)
    sale.items.append(item)
    _recalc_sale_totals(sale)
    db.flush()
    return item


_UNSET: Final = object()


def update_line_item(
    db: Session,
    line: SaleItem,
    *,
    quantity: object = _UNSET,
    discount_amount: object = _UNSET,
) -> SaleItem:
    """Change quantity and/or discount on an existing cart line.

    Either argument may be omitted; only the provided ones change.
    """
    sale = line.sale
    _require_status(sale, SaleStatus.DRAFT)
    _require_cart_unlocked(sale)

    if quantity is not _UNSET:
        line.quantity = _quantity(quantity)  # type: ignore[arg-type]
    if discount_amount is not _UNSET:
        line.discount_amount = _money(
            discount_amount, field="discount_amount"  # type: ignore[arg-type]
        )

    line.line_total = _calc_line_total(
        line.unit_price, line.quantity, line.discount_amount
    )
    line.synced = False
    _recalc_sale_totals(sale)
    db.flush()
    return line


def remove_line_item(db: Session, line: SaleItem) -> None:
    """Delete a cart line entirely."""
    sale = line.sale
    _require_status(sale, SaleStatus.DRAFT)
    _require_cart_unlocked(sale)

    sale.items.remove(line)
    db.delete(line)
    _recalc_sale_totals(sale)
    db.flush()


def set_cart_discount(
    db: Session, sale: Sale, amount: Decimal | int | float | str
) -> Sale:
    """Set a flat-amount discount on the whole cart.

    The discount cannot exceed the subtotal (after line discounts).
    """
    _require_status(sale, SaleStatus.DRAFT)
    _require_cart_unlocked(sale)

    discount = _money(amount, field="cart_discount")
    if discount > sale.subtotal:
        raise InvalidLineItemError(
            f"cart_discount {discount} exceeds subtotal {sale.subtotal}"
        )
    sale.cart_discount = discount
    _recalc_sale_totals(sale)
    db.flush()
    return sale


# --- Public API: payments -----------------------------------------------------


def add_payment(
    db: Session,
    sale: Sale,
    *,
    method: str,
    amount: Decimal | int | float | str,
    reference: str | None = None,
) -> Payment:
    """Record a tender (cash, card, MFS) against a sale.

    Multiple payments are allowed for split tender. The cart becomes locked
    against item edits as soon as the first payment is recorded.
    """
    _require_status(sale, SaleStatus.DRAFT)
    method = _validate_payment_method(method)
    paid = _money(amount, field="amount")
    if paid <= 0:
        raise InvalidPaymentError("amount must be greater than zero")

    payment = Payment(
        sale_id=sale.id,
        method=method,
        amount=paid,
        reference=reference.strip() if isinstance(reference, str) and reference.strip() else None,
    )
    db.add(payment)
    sale.payments.append(payment)
    sale.synced = False
    db.flush()
    return payment


def remove_payment(db: Session, payment: Payment) -> None:
    """Remove a previously-recorded payment.

    Useful when the cashier mis-keys an amount and needs to redo it. After
    removing the last payment, item edits become possible again.
    """
    sale = payment.sale
    _require_status(sale, SaleStatus.DRAFT)

    sale.payments.remove(payment)
    db.delete(payment)
    sale.synced = False
    db.flush()


# --- Public API: hold / resume / void / complete -----------------------------


def hold_sale(db: Session, sale: Sale) -> Sale:
    """Pause a DRAFT sale so the cashier can serve another customer.

    Refuses if the terminal already has the maximum number of held sales -
    this prevents stale carts from accumulating.
    """
    _require_status(sale, SaleStatus.DRAFT)

    held_count = db.scalar(
        select(func.count(Sale.id)).where(
            and_(
                Sale.terminal_id == sale.terminal_id,
                Sale.status == SaleStatus.HELD,
            )
        )
    ) or 0
    if held_count >= MAX_HELD_SALES_PER_TERMINAL:
        raise HeldSaleLimitExceededError(
            f"terminal already has {MAX_HELD_SALES_PER_TERMINAL} held sales"
        )

    sale.status = SaleStatus.HELD
    sale.synced = False
    db.flush()
    return sale


def resume_sale(db: Session, sale: Sale) -> Sale:
    """Bring a HELD sale back into DRAFT for further editing."""
    _require_status(sale, SaleStatus.HELD)
    sale.status = SaleStatus.DRAFT
    sale.synced = False
    db.flush()
    return sale


def list_held_sales(
    db: Session,
    *,
    terminal_id: str,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> list[Sale]:
    """Return held sales for a terminal, oldest first (FIFO is more natural)."""
    if limit <= 0 or offset < 0 or limit > MAX_PAGE_SIZE:
        raise ValueError("invalid pagination parameters")
    stmt = (
        select(Sale)
        .where(Sale.terminal_id == terminal_id)
        .where(Sale.status == SaleStatus.HELD)
        .order_by(Sale.created_at)
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))


def void_sale(db: Session, sale: Sale, *, reason: str) -> Sale:
    """Cancel a sale that hasn't been completed.

    A short reason (e.g. "customer cancelled", "duplicate") is required for
    the audit trail.
    """
    _require_status(sale, SaleStatus.DRAFT, SaleStatus.HELD)
    cleaned_reason = reason.strip() if isinstance(reason, str) else ""
    if not cleaned_reason:
        raise SaleError("reason is required when voiding a sale")

    sale.status = SaleStatus.VOID
    sale.void_reason = cleaned_reason[:200]
    sale.voided_at = _utcnow()
    sale.synced = False
    db.flush()
    return sale


def complete_sale(db: Session, sale: Sale) -> Sale:
    """Finalize a sale: deduct stock, assign a receipt number, mark COMPLETED.

    Preconditions:
      * sale is in DRAFT
      * at least one line item exists
      * sum of payment amounts >= total_amount

    Side effects (all in the caller's transaction):
      * For every line item, a SALE-type stock movement is recorded with
        ``reference_id = sale.id`` so inventory is decremented and audited.
      * The sale's ``status``, ``receipt_number``, ``completed_at``,
        ``amount_tendered``, and ``change_amount`` are populated.
    """
    _require_status(sale, SaleStatus.DRAFT)
    if not sale.items:
        raise EmptyCartError("cannot complete a sale with no line items")

    paid = _amount_paid(sale)
    if paid < sale.total_amount:
        raise InsufficientPaymentError(
            f"payments {paid} do not cover total {sale.total_amount}"
        )

    now = _utcnow()
    terminal = db.get(Terminal, sale.terminal_id)
    if terminal is None:
        # Should be unreachable thanks to FK, but guard anyway.
        raise InvalidSaleStateError("sale's terminal no longer exists")

    # Deduct stock for each line. We re-fetch the Product to ensure the FK
    # target still exists; the StockMovement carries the sale id as a
    # reference so inventory reports can join back to receipts.
    for line in sale.items:
        product = db.get(Product, line.product_id)
        if product is None:
            raise InvalidSaleStateError(
                f"product {line.product_id!r} no longer exists"
            )
        adjust_stock(
            db,
            product,
            -line.quantity,  # outflow
            movement_type=MovementType.SALE,
            user_id=sale.cashier_id,
            reference_id=sale.id,
            reference_type="sale",
            notes=f"Sale {line.product_name}",
        )

    sale.amount_tendered = paid
    sale.change_amount = (paid - sale.total_amount).quantize(Decimal("0.01"))
    sale.completed_at = now
    sale.receipt_number = _generate_receipt_number(db, terminal, now)
    sale.status = SaleStatus.COMPLETED
    sale.synced = False
    db.flush()
    return sale


# --- Public API: receipt ------------------------------------------------------


def get_receipt(db: Session, sale: Sale) -> SaleReceipt:
    """Build an immutable receipt DTO from any sale (typically COMPLETED).

    Reused for both the initial print and any later re-print.
    """
    cashier = db.get(User, sale.cashier_id)
    terminal = db.get(Terminal, sale.terminal_id)

    lines = tuple(
        ReceiptLine(
            product_name=item.product_name,
            barcode=item.barcode_snapshot,
            unit=item.unit,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_amount=item.discount_amount,
            line_total=item.line_total,
        )
        for item in sale.items
    )
    payments = tuple(
        ReceiptPayment(method=p.method, amount=p.amount, reference=p.reference)
        for p in sale.payments
    )
    return SaleReceipt(
        sale_id=sale.id,
        receipt_number=sale.receipt_number,
        completed_at=sale.completed_at,
        cashier_name=cashier.full_name if cashier is not None else "(unknown)",
        terminal_code=terminal.terminal_code if terminal is not None else "(unknown)",
        customer_id=sale.customer_id,
        line_items=lines,
        subtotal=sale.subtotal,
        cart_discount=sale.cart_discount,
        total=sale.total_amount,
        payments=payments,
        amount_tendered=sale.amount_tendered,
        change=sale.change_amount,
    )

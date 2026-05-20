"""Inventory service: stock-on-hand snapshot + immutable movement audit log.

Every stock change goes through :func:`adjust_stock`, which atomically:
  1. inserts a :class:`StockMovement` row recording why the change happened, and
  2. updates the :class:`Inventory` row that holds the running total.

If a product has no inventory row yet, the first call creates it. The running
sum of every product's :class:`StockMovement.quantity_delta` therefore always
reconciles to its :class:`Inventory.quantity` (this invariant is exercised by
the test suite).

Public API:
    get_stock(db, product_id) -> Decimal
    get_inventory(db, product_id) -> Inventory | None
    set_reorder_level(db, product, level) -> Inventory
    adjust_stock(db, product, delta, *, movement_type, ...) -> StockMovement
    record_initial_stock(db, product, quantity, *, user_id, notes) -> StockMovement
    low_stock_products(db) -> list[tuple[Product, Inventory]]
    list_movements(db, *, product_id, movement_type, limit, offset) -> list[StockMovement]
    count_movements(db, *, product_id, movement_type) -> int
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from retail_pos.models.inventory import Inventory
from retail_pos.models.product import Product
from retail_pos.models.stock_movement import MovementType, StockMovement

# --- Constants ----------------------------------------------------------------

DEFAULT_PAGE_SIZE: Final[int] = 50
MAX_PAGE_SIZE: Final[int] = 500
MAX_NOTES_LENGTH: Final[int] = 500


# --- Exceptions ---------------------------------------------------------------


class InventoryError(Exception):
    """Base class for inventory-service errors."""


class InvalidMovementError(InventoryError):
    """Raised when a stock-change request is malformed."""


# --- Validation helpers -------------------------------------------------------


def _to_decimal(value: Decimal | int | float | str, *, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (ValueError, ArithmeticError) as exc:
        raise InvalidMovementError(f"{field} is not a valid number") from exc


def _validate_movement_type(value: str) -> str:
    valid = {m.value for m in MovementType}
    if value not in valid:
        raise InvalidMovementError(
            f"movement_type must be one of {sorted(valid)}, got {value!r}"
        )
    return value


def _normalise_notes(notes: str | None) -> str | None:
    if notes is None:
        return None
    if not isinstance(notes, str):
        raise InvalidMovementError("notes must be a string or None")
    stripped = notes.strip()
    if not stripped:
        return None
    if len(stripped) > MAX_NOTES_LENGTH:
        raise InvalidMovementError(
            f"notes must be at most {MAX_NOTES_LENGTH} characters"
        )
    return stripped


def _validate_page(limit: int, offset: int) -> tuple[int, int]:
    if limit <= 0:
        raise ValueError("limit must be positive")
    if offset < 0:
        raise ValueError("offset must not be negative")
    if limit > MAX_PAGE_SIZE:
        raise ValueError(f"limit must be at most {MAX_PAGE_SIZE}")
    return limit, offset


# --- Internal: ensure an inventory row exists --------------------------------


def _get_or_create_inventory(db: Session, product: Product) -> Inventory:
    """Fetch the inventory row for ``product``, creating an empty one if missing."""
    inventory = db.scalar(
        select(Inventory).where(Inventory.product_id == product.id)
    )
    if inventory is None:
        inventory = Inventory(
            product_id=product.id,
            quantity=Decimal("0.000"),
            reorder_level=Decimal("0.000"),
        )
        db.add(inventory)
        db.flush()  # populate id and make it queryable in this session
    return inventory


# --- Public read API ----------------------------------------------------------


def get_inventory(db: Session, product_id: str) -> Inventory | None:
    """Return the inventory row for ``product_id`` or ``None`` if there isn't one."""
    return db.scalar(select(Inventory).where(Inventory.product_id == product_id))


def get_stock(db: Session, product_id: str) -> Decimal:
    """Return the current stock-on-hand for ``product_id`` (``0`` if no row)."""
    inventory = get_inventory(db, product_id)
    return inventory.quantity if inventory is not None else Decimal("0.000")


# --- Public write API ---------------------------------------------------------


def set_reorder_level(
    db: Session, product: Product, level: Decimal | int | float | str
) -> Inventory:
    """Set the low-stock alert threshold for ``product``.

    Raises:
        InvalidMovementError: ``level`` is negative or unparseable.
    """
    amount = _to_decimal(level, field="reorder_level")
    if amount < 0:
        raise InvalidMovementError("reorder_level must not be negative")

    inventory = _get_or_create_inventory(db, product)
    inventory.reorder_level = amount
    inventory.synced = False
    db.flush()
    return inventory


def adjust_stock(
    db: Session,
    product: Product,
    delta: Decimal | int | float | str,
    *,
    movement_type: str,
    user_id: str | None = None,
    reference_id: str | None = None,
    reference_type: str | None = None,
    notes: str | None = None,
) -> StockMovement:
    """Apply a signed change to ``product``'s stock and record an audit row.

    ``delta`` is signed: positive adds to stock, negative removes. The
    function does **not** prevent stock from going negative — that policy
    belongs to higher-level services (e.g. Sales) which can choose to allow
    or block the operation depending on configuration.

    Both the inventory update and the movement insert happen via
    ``session.flush()`` inside the caller's transaction, so they succeed or
    fail together.

    Raises:
        InvalidMovementError: ``delta`` is zero, ``movement_type`` is unknown,
            or ``notes`` is malformed.
    """
    movement_type = _validate_movement_type(movement_type)
    notes = _normalise_notes(notes)

    delta_amount = _to_decimal(delta, field="delta")
    if delta_amount == 0:
        raise InvalidMovementError("delta must not be zero")

    inventory = _get_or_create_inventory(db, product)
    inventory.quantity = inventory.quantity + delta_amount
    inventory.synced = False

    movement = StockMovement(
        product_id=product.id,
        movement_type=movement_type,
        quantity_delta=delta_amount,
        reference_id=reference_id,
        reference_type=reference_type,
        notes=notes,
        user_id=user_id,
    )
    db.add(movement)
    db.flush()
    return movement


def record_initial_stock(
    db: Session,
    product: Product,
    quantity: Decimal | int | float | str,
    *,
    user_id: str | None = None,
    notes: str | None = None,
) -> StockMovement:
    """Convenience wrapper for the very first stock entry on a new product.

    Equivalent to :func:`adjust_stock` with ``movement_type="initial"``. Use
    this when migrating existing inventory from another system or doing the
    opening stock count at shop launch.
    """
    return adjust_stock(
        db,
        product,
        quantity,
        movement_type=MovementType.INITIAL,
        user_id=user_id,
        notes=notes,
    )


# --- Reports ------------------------------------------------------------------


def low_stock_products(
    db: Session, *, include_zero_threshold: bool = False
) -> list[tuple[Product, Inventory]]:
    """Return ``(product, inventory)`` pairs whose stock is at or below the reorder level.

    By default rows where ``reorder_level == 0`` are excluded — those products
    haven't been configured for low-stock alerts and would otherwise drown
    out the signal. Pass ``include_zero_threshold=True`` to include them
    (useful for "show me everything that's out of stock").
    """
    stmt = (
        select(Product, Inventory)
        .join(Inventory, Inventory.product_id == Product.id)
        .where(Inventory.quantity <= Inventory.reorder_level)
        .where(Product.is_active.is_(True))
    )
    if not include_zero_threshold:
        stmt = stmt.where(Inventory.reorder_level > 0)
    stmt = stmt.order_by(Product.name)
    return [(product, inventory) for product, inventory in db.execute(stmt).all()]


def list_movements(
    db: Session,
    *,
    product_id: str | None = None,
    movement_type: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> list[StockMovement]:
    """Return a page of stock movements, newest first.

    Useful for the per-product history view and for reconciliation reports.
    """
    limit, offset = _validate_page(limit, offset)
    stmt = _build_movements_filter(product_id=product_id, movement_type=movement_type)
    stmt = stmt.order_by(desc(StockMovement.created_at)).limit(limit).offset(offset)
    return list(db.scalars(stmt))


def count_movements(
    db: Session,
    *,
    product_id: str | None = None,
    movement_type: str | None = None,
) -> int:
    """Return the total number of movements matching the same filters as :func:`list_movements`."""
    stmt = _build_movements_filter(product_id=product_id, movement_type=movement_type)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    return int(db.scalar(count_stmt) or 0)


def _build_movements_filter(
    *, product_id: str | None, movement_type: str | None
):
    stmt = select(StockMovement)
    if product_id is not None:
        stmt = stmt.where(StockMovement.product_id == product_id)
    if movement_type is not None:
        # Validate so a typo gives an early error instead of an empty result.
        stmt = stmt.where(StockMovement.movement_type == _validate_movement_type(movement_type))
    return stmt

"""Product management service.

CRUD + search for the catalog. Products are never hard-deleted: setting
``is_active=False`` keeps them queryable for historical sale records while
hiding them from POS and inventory listings.

Public API:
    create_product(db, ...) -> Product
    get_product(db, product_id) -> Product
    get_product_by_barcode(db, barcode) -> Product
    update_product(db, product, ...) -> Product
    deactivate_product(db, product) -> None
    reactivate_product(db, product) -> None
    list_products(db, ...) -> list[Product]
    count_products(db, ...) -> int
    list_categories(db) -> list[str]

All functions take an existing :class:`~sqlalchemy.orm.Session`; the caller
controls transaction boundaries.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Final

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from retail_pos.models.product import Product, ProductUnit

# --- Validation limits --------------------------------------------------------

MAX_NAME_LENGTH: Final[int] = 200
MAX_BARCODE_LENGTH: Final[int] = 50
MAX_CATEGORY_LENGTH: Final[int] = 100
MAX_TAX_RATE: Final[Decimal] = Decimal("100.00")

# Pagination guardrails so misuse can't accidentally fetch the entire catalog.
DEFAULT_PAGE_SIZE: Final[int] = 50
MAX_PAGE_SIZE: Final[int] = 500

# Sentinel for "field not specified" in update_product. Distinguishing this
# from ``None`` lets callers clear nullable fields (``category``) explicitly.
_UNSET: Final[Any] = object()


# --- Exceptions ---------------------------------------------------------------


class ProductError(Exception):
    """Base class for product-service errors."""


class ProductNotFoundError(ProductError):
    """Lookup by id or barcode returned no row."""


class DuplicateBarcodeError(ProductError):
    """A product with the same barcode already exists."""


# --- Validation helpers -------------------------------------------------------


def _norm_str(value: str, *, field: str, max_length: int) -> str:
    """Strip whitespace and validate non-empty length."""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field} must not be empty")
    if len(stripped) > max_length:
        raise ValueError(f"{field} must be at most {max_length} characters")
    return stripped


def _norm_optional_category(value: str | None) -> str | None:
    """Trim/normalise an optional category string. Empty becomes ``None``."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("category must be a string or None")
    stripped = value.strip()
    if not stripped:
        return None
    if len(stripped) > MAX_CATEGORY_LENGTH:
        raise ValueError(f"category must be at most {MAX_CATEGORY_LENGTH} characters")
    return stripped


def _validate_unit(value: str) -> str:
    """Ensure ``value`` is one of the known :class:`ProductUnit` values."""
    valid = {u.value for u in ProductUnit}
    if value not in valid:
        raise ValueError(f"unit must be one of {sorted(valid)}, got {value!r}")
    return value


def _to_money(value: Decimal | int | float | str, *, field: str) -> Decimal:
    """Convert ``value`` to ``Decimal`` and ensure it is non-negative."""
    try:
        amount = Decimal(str(value))
    except (ValueError, ArithmeticError) as exc:
        raise ValueError(f"{field} is not a valid number") from exc
    if amount < 0:
        raise ValueError(f"{field} must not be negative")
    return amount


def _to_tax_rate(value: Decimal | int | float | str) -> Decimal:
    """Convert ``value`` to a tax-rate ``Decimal`` in the range 0–100."""
    rate = _to_money(value, field="tax_rate")
    if rate > MAX_TAX_RATE:
        raise ValueError(f"tax_rate must not exceed {MAX_TAX_RATE}")
    return rate


def _validate_page(limit: int, offset: int) -> tuple[int, int]:
    """Clamp pagination parameters to safe values."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    if offset < 0:
        raise ValueError("offset must not be negative")
    if limit > MAX_PAGE_SIZE:
        raise ValueError(f"limit must be at most {MAX_PAGE_SIZE}")
    return limit, offset


# --- Create -------------------------------------------------------------------


def create_product(
    db: Session,
    *,
    barcode: str,
    name: str,
    selling_price: Decimal | int | float | str,
    category: str | None = None,
    unit: str = ProductUnit.PIECE,
    cost_price: Decimal | int | float | str = 0,
    tax_rate: Decimal | int | float | str = 0,
) -> Product:
    """Create and persist a new product.

    Raises:
        ValueError: a field failed validation.
        DuplicateBarcodeError: a product with this barcode already exists.
    """
    product = Product(
        barcode=_norm_str(barcode, field="barcode", max_length=MAX_BARCODE_LENGTH),
        name=_norm_str(name, field="name", max_length=MAX_NAME_LENGTH),
        category=_norm_optional_category(category),
        unit=_validate_unit(unit),
        cost_price=_to_money(cost_price, field="cost_price"),
        selling_price=_to_money(selling_price, field="selling_price"),
        tax_rate=_to_tax_rate(tax_rate),
    )
    db.add(product)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateBarcodeError(
            f"a product with barcode {product.barcode!r} already exists"
        ) from exc
    return product


# --- Read ---------------------------------------------------------------------


def get_product(db: Session, product_id: str) -> Product:
    """Return the product with the given id or raise :class:`ProductNotFoundError`."""
    product = db.get(Product, product_id)
    if product is None:
        raise ProductNotFoundError(f"no product with id={product_id!r}")
    return product


def get_product_by_barcode(db: Session, barcode: str) -> Product:
    """Return the product with the given barcode or raise :class:`ProductNotFoundError`.

    Barcode lookup is the hot path during checkout, so this is kept as cheap
    as possible — a single indexed query, no joins.
    """
    barcode = _norm_str(barcode, field="barcode", max_length=MAX_BARCODE_LENGTH)
    product = db.scalar(select(Product).where(Product.barcode == barcode))
    if product is None:
        raise ProductNotFoundError(f"no product with barcode={barcode!r}")
    return product


def list_products(
    db: Session,
    *,
    query: str | None = None,
    category: str | None = None,
    active_only: bool = True,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> list[Product]:
    """Return a page of products matching the given filters.

    ``query`` matches ``name`` or ``barcode`` (case-insensitive substring).
    Results are sorted alphabetically by ``name`` for stable pagination.
    """
    limit, offset = _validate_page(limit, offset)
    stmt = _build_filter(query=query, category=category, active_only=active_only)
    stmt = stmt.order_by(func.lower(Product.name)).limit(limit).offset(offset)
    return list(db.scalars(stmt))


def count_products(
    db: Session,
    *,
    query: str | None = None,
    category: str | None = None,
    active_only: bool = True,
) -> int:
    """Return the total number of products matching the same filters as :func:`list_products`."""
    stmt = _build_filter(query=query, category=category, active_only=active_only)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    return int(db.scalar(count_stmt) or 0)


def list_categories(db: Session) -> list[str]:
    """Return the distinct, non-null categories in alphabetical order."""
    stmt = (
        select(Product.category)
        .where(Product.category.is_not(None))
        .distinct()
        .order_by(Product.category)
    )
    return [c for c in db.scalars(stmt) if c is not None]


def _build_filter(
    *, query: str | None, category: str | None, active_only: bool
) -> Any:
    """Build a SELECT for products with the standard filter combinations."""
    stmt = select(Product)
    if active_only:
        stmt = stmt.where(Product.is_active.is_(True))
    if category is not None:
        normalized = _norm_optional_category(category)
        # category=None after normalization means "match products without a
        # category"; preserve that explicitly.
        if normalized is None:
            stmt = stmt.where(Product.category.is_(None))
        else:
            stmt = stmt.where(Product.category == normalized)
    if query:
        pattern = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(Product.name.ilike(pattern), Product.barcode.ilike(pattern))
        )
    return stmt


# --- Update -------------------------------------------------------------------


def update_product(
    db: Session,
    product: Product,
    *,
    barcode: Any = _UNSET,
    name: Any = _UNSET,
    category: Any = _UNSET,
    unit: Any = _UNSET,
    cost_price: Any = _UNSET,
    selling_price: Any = _UNSET,
    tax_rate: Any = _UNSET,
    is_active: Any = _UNSET,
) -> Product:
    """Update one or more fields on ``product``.

    Any keyword argument left at the default sentinel is not changed. Pass
    ``category=None`` to explicitly clear a product's category.

    Raises:
        ValueError: a field failed validation.
        DuplicateBarcodeError: changing ``barcode`` would collide with another product.
    """
    if barcode is not _UNSET:
        product.barcode = _norm_str(
            barcode, field="barcode", max_length=MAX_BARCODE_LENGTH
        )
    if name is not _UNSET:
        product.name = _norm_str(name, field="name", max_length=MAX_NAME_LENGTH)
    if category is not _UNSET:
        product.category = _norm_optional_category(category)
    if unit is not _UNSET:
        product.unit = _validate_unit(unit)
    if cost_price is not _UNSET:
        product.cost_price = _to_money(cost_price, field="cost_price")
    if selling_price is not _UNSET:
        product.selling_price = _to_money(selling_price, field="selling_price")
    if tax_rate is not _UNSET:
        product.tax_rate = _to_tax_rate(tax_rate)
    if is_active is not _UNSET:
        if not isinstance(is_active, bool):
            raise ValueError("is_active must be a bool")
        product.is_active = is_active

    product.synced = False  # local change; sync engine will pick this up

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateBarcodeError(
            f"a product with barcode {product.barcode!r} already exists"
        ) from exc
    return product


def deactivate_product(db: Session, product: Product) -> None:
    """Soft-delete a product by setting ``is_active=False``."""
    if product.is_active:
        product.is_active = False
        product.synced = False
        db.flush()


def reactivate_product(db: Session, product: Product) -> None:
    """Re-enable a previously deactivated product."""
    if not product.is_active:
        product.is_active = True
        product.synced = False
        db.flush()

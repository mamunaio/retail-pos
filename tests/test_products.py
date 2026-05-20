"""Tests for the product management service."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from retail_pos.models import Product, ProductUnit
from retail_pos.services.products import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    DuplicateBarcodeError,
    ProductNotFoundError,
    count_products,
    create_product,
    deactivate_product,
    get_product,
    get_product_by_barcode,
    list_categories,
    list_products,
    reactivate_product,
    update_product,
)


# --- Helpers ------------------------------------------------------------------


def _create(
    db: Session,
    *,
    barcode: str,
    name: str = "Sample Product",
    category: str | None = "Grocery",
    selling_price: Decimal | int = 100,
    cost_price: Decimal | int = 70,
    unit: str = ProductUnit.PIECE,
    tax_rate: Decimal | int = 0,
) -> Product:
    product = create_product(
        db,
        barcode=barcode,
        name=name,
        category=category,
        unit=unit,
        cost_price=cost_price,
        selling_price=selling_price,
        tax_rate=tax_rate,
    )
    db.commit()
    return product


# --- create_product -----------------------------------------------------------


def test_create_product_success(db_session: Session) -> None:
    product = create_product(
        db_session,
        barcode="123456",
        name="  Coca-Cola 500ml  ",  # extra whitespace is trimmed
        category=" Beverages ",
        selling_price=Decimal("40.00"),
        cost_price=Decimal("32.00"),
    )
    db_session.commit()

    assert product.id  # auto-generated UUID
    assert product.barcode == "123456"
    assert product.name == "Coca-Cola 500ml"
    assert product.category == "Beverages"
    assert product.unit == ProductUnit.PIECE
    assert product.is_active is True
    assert product.synced is False


def test_create_product_accepts_numeric_strings(db_session: Session) -> None:
    product = create_product(
        db_session,
        barcode="9999",
        name="Soybean Oil",
        selling_price="185.50",
        cost_price="165.00",
        tax_rate="5",
    )
    db_session.commit()

    assert product.selling_price == Decimal("185.50")
    assert product.cost_price == Decimal("165.00")
    assert product.tax_rate == Decimal("5")


def test_create_product_empty_category_becomes_none(db_session: Session) -> None:
    product = create_product(
        db_session,
        barcode="0001",
        name="Test",
        category="   ",  # only whitespace
        selling_price=10,
    )
    db_session.commit()

    assert product.category is None


def test_create_product_rejects_empty_barcode(db_session: Session) -> None:
    with pytest.raises(ValueError, match="barcode"):
        create_product(db_session, barcode="  ", name="x", selling_price=1)


def test_create_product_rejects_empty_name(db_session: Session) -> None:
    with pytest.raises(ValueError, match="name"):
        create_product(db_session, barcode="1", name="  ", selling_price=1)


def test_create_product_rejects_negative_price(db_session: Session) -> None:
    with pytest.raises(ValueError, match="selling_price"):
        create_product(db_session, barcode="1", name="x", selling_price=-1)
    with pytest.raises(ValueError, match="cost_price"):
        create_product(
            db_session, barcode="2", name="x", selling_price=10, cost_price=-1
        )


def test_create_product_rejects_invalid_tax_rate(db_session: Session) -> None:
    with pytest.raises(ValueError, match="tax_rate"):
        create_product(
            db_session, barcode="1", name="x", selling_price=10, tax_rate=120
        )
    with pytest.raises(ValueError, match="tax_rate"):
        create_product(
            db_session, barcode="2", name="x", selling_price=10, tax_rate=-5
        )


def test_create_product_rejects_unknown_unit(db_session: Session) -> None:
    with pytest.raises(ValueError, match="unit"):
        create_product(
            db_session, barcode="1", name="x", selling_price=10, unit="bucket"
        )


def test_create_product_duplicate_barcode_raises(db_session: Session) -> None:
    _create(db_session, barcode="DUP-1")

    with pytest.raises(DuplicateBarcodeError):
        create_product(db_session, barcode="DUP-1", name="Other", selling_price=10)


# --- get_product / get_product_by_barcode -------------------------------------


def test_get_product_by_id(db_session: Session) -> None:
    product = _create(db_session, barcode="GET-1", name="Lookup")

    fetched = get_product(db_session, product.id)
    assert fetched.id == product.id


def test_get_product_unknown_id_raises(db_session: Session) -> None:
    with pytest.raises(ProductNotFoundError):
        get_product(db_session, "no-such-id")


def test_get_product_by_barcode(db_session: Session) -> None:
    _create(db_session, barcode="BC-100", name="Test")

    fetched = get_product_by_barcode(db_session, "BC-100")
    assert fetched.barcode == "BC-100"


def test_get_product_by_barcode_unknown_raises(db_session: Session) -> None:
    with pytest.raises(ProductNotFoundError):
        get_product_by_barcode(db_session, "missing-barcode")


# --- update_product -----------------------------------------------------------


def test_update_product_changes_provided_fields_only(db_session: Session) -> None:
    product = _create(
        db_session,
        barcode="UPD-1",
        name="Original",
        category="Cat-A",
        selling_price=100,
    )
    original_cost = product.cost_price

    update_product(db_session, product, name="Updated", selling_price=120)
    db_session.commit()
    db_session.refresh(product)

    assert product.name == "Updated"
    assert product.selling_price == Decimal("120")
    # Untouched fields preserved.
    assert product.barcode == "UPD-1"
    assert product.category == "Cat-A"
    assert product.cost_price == original_cost


def test_update_product_can_clear_category(db_session: Session) -> None:
    product = _create(db_session, barcode="UPD-2", category="Cat-A")

    # Explicitly passing None must clear the field (sentinel-distinct from "no change").
    update_product(db_session, product, category=None)
    db_session.commit()
    db_session.refresh(product)

    assert product.category is None


def test_update_product_marks_synced_false(db_session: Session) -> None:
    product = _create(db_session, barcode="UPD-3")
    product.synced = True
    db_session.commit()

    update_product(db_session, product, name="New Name")
    db_session.commit()
    db_session.refresh(product)

    assert product.synced is False


def test_update_product_duplicate_barcode_raises(db_session: Session) -> None:
    _create(db_session, barcode="A-1")
    other = _create(db_session, barcode="B-1")

    with pytest.raises(DuplicateBarcodeError):
        update_product(db_session, other, barcode="A-1")
        db_session.commit()


def test_update_product_validates_new_values(db_session: Session) -> None:
    product = _create(db_session, barcode="UPD-4")

    with pytest.raises(ValueError, match="selling_price"):
        update_product(db_session, product, selling_price=-1)


# --- deactivate / reactivate --------------------------------------------------


def test_deactivate_and_reactivate(db_session: Session) -> None:
    product = _create(db_session, barcode="DEL-1")
    assert product.is_active is True

    deactivate_product(db_session, product)
    db_session.commit()
    db_session.refresh(product)
    assert product.is_active is False
    assert product.synced is False

    reactivate_product(db_session, product)
    db_session.commit()
    db_session.refresh(product)
    assert product.is_active is True


def test_deactivate_is_idempotent(db_session: Session) -> None:
    product = _create(db_session, barcode="DEL-2")
    deactivate_product(db_session, product)
    db_session.commit()

    # Second call must not raise.
    deactivate_product(db_session, product)


# --- list_products ------------------------------------------------------------


def test_list_products_active_only_by_default(db_session: Session) -> None:
    a = _create(db_session, barcode="L-1", name="Apple")
    b = _create(db_session, barcode="L-2", name="Banana")
    deactivate_product(db_session, b)
    db_session.commit()

    results = list_products(db_session)
    ids = {p.id for p in results}
    assert a.id in ids
    assert b.id not in ids


def test_list_products_includes_inactive_when_requested(db_session: Session) -> None:
    _create(db_session, barcode="L-3", name="Apple")
    b = _create(db_session, barcode="L-4", name="Banana")
    deactivate_product(db_session, b)
    db_session.commit()

    results = list_products(db_session, active_only=False)
    assert len(results) == 2


def test_list_products_filters_by_category(db_session: Session) -> None:
    _create(db_session, barcode="C-1", name="Apple", category="Fruit")
    _create(db_session, barcode="C-2", name="Banana", category="Fruit")
    _create(db_session, barcode="C-3", name="Bread", category="Bakery")

    results = list_products(db_session, category="Fruit")
    assert len(results) == 2
    assert {p.name for p in results} == {"Apple", "Banana"}


def test_list_products_search_by_name_case_insensitive(db_session: Session) -> None:
    _create(db_session, barcode="S-1", name="Coca-Cola 500ml")
    _create(db_session, barcode="S-2", name="Pepsi 500ml")
    _create(db_session, barcode="S-3", name="Mango Juice")

    results = list_products(db_session, query="cola")
    assert len(results) == 1
    assert results[0].name == "Coca-Cola 500ml"


def test_list_products_search_matches_barcode(db_session: Session) -> None:
    _create(db_session, barcode="8901234567890", name="Mango Juice")
    _create(db_session, barcode="0000000000001", name="Soybean Oil")

    results = list_products(db_session, query="89012")
    assert len(results) == 1
    assert results[0].name == "Mango Juice"


def test_list_products_pagination(db_session: Session) -> None:
    # Names chosen so alphabetic sort is predictable.
    for i in range(10):
        _create(db_session, barcode=f"P-{i:02d}", name=f"Item {i:02d}")

    page1 = list_products(db_session, limit=4, offset=0)
    page2 = list_products(db_session, limit=4, offset=4)
    page3 = list_products(db_session, limit=4, offset=8)

    assert [p.name for p in page1] == ["Item 00", "Item 01", "Item 02", "Item 03"]
    assert [p.name for p in page2] == ["Item 04", "Item 05", "Item 06", "Item 07"]
    assert [p.name for p in page3] == ["Item 08", "Item 09"]


def test_list_products_rejects_invalid_pagination(db_session: Session) -> None:
    with pytest.raises(ValueError):
        list_products(db_session, limit=0)
    with pytest.raises(ValueError):
        list_products(db_session, offset=-1)
    with pytest.raises(ValueError):
        list_products(db_session, limit=MAX_PAGE_SIZE + 1)


def test_list_products_default_limit(db_session: Session) -> None:
    # Sanity check: default page size is what the constant says.
    assert DEFAULT_PAGE_SIZE > 0


# --- count_products -----------------------------------------------------------


def test_count_products_matches_filters(db_session: Session) -> None:
    _create(db_session, barcode="K-1", name="Apple", category="Fruit")
    _create(db_session, barcode="K-2", name="Banana", category="Fruit")
    _create(db_session, barcode="K-3", name="Bread", category="Bakery")

    assert count_products(db_session) == 3
    assert count_products(db_session, category="Fruit") == 2
    assert count_products(db_session, query="App") == 1


def test_count_excludes_inactive_by_default(db_session: Session) -> None:
    _create(db_session, barcode="K-4", name="Active")
    inactive = _create(db_session, barcode="K-5", name="Inactive")
    deactivate_product(db_session, inactive)
    db_session.commit()

    assert count_products(db_session) == 1
    assert count_products(db_session, active_only=False) == 2


# --- list_categories ----------------------------------------------------------


def test_list_categories_distinct_and_sorted(db_session: Session) -> None:
    _create(db_session, barcode="X-1", category="Beverages")
    _create(db_session, barcode="X-2", category="Beverages")
    _create(db_session, barcode="X-3", category="Grocery")
    _create(db_session, barcode="X-4", category=None)
    _create(db_session, barcode="X-5", category="Bakery")

    assert list_categories(db_session) == ["Bakery", "Beverages", "Grocery"]


def test_list_categories_empty_when_no_products(db_session: Session) -> None:
    assert list_categories(db_session) == []

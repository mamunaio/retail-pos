"""Seed sample data for local development.

Creates:
  - 1 admin user (username ``admin``, PIN ``1234``)
  - 1 cashier user (username ``cashier1``, PIN ``0000``)
  - 1 terminal (``POS-01``)
  - A handful of sample products

Safe to run multiple times: existing rows (matched by their unique key) are
skipped.

Usage:
    python -m scripts.seed
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from retail_pos.db import session_scope
from retail_pos.models import Discount, Product, ProductUnit, Supplier, Terminal, User, UserRole
from retail_pos.services.inventory_service import InventoryService
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


def _get_or_create_supplier(
    db: Session,
    *,
    supplier_code: str,
    name: str,
    company_name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    address: str | None = None,
    contact_person: str | None = None,
    payment_terms: str | None = None,
    credit_limit: Decimal = Decimal("0.00"),
) -> Supplier:
    existing = db.scalar(select(Supplier).where(Supplier.supplier_code == supplier_code))
    if existing is not None:
        return existing
    supplier = Supplier(
        supplier_code=supplier_code,
        name=name,
        company_name=company_name,
        phone=phone,
        email=email,
        address=address,
        contact_person=contact_person,
        payment_terms=payment_terms,
        credit_limit=credit_limit,
    )
    db.add(supplier)
    return supplier


SAMPLE_PRODUCTS: list[dict[str, object]] = [
    {
        "barcode": "8901234567890",
        "name": "Pran Mango Juice 250ml",
        "category": "Beverages",
        "unit": ProductUnit.PIECE,
        "cost_price": Decimal("18.00"),
        "selling_price": Decimal("25.00"),
        "initial_stock": Decimal("50.00"),
    },
    {
        "barcode": "8901234567891",
        "name": "Coca-Cola 500ml",
        "category": "Beverages",
        "unit": ProductUnit.PIECE,
        "cost_price": Decimal("32.00"),
        "selling_price": Decimal("40.00"),
        "initial_stock": Decimal("100.00"),
    },
    {
        "barcode": "8901234567892",
        "name": "Miniket Rice (loose)",
        "category": "Grocery",
        "unit": ProductUnit.KILOGRAM,
        "cost_price": Decimal("65.00"),
        "selling_price": Decimal("75.00"),
        "initial_stock": Decimal("200.00"),
    },
    {
        "barcode": "8901234567893",
        "name": "Soybean Oil 1L",
        "category": "Grocery",
        "unit": ProductUnit.PIECE,
        "cost_price": Decimal("165.00"),
        "selling_price": Decimal("185.00"),
        "initial_stock": Decimal("30.00"),
    },
    {
        "barcode": "8901234567894",
        "name": "Lux Soap 100g",
        "category": "Toiletries",
        "unit": ProductUnit.PIECE,
        "cost_price": Decimal("45.00"),
        "selling_price": Decimal("55.00"),
        "initial_stock": Decimal("75.00"),
    },
]


SAMPLE_SUPPLIERS: list[dict[str, object]] = [
    {
        "supplier_code": "SUP-0001",
        "name": "Pran-RFL Group",
        "company_name": "Pran-RFL Group",
        "phone": "+880-2-8878456",
        "email": "info@prangroup.com",
        "address": "PRAN Centre, 105 Middle Badda, Dhaka 1212",
        "contact_person": "Mr. Rahman",
        "payment_terms": "Net 30",
        "credit_limit": Decimal("500000.00"),
    },
    {
        "supplier_code": "SUP-0002",
        "name": "Square Toiletries",
        "company_name": "Square Toiletries Ltd.",
        "phone": "+880-2-8159687",
        "email": "contact@squaretoiletries.com",
        "address": "Square Centre, 48 Mohakhali C/A, Dhaka 1212",
        "contact_person": "Ms. Sultana",
        "payment_terms": "Net 15",
        "credit_limit": Decimal("300000.00"),
    },
    {
        "supplier_code": "SUP-0003",
        "name": "City Group",
        "company_name": "City Group Bangladesh",
        "phone": "+880-2-9887766",
        "email": "sales@citygroup.com.bd",
        "address": "City Centre, Gulshan-1, Dhaka 1212",
        "contact_person": "Mr. Karim",
        "payment_terms": "COD",
        "credit_limit": Decimal("200000.00"),
    },
]


SAMPLE_DISCOUNTS: list[dict[str, object]] = [
    {
        "code": "WELCOME10",
        "name": "Welcome Discount 10%",
        "description": "10% off for new customers",
        "discount_type": "percentage",
        "discount_scope": "order",
        "discount_value": Decimal("10.00"),
        "max_discount_amount": Decimal("500.00"),
        "min_purchase_amount": Decimal("500.00"),
        "is_automatic": False,
        "requires_code": True,
        "usage_limit": 100,
        "usage_limit_per_customer": 1,
    },
    {
        "code": "SAVE50",
        "name": "Save ৳50",
        "description": "৳50 off on orders above ৳1000",
        "discount_type": "fixed_amount",
        "discount_scope": "order",
        "discount_value": Decimal("50.00"),
        "min_purchase_amount": Decimal("1000.00"),
        "is_automatic": False,
        "requires_code": True,
        "usage_limit": 50,
    },
    {
        "code": "BUY2GET1",
        "name": "Buy 2 Get 1 Free",
        "description": "Buy 2 items, get 1 free on beverages",
        "discount_type": "buy_x_get_y",
        "discount_scope": "category",
        "discount_value": Decimal("0.00"),
        "buy_quantity": 2,
        "get_quantity": 1,
        "category": "Beverages",
        "is_automatic": True,
        "requires_code": False,
    },
]


def _get_or_create_discount(
    db: Session,
    admin_user_id: str,
    *,
    code: str,
    name: str,
    description: str | None,
    discount_type: str,
    discount_scope: str,
    discount_value: Decimal,
    max_discount_amount: Decimal | None = None,
    buy_quantity: int | None = None,
    get_quantity: int | None = None,
    min_purchase_amount: Decimal = Decimal("0.00"),
    category: str | None = None,
    is_automatic: bool = False,
    requires_code: bool = True,
    usage_limit: int | None = None,
    usage_limit_per_customer: int | None = None,
) -> Discount:
    from datetime import datetime, timedelta

    existing = db.scalar(select(Discount).where(Discount.code == code))
    if existing is not None:
        return existing

    discount = Discount(
        code=code,
        name=name,
        description=description,
        discount_type=discount_type,
        discount_scope=discount_scope,
        discount_value=discount_value,
        max_discount_amount=max_discount_amount,
        buy_quantity=buy_quantity,
        get_quantity=get_quantity,
        min_purchase_amount=min_purchase_amount,
        category=category,
        valid_from=datetime.now(),
        valid_until=datetime.now() + timedelta(days=90),  # Valid for 90 days
        is_automatic=is_automatic,
        requires_code=requires_code,
        usage_limit=usage_limit,
        usage_limit_per_customer=usage_limit_per_customer,
        created_by=admin_user_id,
    )
    db.add(discount)
    return discount


def seed() -> None:
    """Populate the local database with development sample data."""
    with session_scope() as db:
        admin_user = _get_or_create_user(
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

        # Create suppliers
        for supplier_data in SAMPLE_SUPPLIERS:
            _get_or_create_supplier(db, **supplier_data)  # type: ignore[arg-type]

        # Create products and set initial stock
        for item in SAMPLE_PRODUCTS:
            initial_stock = item.pop("initial_stock", None)
            product = _get_or_create_product(db, **item)  # type: ignore[arg-type]

            # Set initial stock if provided
            if initial_stock is not None:
                from retail_pos.models import StockMovementType

                InventoryService.adjust_stock(
                    db=db,
                    product_id=product.id,
                    quantity_change=initial_stock,
                    movement_type=StockMovementType.INITIAL,
                    notes="Initial stock",
                )

        # Create discounts
        for discount_data in SAMPLE_DISCOUNTS:
            _get_or_create_discount(db, admin_user.id, **discount_data)  # type: ignore[arg-type]

    print("Seed complete:")
    print("  - admin   / PIN 1234")
    print("  - cashier1 / PIN 0000")
    print("  - terminal POS-01")
    print(f"  - {len(SAMPLE_PRODUCTS)} sample products with initial stock")
    print(f"  - {len(SAMPLE_SUPPLIERS)} sample suppliers")
    print(f"  - {len(SAMPLE_DISCOUNTS)} sample discounts")


if __name__ == "__main__":
    seed()

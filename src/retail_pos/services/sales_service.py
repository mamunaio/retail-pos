"""Sales service for POS operations."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from retail_pos.models import (
    PaymentMethod,
    Product,
    Sale,
    SaleItem,
    SaleStatus,
    StockMovementType,
)
from retail_pos.services.customer_service import CustomerService
from retail_pos.services.inventory_service import InventoryService


class SalesService:
    """Service for managing sales and POS operations."""

    @staticmethod
    def generate_invoice_number(db: Session) -> str:
        """Generate a unique invoice number.

        Format: INV-YYYYMMDD-NNNN
        Example: INV-20260521-0001
        """
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"INV-{today}-"

        # Get the last invoice number for today
        last_sale = db.scalar(
            select(Sale)
            .where(Sale.invoice_number.like(f"{prefix}%"))
            .order_by(Sale.invoice_number.desc())
            .limit(1)
        )

        if last_sale:
            # Extract the sequence number and increment
            last_seq = int(last_sale.invoice_number.split("-")[-1])
            new_seq = last_seq + 1
        else:
            new_seq = 1

        return f"{prefix}{new_seq:04d}"

    @staticmethod
    def calculate_line_total(
        unit_price: Decimal,
        quantity: Decimal,
        tax_rate: Decimal = Decimal("0.00"),
        discount: Decimal = Decimal("0.00"),
    ) -> Decimal:
        """Calculate line item total.

        Formula: (unit_price × quantity - discount) × (1 + tax_rate/100)
        """
        subtotal = unit_price * quantity - discount
        tax_amount = subtotal * (tax_rate / Decimal("100"))
        return subtotal + tax_amount

    @staticmethod
    def create_sale(
        db: Session,
        terminal_id: str,
        cashier_id: str,
        items: list[dict],
        payment_method: PaymentMethod,
        amount_paid: Decimal,
        customer_id: str | None = None,
        customer_name: str | None = None,
        customer_phone: str | None = None,
        discount_amount: Decimal = Decimal("0.00"),
        notes: str | None = None,
    ) -> Sale:
        """Create a new sale with items and process payment.

        Args:
            db: Database session
            terminal_id: Terminal ID
            cashier_id: Cashier user ID
            items: List of items with product_id, quantity, unit_price
            payment_method: Payment method
            amount_paid: Amount paid by customer
            customer_name: Optional customer name
            customer_phone: Optional customer phone
            discount_amount: Optional discount on total
            notes: Optional notes

        Returns:
            Created Sale object

        Raises:
            ValueError: If insufficient stock or payment
        """
        # Generate invoice number
        invoice_number = SalesService.generate_invoice_number(db)

        # Calculate totals
        subtotal = Decimal("0.00")
        tax_amount = Decimal("0.00")
        sale_items = []

        for item_data in items:
            product = db.get(Product, item_data["product_id"])
            if not product:
                raise ValueError(f"Product {item_data['product_id']} not found")

            if not product.is_active:
                raise ValueError(f"Product {product.name} is not active")

            quantity = Decimal(str(item_data["quantity"]))
            unit_price_value = item_data.get("unit_price")
            if unit_price_value is None:
                unit_price = product.selling_price
            else:
                unit_price = Decimal(str(unit_price_value))
            item_discount = Decimal(str(item_data.get("discount", "0.00")))

            # Calculate line total
            line_total = SalesService.calculate_line_total(
                unit_price=unit_price,
                quantity=quantity,
                tax_rate=product.tax_rate,
                discount=item_discount,
            )

            # Calculate tax for this line
            line_subtotal = unit_price * quantity - item_discount
            line_tax = line_subtotal * (product.tax_rate / Decimal("100"))

            subtotal += line_subtotal
            tax_amount += line_tax

            # Check stock availability
            inventory = InventoryService.get_or_create_inventory(db, product.id)
            if inventory.quantity < quantity:
                raise ValueError(
                    f"Insufficient stock for {product.name}. "
                    f"Available: {inventory.quantity}, Requested: {quantity}"
                )

            sale_items.append(
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "product_barcode": product.barcode,
                    "unit_price": unit_price,
                    "quantity": quantity,
                    "tax_rate": product.tax_rate,
                    "discount_amount": item_discount,
                    "line_total": line_total,
                }
            )

        # Calculate final total
        total_amount = subtotal + tax_amount - discount_amount

        # Validate payment
        if amount_paid < total_amount:
            raise ValueError(
                f"Insufficient payment. Total: {total_amount}, Paid: {amount_paid}"
            )

        change_given = amount_paid - total_amount

        # Create sale
        sale = Sale(
            invoice_number=invoice_number,
            terminal_id=terminal_id,
            cashier_id=cashier_id,
            customer_id=customer_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            subtotal=subtotal,
            tax_amount=tax_amount,
            discount_amount=discount_amount,
            total_amount=total_amount,
            payment_method=payment_method,
            amount_paid=amount_paid,
            change_given=change_given,
            status=SaleStatus.COMPLETED,
            notes=notes,
        )
        db.add(sale)
        db.flush()

        # Create sale items and deduct stock
        for item_data in sale_items:
            sale_item = SaleItem(sale_id=sale.id, **item_data)
            db.add(sale_item)

            # Deduct stock
            InventoryService.adjust_stock(
                db=db,
                product_id=item_data["product_id"],
                quantity_change=-item_data["quantity"],
                movement_type=StockMovementType.SALE,
                user_id=cashier_id,
                reference_id=sale.id,
                notes=f"Sale {invoice_number}",
            )

        # Update customer stats if customer is linked
        if customer_id:
            CustomerService.update_purchase_stats(db, customer_id, total_amount)

        db.flush()
        return sale

    @staticmethod
    def get_sale(db: Session, sale_id: str) -> Sale | None:
        """Get a sale with all its items."""
        return db.scalar(
            select(Sale)
            .options(
                joinedload(Sale.items).joinedload(SaleItem.product),
                joinedload(Sale.cashier),
                joinedload(Sale.terminal),
            )
            .where(Sale.id == sale_id)
        )

    @staticmethod
    def get_sale_by_invoice(db: Session, invoice_number: str) -> Sale | None:
        """Get a sale by invoice number."""
        return db.scalar(
            select(Sale)
            .options(
                joinedload(Sale.items).joinedload(SaleItem.product),
                joinedload(Sale.cashier),
                joinedload(Sale.terminal),
            )
            .where(Sale.invoice_number == invoice_number)
        )

    @staticmethod
    def list_sales(
        db: Session,
        status: SaleStatus | None = None,
        cashier_id: str | None = None,
        terminal_id: str | None = None,
        limit: int = 100,
    ) -> list[Sale]:
        """List sales with filters."""
        query = select(Sale).options(
            joinedload(Sale.cashier), joinedload(Sale.terminal)
        )

        if status:
            query = query.where(Sale.status == status)
        if cashier_id:
            query = query.where(Sale.cashier_id == cashier_id)
        if terminal_id:
            query = query.where(Sale.terminal_id == terminal_id)

        query = query.order_by(Sale.created_at.desc()).limit(limit)

        return list(db.scalars(query).unique().all())

    @staticmethod
    def cancel_sale(db: Session, sale_id: str, user_id: str, reason: str) -> Sale:
        """Cancel a sale and restore stock.

        Args:
            db: Database session
            sale_id: Sale ID to cancel
            user_id: User performing the cancellation
            reason: Reason for cancellation

        Returns:
            Updated Sale object

        Raises:
            ValueError: If sale not found or already cancelled
        """
        sale = SalesService.get_sale(db, sale_id)
        if not sale:
            raise ValueError("Sale not found")

        if sale.status == SaleStatus.CANCELLED:
            raise ValueError("Sale is already cancelled")

        # Restore stock for each item
        for item in sale.items:
            InventoryService.adjust_stock(
                db=db,
                product_id=item.product_id,
                quantity_change=item.quantity,  # Add back
                movement_type=StockMovementType.ADJUSTMENT,
                user_id=user_id,
                reference_id=sale.id,
                notes=f"Sale {sale.invoice_number} cancelled: {reason}",
            )

        # Update sale status
        sale.status = SaleStatus.CANCELLED
        sale.notes = f"{sale.notes or ''}\n[CANCELLED] {reason}".strip()

        db.flush()
        return sale

    @staticmethod
    def get_daily_summary(db: Session, date: datetime | None = None) -> dict:
        """Get sales summary for a specific date.

        Args:
            db: Database session
            date: Date to get summary for (defaults to today)

        Returns:
            Dictionary with sales statistics
        """
        if date is None:
            date = datetime.now()

        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)

        sales = db.scalars(
            select(Sale)
            .where(
                Sale.created_at >= start_of_day,
                Sale.created_at <= end_of_day,
                Sale.status == SaleStatus.COMPLETED,
            )
            .order_by(Sale.created_at)
        ).all()

        total_sales = len(sales)
        total_revenue = sum(sale.total_amount for sale in sales)
        total_tax = sum(sale.tax_amount for sale in sales)
        total_discount = sum(sale.discount_amount for sale in sales)

        # Count by payment method
        payment_methods = {}
        for sale in sales:
            method = sale.payment_method
            if method not in payment_methods:
                payment_methods[method] = {"count": 0, "amount": Decimal("0.00")}
            payment_methods[method]["count"] += 1
            payment_methods[method]["amount"] += sale.total_amount

        return {
            "date": date.strftime("%Y-%m-%d"),
            "total_sales": total_sales,
            "total_revenue": float(total_revenue),
            "total_tax": float(total_tax),
            "total_discount": float(total_discount),
            "payment_methods": {
                k: {"count": v["count"], "amount": float(v["amount"])}
                for k, v in payment_methods.items()
            },
        }

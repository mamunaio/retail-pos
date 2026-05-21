"""Purchase service for managing purchase orders."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from retail_pos.models.inventory import StockMovementType
from retail_pos.models.product import Product
from retail_pos.models.purchase import PaymentStatus, Purchase, PurchaseItem, PurchaseStatus
from retail_pos.models.supplier import Supplier
from retail_pos.services.inventory_service import InventoryService
from retail_pos.services.supplier_service import SupplierService
from retail_pos.utils.exceptions import ResourceNotFoundError, ValidationError

if TYPE_CHECKING:
    pass


class PurchaseService:
    """Service for managing purchase orders."""

    def __init__(self, db: Session) -> None:
        """Initialize purchase service.

        Args:
            db: Database session
        """
        self.db = db
        self.inventory_service = InventoryService(db)
        self.supplier_service = SupplierService(db)

    def create_purchase(
        self,
        supplier_id: str,
        items: list[dict],
        created_by: str,
        purchase_date: datetime | None = None,
        expected_delivery_date: datetime | None = None,
        tax_amount: Decimal = Decimal("0.00"),
        shipping_cost: Decimal = Decimal("0.00"),
        discount_amount: Decimal = Decimal("0.00"),
        reference_number: str | None = None,
        notes: str | None = None,
    ) -> Purchase:
        """Create a new purchase order.

        Args:
            supplier_id: Supplier ID
            items: List of items with product_id, quantity, unit_cost
            created_by: User ID who created the purchase
            purchase_date: Purchase date (defaults to now)
            expected_delivery_date: Expected delivery date
            tax_amount: Tax amount
            shipping_cost: Shipping cost
            discount_amount: Discount amount
            reference_number: Supplier's reference number
            notes: Additional notes

        Returns:
            Created purchase order

        Raises:
            ValidationError: If validation fails
            ResourceNotFoundError: If supplier or product not found
        """
        # Validate supplier
        supplier = self.supplier_service.get_supplier(supplier_id)

        # Validate items
        if not items:
            raise ValidationError("Purchase must have at least one item")

        # Calculate subtotal
        subtotal = Decimal("0.00")
        purchase_items = []

        for item_data in items:
            product_id = item_data.get("product_id")
            quantity = Decimal(str(item_data.get("quantity", 0)))
            unit_cost = Decimal(str(item_data.get("unit_cost", 0)))

            if quantity <= 0:
                raise ValidationError("Quantity must be greater than 0")
            if unit_cost < 0:
                raise ValidationError("Unit cost cannot be negative")

            # Validate product exists
            product = self.db.get(Product, product_id)
            if not product:
                raise ResourceNotFoundError("Product", product_id)

            total_cost = quantity * unit_cost
            subtotal += total_cost

            purchase_items.append(
                PurchaseItem(
                    product_id=product_id,
                    quantity_ordered=quantity,
                    unit_cost=unit_cost,
                    total_cost=total_cost,
                    notes=item_data.get("notes"),
                )
            )

        # Calculate total
        total_amount = subtotal + tax_amount + shipping_cost - discount_amount

        # Generate purchase number
        purchase_number = self._generate_purchase_number()

        # Create purchase
        purchase = Purchase(
            purchase_number=purchase_number,
            supplier_id=supplier_id,
            purchase_date=purchase_date or datetime.now(),
            expected_delivery_date=expected_delivery_date,
            subtotal=subtotal,
            tax_amount=tax_amount,
            shipping_cost=shipping_cost,
            discount_amount=discount_amount,
            total_amount=total_amount,
            reference_number=reference_number,
            notes=notes,
            created_by=created_by,
            status=PurchaseStatus.DRAFT.value,
            payment_status=PaymentStatus.UNPAID.value,
        )

        # Add items
        for item in purchase_items:
            purchase.items.append(item)

        self.db.add(purchase)
        self.db.commit()
        self.db.refresh(purchase)

        return purchase

    def get_purchase(self, purchase_id: str) -> Purchase:
        """Get purchase by ID with items loaded.

        Args:
            purchase_id: Purchase ID

        Returns:
            Purchase

        Raises:
            ResourceNotFoundError: If purchase not found
        """
        stmt = (
            select(Purchase)
            .where(Purchase.id == purchase_id)
            .options(joinedload(Purchase.items), joinedload(Purchase.supplier))
        )
        purchase = self.db.execute(stmt).scalar_one_or_none()
        if not purchase:
            raise ResourceNotFoundError("Purchase", purchase_id)
        return purchase

    def get_purchase_by_number(self, purchase_number: str) -> Purchase:
        """Get purchase by purchase number.

        Args:
            purchase_number: Purchase number

        Returns:
            Purchase

        Raises:
            ResourceNotFoundError: If purchase not found
        """
        stmt = (
            select(Purchase)
            .where(Purchase.purchase_number == purchase_number)
            .options(joinedload(Purchase.items), joinedload(Purchase.supplier))
        )
        purchase = self.db.execute(stmt).scalar_one_or_none()
        if not purchase:
            raise ResourceNotFoundError("Purchase", purchase_number)
        return purchase

    def list_purchases(
        self,
        supplier_id: str | None = None,
        status: str | None = None,
        payment_status: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Purchase]:
        """List purchases with optional filtering.

        Args:
            supplier_id: Filter by supplier
            status: Filter by status
            payment_status: Filter by payment status
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of purchases
        """
        stmt = select(Purchase).options(joinedload(Purchase.supplier))

        if supplier_id:
            stmt = stmt.where(Purchase.supplier_id == supplier_id)
        if status:
            stmt = stmt.where(Purchase.status == status)
        if payment_status:
            stmt = stmt.where(Purchase.payment_status == payment_status)
        if start_date:
            stmt = stmt.where(Purchase.purchase_date >= start_date)
        if end_date:
            stmt = stmt.where(Purchase.purchase_date <= end_date)

        stmt = stmt.order_by(Purchase.purchase_date.desc()).limit(limit).offset(offset)
        result = self.db.execute(stmt)
        return list(result.scalars().all())

    def update_purchase_status(
        self,
        purchase_id: str,
        status: str,
        received_by: str | None = None,
    ) -> Purchase:
        """Update purchase status.

        Args:
            purchase_id: Purchase ID
            status: New status
            received_by: User ID who received the goods (for RECEIVED status)

        Returns:
            Updated purchase

        Raises:
            ResourceNotFoundError: If purchase not found
            ValidationError: If status transition is invalid
        """
        purchase = self.get_purchase(purchase_id)

        # Validate status
        if status not in [s.value for s in PurchaseStatus]:
            raise ValidationError(f"Invalid status: {status}")

        # Validate status transition
        if purchase.status == PurchaseStatus.CANCELLED.value:
            raise ValidationError("Cannot update cancelled purchase")

        if status == PurchaseStatus.RECEIVED.value:
            if purchase.status != PurchaseStatus.ORDERED.value:
                raise ValidationError("Can only receive ordered purchases")
            if not received_by:
                raise ValidationError("received_by is required for RECEIVED status")

            # Update stock for all items
            for item in purchase.items:
                self.inventory_service.adjust_stock(
                    product_id=item.product_id,
                    quantity_change=item.quantity_ordered,
                    movement_type=StockMovementType.PURCHASE.value,
                    reference_id=purchase.id,
                    notes=f"Purchase received: {purchase.purchase_number}",
                )
                item.quantity_received = item.quantity_ordered

            purchase.received_date = datetime.now()
            purchase.received_by = received_by

            # Update supplier stats
            self.supplier_service.update_supplier_stats(
                supplier_id=purchase.supplier_id,
                purchase_amount=purchase.total_amount,
                paid_amount=purchase.paid_amount,
            )

        purchase.status = status
        self.db.commit()
        self.db.refresh(purchase)

        return purchase

    def record_payment(
        self,
        purchase_id: str,
        amount: Decimal,
        payment_date: datetime | None = None,
        notes: str | None = None,
    ) -> Purchase:
        """Record a payment for a purchase.

        Args:
            purchase_id: Purchase ID
            amount: Payment amount
            payment_date: Payment date (defaults to now)
            notes: Payment notes

        Returns:
            Updated purchase

        Raises:
            ResourceNotFoundError: If purchase not found
            ValidationError: If payment is invalid
        """
        purchase = self.get_purchase(purchase_id)

        if amount <= 0:
            raise ValidationError("Payment amount must be greater than 0")

        remaining = purchase.total_amount - purchase.paid_amount
        if amount > remaining:
            raise ValidationError(f"Payment amount exceeds remaining balance of {remaining}")

        purchase.paid_amount += amount

        # Update payment status
        if purchase.paid_amount >= purchase.total_amount:
            purchase.payment_status = PaymentStatus.PAID.value
        elif purchase.paid_amount > 0:
            purchase.payment_status = PaymentStatus.PARTIAL.value

        # Update supplier outstanding balance
        supplier = self.supplier_service.get_supplier(purchase.supplier_id)
        supplier.outstanding_balance -= amount

        self.db.commit()
        self.db.refresh(purchase)

        return purchase

    def cancel_purchase(self, purchase_id: str, reason: str | None = None) -> Purchase:
        """Cancel a purchase order.

        Args:
            purchase_id: Purchase ID
            reason: Cancellation reason

        Returns:
            Cancelled purchase

        Raises:
            ResourceNotFoundError: If purchase not found
            ValidationError: If purchase cannot be cancelled
        """
        purchase = self.get_purchase(purchase_id)

        if purchase.status == PurchaseStatus.RECEIVED.value:
            raise ValidationError("Cannot cancel received purchase")
        if purchase.status == PurchaseStatus.CANCELLED.value:
            raise ValidationError("Purchase is already cancelled")

        purchase.status = PurchaseStatus.CANCELLED.value
        if reason:
            purchase.notes = f"{purchase.notes or ''}\nCancellation reason: {reason}".strip()

        self.db.commit()
        self.db.refresh(purchase)

        return purchase

    def get_purchase_summary(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict:
        """Get purchase summary statistics.

        Args:
            start_date: Start date for filtering
            end_date: End date for filtering

        Returns:
            Dictionary with purchase statistics
        """
        stmt = select(Purchase)

        if start_date:
            stmt = stmt.where(Purchase.purchase_date >= start_date)
        if end_date:
            stmt = stmt.where(Purchase.purchase_date <= end_date)

        purchases = self.db.execute(stmt).scalars().all()

        total_purchases = len(purchases)
        total_amount = sum(p.total_amount for p in purchases)
        total_paid = sum(p.paid_amount for p in purchases)
        total_outstanding = total_amount - total_paid

        status_counts = {}
        for status in PurchaseStatus:
            count = sum(1 for p in purchases if p.status == status.value)
            status_counts[status.value] = count

        return {
            "total_purchases": total_purchases,
            "total_amount": float(total_amount),
            "total_paid": float(total_paid),
            "total_outstanding": float(total_outstanding),
            "status_counts": status_counts,
        }

    def _generate_purchase_number(self) -> str:
        """Generate unique purchase number.

        Returns:
            Purchase number in format PO-YYYYMMDD-0001
        """
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"PO-{today}-"

        stmt = select(func.count(Purchase.id)).where(Purchase.purchase_number.like(f"{prefix}%"))
        count = self.db.execute(stmt).scalar() or 0

        return f"{prefix}{count + 1:04d}"

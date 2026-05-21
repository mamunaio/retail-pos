"""Customer management service."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from retail_pos.models import Customer, Sale, SaleStatus
from retail_pos.utils.exceptions import DuplicateResourceError, ResourceNotFoundError


class CustomerService:
    """Service for managing customers and loyalty programs."""

    @staticmethod
    def generate_customer_code(db: Session) -> str:
        """Generate a unique customer code.

        Format: CUST-NNNN
        Example: CUST-0001
        """
        # Get the last customer code
        last_customer = db.scalar(
            select(Customer)
            .where(Customer.customer_code.like("CUST-%"))
            .order_by(Customer.customer_code.desc())
            .limit(1)
        )

        if last_customer:
            # Extract the sequence number and increment
            last_seq = int(last_customer.customer_code.split("-")[-1])
            new_seq = last_seq + 1
        else:
            new_seq = 1

        return f"CUST-{new_seq:04d}"

    @staticmethod
    def create_customer(
        db: Session,
        name: str,
        phone: str | None = None,
        email: str | None = None,
        address: str | None = None,
        notes: str | None = None,
    ) -> Customer:
        """Create a new customer.

        Args:
            db: Database session
            name: Customer name
            phone: Phone number
            email: Email address
            address: Physical address
            notes: Additional notes

        Returns:
            Created Customer instance

        Raises:
            DuplicateResourceError: If phone already exists
        """
        # Check for duplicate phone
        if phone:
            existing = db.scalar(select(Customer).where(Customer.phone == phone))
            if existing:
                raise DuplicateResourceError("Customer", "phone", phone)

        customer_code = CustomerService.generate_customer_code(db)

        customer = Customer(
            customer_code=customer_code,
            name=name,
            phone=phone,
            email=email,
            address=address,
            notes=notes,
        )

        db.add(customer)
        db.flush()

        return customer

    @staticmethod
    def get_customer(db: Session, customer_id: str) -> Customer:
        """Get a customer by ID.

        Raises:
            ResourceNotFoundError: If customer not found
        """
        customer = db.get(Customer, customer_id)
        if not customer:
            raise ResourceNotFoundError("Customer", customer_id)
        return customer

    @staticmethod
    def get_customer_by_code(db: Session, customer_code: str) -> Customer | None:
        """Get a customer by customer code."""
        return db.scalar(
            select(Customer).where(Customer.customer_code == customer_code)
        )

    @staticmethod
    def get_customer_by_phone(db: Session, phone: str) -> Customer | None:
        """Get a customer by phone number."""
        return db.scalar(select(Customer).where(Customer.phone == phone))

    @staticmethod
    def search_customers(
        db: Session, query: str | None = None, active_only: bool = True, limit: int = 50
    ) -> list[Customer]:
        """Search customers by name, phone, or code."""
        stmt = select(Customer)

        if active_only:
            stmt = stmt.where(Customer.is_active == True)  # noqa: E712

        if query:
            search_pattern = f"%{query}%"
            stmt = stmt.where(
                (Customer.name.like(search_pattern))
                | (Customer.phone.like(search_pattern))
                | (Customer.customer_code.like(search_pattern))
            )

        stmt = stmt.order_by(Customer.name).limit(limit)

        return list(db.scalars(stmt).all())

    @staticmethod
    def update_customer(
        db: Session,
        customer_id: str,
        name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        address: str | None = None,
        notes: str | None = None,
        is_active: bool | None = None,
    ) -> Customer:
        """Update customer information.

        Raises:
            ResourceNotFoundError: If customer not found
            DuplicateResourceError: If phone already exists
        """
        customer = CustomerService.get_customer(db, customer_id)

        # Check for duplicate phone
        if phone and phone != customer.phone:
            existing = db.scalar(
                select(Customer).where(
                    Customer.phone == phone, Customer.id != customer_id
                )
            )
            if existing:
                raise DuplicateResourceError("Customer", "phone", phone)

        if name is not None:
            customer.name = name
        if phone is not None:
            customer.phone = phone
        if email is not None:
            customer.email = email
        if address is not None:
            customer.address = address
        if notes is not None:
            customer.notes = notes
        if is_active is not None:
            customer.is_active = is_active

        db.flush()
        return customer

    @staticmethod
    def add_loyalty_points(
        db: Session, customer_id: str, points: Decimal
    ) -> Customer:
        """Add loyalty points to a customer.

        Args:
            db: Database session
            customer_id: Customer ID
            points: Points to add (can be negative to deduct)

        Returns:
            Updated Customer instance
        """
        customer = CustomerService.get_customer(db, customer_id)
        customer.loyalty_points += points
        db.flush()
        return customer

    @staticmethod
    def update_purchase_stats(
        db: Session, customer_id: str, sale_amount: Decimal
    ) -> Customer:
        """Update customer purchase statistics after a sale.

        Args:
            db: Database session
            customer_id: Customer ID
            sale_amount: Sale total amount

        Returns:
            Updated Customer instance
        """
        customer = CustomerService.get_customer(db, customer_id)
        customer.total_purchases += sale_amount
        customer.purchase_count += 1

        # Award loyalty points (1 point per 100 BDT spent)
        points_earned = sale_amount / Decimal("100")
        customer.loyalty_points += points_earned

        db.flush()
        return customer

    @staticmethod
    def get_customer_purchase_history(
        db: Session, customer_id: str, limit: int = 50
    ) -> list[Sale]:
        """Get purchase history for a customer."""
        return list(
            db.scalars(
                select(Sale)
                .where(Sale.customer_id == customer_id)
                .order_by(Sale.created_at.desc())
                .limit(limit)
            ).all()
        )

    @staticmethod
    def get_customer_stats(db: Session, customer_id: str) -> dict:
        """Get customer statistics.

        Returns:
            Dictionary with customer stats
        """
        customer = CustomerService.get_customer(db, customer_id)

        # Get completed sales only
        completed_sales = db.scalars(
            select(Sale).where(
                Sale.customer_id == customer_id, Sale.status == SaleStatus.COMPLETED
            )
        ).all()

        # Calculate stats
        total_spent = sum(sale.total_amount for sale in completed_sales)
        avg_purchase = (
            total_spent / len(completed_sales) if completed_sales else Decimal("0.00")
        )

        # Get last purchase date
        last_purchase = None
        if completed_sales:
            last_purchase = max(sale.created_at for sale in completed_sales)

        return {
            "customer_id": customer.id,
            "customer_code": customer.customer_code,
            "name": customer.name,
            "total_purchases": float(customer.total_purchases),
            "purchase_count": customer.purchase_count,
            "loyalty_points": float(customer.loyalty_points),
            "average_purchase": float(avg_purchase),
            "last_purchase_date": last_purchase.isoformat() if last_purchase else None,
            "member_since": customer.created_at.isoformat(),
        }

    @staticmethod
    def get_top_customers(
        db: Session, limit: int = 10, by: str = "total_purchases"
    ) -> list[Customer]:
        """Get top customers by total purchases or purchase count.

        Args:
            db: Database session
            limit: Number of customers to return
            by: Sort by 'total_purchases' or 'purchase_count'

        Returns:
            List of top customers
        """
        stmt = select(Customer).where(Customer.is_active == True)  # noqa: E712

        if by == "purchase_count":
            stmt = stmt.order_by(Customer.purchase_count.desc())
        else:
            stmt = stmt.order_by(Customer.total_purchases.desc())

        stmt = stmt.limit(limit)

        return list(db.scalars(stmt).all())

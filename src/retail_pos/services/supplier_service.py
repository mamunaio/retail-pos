"""Supplier service for managing suppliers."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from retail_pos.models.supplier import Supplier
from retail_pos.utils.exceptions import ResourceNotFoundError, ValidationError

if TYPE_CHECKING:
    from datetime import datetime


class SupplierService:
    """Service for managing suppliers."""

    def __init__(self, db: Session) -> None:
        """Initialize supplier service.

        Args:
            db: Database session
        """
        self.db = db

    def create_supplier(
        self,
        name: str,
        phone: str | None = None,
        email: str | None = None,
        address: str | None = None,
        company_name: str | None = None,
        contact_person: str | None = None,
        payment_terms: str | None = None,
        credit_limit: Decimal = Decimal("0.00"),
        notes: str | None = None,
    ) -> Supplier:
        """Create a new supplier.

        Args:
            name: Supplier name
            phone: Phone number
            email: Email address
            address: Physical address
            company_name: Company name
            contact_person: Contact person name
            payment_terms: Payment terms (e.g., Net 30, COD)
            credit_limit: Credit limit
            notes: Additional notes

        Returns:
            Created supplier

        Raises:
            ValidationError: If validation fails
        """
        # Validate required fields
        if not name or not name.strip():
            raise ValidationError("Supplier name is required")

        # Generate supplier code
        supplier_code = self._generate_supplier_code()

        # Create supplier
        supplier = Supplier(
            supplier_code=supplier_code,
            name=name.strip(),
            phone=phone,
            email=email,
            address=address,
            company_name=company_name,
            contact_person=contact_person,
            payment_terms=payment_terms,
            credit_limit=credit_limit,
            notes=notes,
        )

        self.db.add(supplier)
        self.db.commit()
        self.db.refresh(supplier)

        return supplier

    def get_supplier(self, supplier_id: str) -> Supplier:
        """Get supplier by ID.

        Args:
            supplier_id: Supplier ID

        Returns:
            Supplier

        Raises:
            ResourceNotFoundError: If supplier not found
        """
        supplier = self.db.get(Supplier, supplier_id)
        if not supplier:
            raise ResourceNotFoundError("Supplier", supplier_id)
        return supplier

    def get_supplier_by_code(self, supplier_code: str) -> Supplier:
        """Get supplier by code.

        Args:
            supplier_code: Supplier code

        Returns:
            Supplier

        Raises:
            ResourceNotFoundError: If supplier not found
        """
        stmt = select(Supplier).where(Supplier.supplier_code == supplier_code)
        supplier = self.db.execute(stmt).scalar_one_or_none()
        if not supplier:
            raise ResourceNotFoundError("Supplier", supplier_code)
        return supplier

    def list_suppliers(
        self,
        active_only: bool = True,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Supplier]:
        """List suppliers with optional filtering.

        Args:
            active_only: Only return active suppliers
            search: Search term for name, phone, or code
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of suppliers
        """
        stmt = select(Supplier)

        if active_only:
            stmt = stmt.where(Supplier.is_active == True)  # noqa: E712

        if search:
            search_term = f"%{search}%"
            stmt = stmt.where(
                (Supplier.name.ilike(search_term))
                | (Supplier.supplier_code.ilike(search_term))
                | (Supplier.phone.ilike(search_term))
            )

        stmt = stmt.order_by(Supplier.name).limit(limit).offset(offset)
        result = self.db.execute(stmt)
        return list(result.scalars().all())

    def update_supplier(
        self,
        supplier_id: str,
        name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        address: str | None = None,
        company_name: str | None = None,
        contact_person: str | None = None,
        payment_terms: str | None = None,
        credit_limit: Decimal | None = None,
        is_active: bool | None = None,
        notes: str | None = None,
    ) -> Supplier:
        """Update supplier information.

        Args:
            supplier_id: Supplier ID
            name: New name
            phone: New phone
            email: New email
            address: New address
            company_name: New company name
            contact_person: New contact person
            payment_terms: New payment terms
            credit_limit: New credit limit
            is_active: New active status
            notes: New notes

        Returns:
            Updated supplier

        Raises:
            ResourceNotFoundError: If supplier not found
        """
        supplier = self.get_supplier(supplier_id)

        if name is not None:
            supplier.name = name.strip()
        if phone is not None:
            supplier.phone = phone
        if email is not None:
            supplier.email = email
        if address is not None:
            supplier.address = address
        if company_name is not None:
            supplier.company_name = company_name
        if contact_person is not None:
            supplier.contact_person = contact_person
        if payment_terms is not None:
            supplier.payment_terms = payment_terms
        if credit_limit is not None:
            supplier.credit_limit = credit_limit
        if is_active is not None:
            supplier.is_active = is_active
        if notes is not None:
            supplier.notes = notes

        self.db.commit()
        self.db.refresh(supplier)

        return supplier

    def update_supplier_stats(
        self,
        supplier_id: str,
        purchase_amount: Decimal,
        paid_amount: Decimal,
    ) -> None:
        """Update supplier purchase statistics.

        Args:
            supplier_id: Supplier ID
            purchase_amount: Purchase amount to add
            paid_amount: Amount paid
        """
        supplier = self.get_supplier(supplier_id)
        supplier.total_purchases += purchase_amount
        supplier.purchase_count += 1
        supplier.outstanding_balance += purchase_amount - paid_amount
        self.db.commit()

    def get_supplier_stats(self, supplier_id: str) -> dict:
        """Get supplier statistics.

        Args:
            supplier_id: Supplier ID

        Returns:
            Dictionary with supplier statistics
        """
        supplier = self.get_supplier(supplier_id)

        return {
            "supplier_id": supplier.id,
            "supplier_code": supplier.supplier_code,
            "name": supplier.name,
            "total_purchases": float(supplier.total_purchases),
            "purchase_count": supplier.purchase_count,
            "outstanding_balance": float(supplier.outstanding_balance),
            "credit_limit": float(supplier.credit_limit),
            "credit_available": float(supplier.credit_limit - supplier.outstanding_balance),
        }

    def get_top_suppliers(self, limit: int = 10) -> list[dict]:
        """Get top suppliers by purchase value.

        Args:
            limit: Number of suppliers to return

        Returns:
            List of supplier statistics
        """
        stmt = (
            select(Supplier)
            .where(Supplier.is_active == True)  # noqa: E712
            .order_by(Supplier.total_purchases.desc())
            .limit(limit)
        )
        suppliers = self.db.execute(stmt).scalars().all()

        return [
            {
                "supplier_id": s.id,
                "supplier_code": s.supplier_code,
                "name": s.name,
                "total_purchases": float(s.total_purchases),
                "purchase_count": s.purchase_count,
                "outstanding_balance": float(s.outstanding_balance),
            }
            for s in suppliers
        ]

    def _generate_supplier_code(self) -> str:
        """Generate unique supplier code.

        Returns:
            Supplier code in format SUP-0001, SUP-0002, etc.
        """
        stmt = select(func.count(Supplier.id))
        count = self.db.execute(stmt).scalar() or 0
        return f"SUP-{count + 1:04d}"

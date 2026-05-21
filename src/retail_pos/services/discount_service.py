"""Discount service for managing discounts and promotions."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from retail_pos.models.discount import Discount, DiscountScope, DiscountType, DiscountUsage
from retail_pos.utils.exceptions import ResourceNotFoundError, ValidationError

if TYPE_CHECKING:
    pass


class DiscountService:
    """Service for managing discounts and promotions."""

    def __init__(self, db: Session) -> None:
        """Initialize discount service.

        Args:
            db: Database session
        """
        self.db = db

    def create_discount(
        self,
        code: str,
        name: str,
        discount_type: str,
        discount_scope: str,
        discount_value: Decimal,
        valid_from: datetime,
        created_by: str,
        description: str | None = None,
        max_discount_amount: Decimal | None = None,
        buy_quantity: int | None = None,
        get_quantity: int | None = None,
        min_purchase_amount: Decimal = Decimal("0.00"),
        min_quantity: int = 0,
        category: str | None = None,
        product_ids: str | None = None,
        valid_until: datetime | None = None,
        usage_limit: int | None = None,
        usage_limit_per_customer: int | None = None,
        is_automatic: bool = False,
        requires_code: bool = True,
        is_stackable: bool = False,
        priority: int = 0,
        notes: str | None = None,
    ) -> Discount:
        """Create a new discount.

        Args:
            code: Discount/promo code
            name: Discount name
            discount_type: Type (percentage, fixed_amount, buy_x_get_y)
            discount_scope: Scope (order, category, product)
            discount_value: Discount value (percentage or amount)
            valid_from: Start date
            created_by: User ID who created
            description: Description
            max_discount_amount: Maximum discount amount
            buy_quantity: Buy X quantity
            get_quantity: Get Y quantity
            min_purchase_amount: Minimum purchase amount
            min_quantity: Minimum quantity
            category: Category for category-scoped
            product_ids: Product IDs for product-scoped
            valid_until: End date
            usage_limit: Total usage limit
            usage_limit_per_customer: Per customer limit
            is_automatic: Auto-apply
            requires_code: Requires code
            is_stackable: Can stack with others
            priority: Priority
            notes: Notes

        Returns:
            Created discount

        Raises:
            ValidationError: If validation fails
        """
        # Validate
        if not code or not code.strip():
            raise ValidationError("Discount code is required")
        if not name or not name.strip():
            raise ValidationError("Discount name is required")

        # Check if code already exists
        existing = self.db.scalar(select(Discount).where(Discount.code == code.upper()))
        if existing:
            raise ValidationError(f"Discount code '{code}' already exists")

        # Validate discount type
        if discount_type not in [t.value for t in DiscountType]:
            raise ValidationError(f"Invalid discount type: {discount_type}")

        # Validate discount scope
        if discount_scope not in [s.value for s in DiscountScope]:
            raise ValidationError(f"Invalid discount scope: {discount_scope}")

        # Validate buy_x_get_y
        if discount_type == DiscountType.BUY_X_GET_Y.value:
            if not buy_quantity or not get_quantity:
                raise ValidationError("buy_quantity and get_quantity required for buy_x_get_y")
            if buy_quantity <= 0 or get_quantity <= 0:
                raise ValidationError("buy_quantity and get_quantity must be positive")

        # Validate percentage
        if discount_type == DiscountType.PERCENTAGE.value:
            if discount_value <= 0 or discount_value > 100:
                raise ValidationError("Percentage must be between 0 and 100")

        # Validate scope requirements
        if discount_scope == DiscountScope.CATEGORY.value and not category:
            raise ValidationError("Category required for category-scoped discount")
        if discount_scope == DiscountScope.PRODUCT.value and not product_ids:
            raise ValidationError("Product IDs required for product-scoped discount")

        # Create discount
        discount = Discount(
            code=code.upper(),
            name=name.strip(),
            description=description,
            discount_type=discount_type,
            discount_scope=discount_scope,
            discount_value=discount_value,
            max_discount_amount=max_discount_amount,
            buy_quantity=buy_quantity,
            get_quantity=get_quantity,
            min_purchase_amount=min_purchase_amount,
            min_quantity=min_quantity,
            category=category,
            product_ids=product_ids,
            valid_from=valid_from,
            valid_until=valid_until,
            usage_limit=usage_limit,
            usage_limit_per_customer=usage_limit_per_customer,
            is_automatic=is_automatic,
            requires_code=requires_code,
            is_stackable=is_stackable,
            priority=priority,
            created_by=created_by,
            notes=notes,
        )

        self.db.add(discount)
        self.db.commit()
        self.db.refresh(discount)

        return discount

    def get_discount(self, discount_id: str) -> Discount:
        """Get discount by ID.

        Args:
            discount_id: Discount ID

        Returns:
            Discount

        Raises:
            ResourceNotFoundError: If discount not found
        """
        discount = self.db.get(Discount, discount_id)
        if not discount:
            raise ResourceNotFoundError("Discount", discount_id)
        return discount

    def get_discount_by_code(self, code: str) -> Discount:
        """Get discount by code.

        Args:
            code: Discount code

        Returns:
            Discount

        Raises:
            ResourceNotFoundError: If discount not found
        """
        stmt = select(Discount).where(Discount.code == code.upper())
        discount = self.db.execute(stmt).scalar_one_or_none()
        if not discount:
            raise ResourceNotFoundError("Discount", code)
        return discount

    def list_discounts(
        self,
        active_only: bool = True,
        valid_only: bool = False,
        automatic_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Discount]:
        """List discounts with optional filtering.

        Args:
            active_only: Only return active discounts
            valid_only: Only return currently valid discounts
            automatic_only: Only return automatic discounts
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of discounts
        """
        stmt = select(Discount)

        if active_only:
            stmt = stmt.where(Discount.is_active == True)  # noqa: E712

        if automatic_only:
            stmt = stmt.where(Discount.is_automatic == True)  # noqa: E712

        if valid_only:
            now = datetime.now()
            stmt = stmt.where(
                Discount.valid_from <= now,
                (Discount.valid_until.is_(None)) | (Discount.valid_until >= now),
            )

        stmt = stmt.order_by(Discount.priority.desc(), Discount.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)

        result = self.db.execute(stmt)
        return list(result.scalars().all())

    def update_discount(
        self,
        discount_id: str,
        name: str | None = None,
        description: str | None = None,
        discount_value: Decimal | None = None,
        max_discount_amount: Decimal | None = None,
        min_purchase_amount: Decimal | None = None,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        usage_limit: int | None = None,
        usage_limit_per_customer: int | None = None,
        is_active: bool | None = None,
        is_automatic: bool | None = None,
        is_stackable: bool | None = None,
        priority: int | None = None,
        notes: str | None = None,
    ) -> Discount:
        """Update discount.

        Args:
            discount_id: Discount ID
            name: New name
            description: New description
            discount_value: New value
            max_discount_amount: New max amount
            min_purchase_amount: New min amount
            valid_from: New start date
            valid_until: New end date
            usage_limit: New usage limit
            usage_limit_per_customer: New per customer limit
            is_active: New active status
            is_automatic: New automatic status
            is_stackable: New stackable status
            priority: New priority
            notes: New notes

        Returns:
            Updated discount

        Raises:
            ResourceNotFoundError: If discount not found
        """
        discount = self.get_discount(discount_id)

        if name is not None:
            discount.name = name.strip()
        if description is not None:
            discount.description = description
        if discount_value is not None:
            discount.discount_value = discount_value
        if max_discount_amount is not None:
            discount.max_discount_amount = max_discount_amount
        if min_purchase_amount is not None:
            discount.min_purchase_amount = min_purchase_amount
        if valid_from is not None:
            discount.valid_from = valid_from
        if valid_until is not None:
            discount.valid_until = valid_until
        if usage_limit is not None:
            discount.usage_limit = usage_limit
        if usage_limit_per_customer is not None:
            discount.usage_limit_per_customer = usage_limit_per_customer
        if is_active is not None:
            discount.is_active = is_active
        if is_automatic is not None:
            discount.is_automatic = is_automatic
        if is_stackable is not None:
            discount.is_stackable = is_stackable
        if priority is not None:
            discount.priority = priority
        if notes is not None:
            discount.notes = notes

        self.db.commit()
        self.db.refresh(discount)

        return discount

    def validate_discount(
        self,
        discount: Discount,
        order_amount: Decimal,
        customer_id: str | None = None,
        category: str | None = None,
        product_ids: list[str] | None = None,
    ) -> tuple[bool, str | None]:
        """Validate if discount can be applied.

        Args:
            discount: Discount to validate
            order_amount: Order amount
            customer_id: Customer ID
            category: Order category
            product_ids: Product IDs in order

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if discount is valid
        if not discount.is_valid():
            return False, "Discount is not valid or has expired"

        # Check minimum purchase amount
        if order_amount < discount.min_purchase_amount:
            return False, f"Minimum purchase amount is ৳{discount.min_purchase_amount}"

        # Check per-customer usage limit
        if customer_id and discount.usage_limit_per_customer:
            usage_count = self.db.scalar(
                select(func.count(DiscountUsage.id)).where(
                    DiscountUsage.discount_id == discount.id,
                    DiscountUsage.customer_id == customer_id,
                )
            )
            if usage_count and usage_count >= discount.usage_limit_per_customer:
                return False, "You have reached the usage limit for this discount"

        # Check scope
        if discount.discount_scope == DiscountScope.CATEGORY.value:
            if not category or category != discount.category:
                return False, f"Discount only applies to {discount.category} category"

        if discount.discount_scope == DiscountScope.PRODUCT.value:
            if not product_ids or not discount.product_ids:
                return False, "Discount only applies to specific products"
            allowed_products = set(discount.product_ids.split(","))
            if not any(pid in allowed_products for pid in product_ids):
                return False, "Discount does not apply to products in your order"

        return True, None

    def calculate_discount(
        self,
        discount: Discount,
        amount: Decimal,
        quantity: int = 1,
    ) -> Decimal:
        """Calculate discount amount.

        Args:
            discount: Discount to apply
            amount: Amount to discount
            quantity: Quantity (for buy_x_get_y)

        Returns:
            Discount amount
        """
        if discount.discount_type == DiscountType.PERCENTAGE.value:
            discount_amount = amount * (discount.discount_value / Decimal("100"))
            if discount.max_discount_amount:
                discount_amount = min(discount_amount, discount.max_discount_amount)
            return discount_amount

        elif discount.discount_type == DiscountType.FIXED_AMOUNT.value:
            return min(discount.discount_value, amount)

        elif discount.discount_type == DiscountType.BUY_X_GET_Y.value:
            if discount.buy_quantity and discount.get_quantity:
                # Calculate how many free items customer gets
                sets = quantity // discount.buy_quantity
                free_items = sets * discount.get_quantity
                # Discount = price of free items
                item_price = amount / Decimal(str(quantity))
                return item_price * Decimal(str(free_items))

        return Decimal("0.00")

    def record_usage(
        self,
        discount_id: str,
        sale_id: str,
        discount_amount: Decimal,
        original_amount: Decimal,
        customer_id: str | None = None,
    ) -> DiscountUsage:
        """Record discount usage.

        Args:
            discount_id: Discount ID
            sale_id: Sale ID
            discount_amount: Discount amount applied
            original_amount: Original amount
            customer_id: Customer ID

        Returns:
            Discount usage record
        """
        discount = self.get_discount(discount_id)
        discount.usage_count += 1

        usage = DiscountUsage(
            discount_id=discount_id,
            sale_id=sale_id,
            customer_id=customer_id,
            discount_amount=discount_amount,
            original_amount=original_amount,
        )

        self.db.add(usage)
        self.db.commit()
        self.db.refresh(usage)

        return usage

    def get_discount_stats(self, discount_id: str) -> dict:
        """Get discount statistics.

        Args:
            discount_id: Discount ID

        Returns:
            Dictionary with discount statistics
        """
        discount = self.get_discount(discount_id)

        total_discount_amount = self.db.scalar(
            select(func.sum(DiscountUsage.discount_amount)).where(
                DiscountUsage.discount_id == discount_id
            )
        ) or Decimal("0.00")

        total_original_amount = self.db.scalar(
            select(func.sum(DiscountUsage.original_amount)).where(
                DiscountUsage.discount_id == discount_id
            )
        ) or Decimal("0.00")

        unique_customers = self.db.scalar(
            select(func.count(func.distinct(DiscountUsage.customer_id))).where(
                DiscountUsage.discount_id == discount_id,
                DiscountUsage.customer_id.is_not(None),
            )
        ) or 0

        return {
            "discount_id": discount.id,
            "code": discount.code,
            "name": discount.name,
            "usage_count": discount.usage_count,
            "usage_limit": discount.usage_limit,
            "total_discount_amount": float(total_discount_amount),
            "total_original_amount": float(total_original_amount),
            "unique_customers": unique_customers,
            "is_active": discount.is_active,
            "is_valid": discount.is_valid(),
        }

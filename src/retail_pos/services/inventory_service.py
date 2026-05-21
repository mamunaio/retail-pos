"""Inventory management service."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from retail_pos.models import Inventory, Product, StockMovement, StockMovementType


class InventoryService:
    """Service for managing inventory and stock movements."""

    @staticmethod
    def get_or_create_inventory(db: Session, product_id: str) -> Inventory:
        """Get existing inventory record or create a new one for a product."""
        inventory = db.scalar(
            select(Inventory).where(Inventory.product_id == product_id)
        )
        if not inventory:
            inventory = Inventory(
                product_id=product_id,
                quantity=Decimal("0.00"),
                reorder_level=Decimal("10.00"),
            )
            db.add(inventory)
            db.flush()
        return inventory

    @staticmethod
    def adjust_stock(
        db: Session,
        product_id: str,
        quantity_change: Decimal,
        movement_type: StockMovementType,
        user_id: str | None = None,
        reference_id: str | None = None,
        notes: str | None = None,
    ) -> tuple[Inventory, StockMovement]:
        """Adjust stock level and record the movement.

        Args:
            db: Database session
            product_id: Product ID
            quantity_change: Amount to add (positive) or subtract (negative)
            movement_type: Type of stock movement
            user_id: User who made the change
            reference_id: Related record ID (sale, purchase, etc.)
            notes: Optional notes

        Returns:
            Tuple of (updated inventory, created movement record)
        """
        inventory = InventoryService.get_or_create_inventory(db, product_id)

        # Update quantity
        new_quantity = inventory.quantity + quantity_change
        if new_quantity < 0:
            raise ValueError(
                f"Insufficient stock. Available: {inventory.quantity}, "
                f"Requested: {abs(quantity_change)}"
            )

        inventory.quantity = new_quantity

        # Record movement
        movement = StockMovement(
            inventory_id=inventory.id,
            movement_type=movement_type,
            quantity_change=quantity_change,
            quantity_after=new_quantity,
            reference_id=reference_id,
            user_id=user_id,
            notes=notes,
        )
        db.add(movement)
        db.flush()

        return inventory, movement

    @staticmethod
    def set_stock(
        db: Session,
        product_id: str,
        new_quantity: Decimal,
        user_id: str | None = None,
        notes: str | None = None,
    ) -> tuple[Inventory, StockMovement]:
        """Set stock to a specific quantity (used for initial stock or corrections).

        Args:
            db: Database session
            product_id: Product ID
            new_quantity: New stock quantity
            user_id: User who made the change
            notes: Optional notes

        Returns:
            Tuple of (updated inventory, created movement record)
        """
        inventory = InventoryService.get_or_create_inventory(db, product_id)
        quantity_change = new_quantity - inventory.quantity

        return InventoryService.adjust_stock(
            db=db,
            product_id=product_id,
            quantity_change=quantity_change,
            movement_type=StockMovementType.ADJUSTMENT,
            user_id=user_id,
            notes=notes or "Stock level set",
        )

    @staticmethod
    def get_low_stock_products(db: Session) -> list[tuple[Product, Inventory]]:
        """Get all products with low stock levels.

        Returns:
            List of (Product, Inventory) tuples where stock is below reorder level
        """
        results = db.execute(
            select(Product, Inventory)
            .join(Inventory, Product.id == Inventory.product_id)
            .where(
                Inventory.low_stock_alert == True,  # noqa: E712
                Inventory.quantity <= Inventory.reorder_level,
                Product.is_active == True,  # noqa: E712
            )
            .order_by(Inventory.quantity)
        ).all()

        return [(row[0], row[1]) for row in results]

    @staticmethod
    def get_stock_movements(
        db: Session,
        product_id: str | None = None,
        movement_type: StockMovementType | None = None,
        limit: int = 100,
    ) -> list[StockMovement]:
        """Get stock movement history.

        Args:
            db: Database session
            product_id: Filter by product ID (optional)
            movement_type: Filter by movement type (optional)
            limit: Maximum number of records to return

        Returns:
            List of stock movements
        """
        query = select(StockMovement).options(
            joinedload(StockMovement.inventory).joinedload(Inventory.product),
            joinedload(StockMovement.user),
        )

        if product_id:
            query = query.join(Inventory).where(Inventory.product_id == product_id)

        if movement_type:
            query = query.where(StockMovement.movement_type == movement_type)

        query = query.order_by(StockMovement.created_at.desc()).limit(limit)

        return list(db.scalars(query).unique().all())

    @staticmethod
    def get_inventory_with_product(db: Session, product_id: str) -> tuple[Product, Inventory] | None:
        """Get product with its inventory information.

        Args:
            db: Database session
            product_id: Product ID

        Returns:
            Tuple of (Product, Inventory) or None if not found
        """
        result = db.execute(
            select(Product, Inventory)
            .outerjoin(Inventory, Product.id == Inventory.product_id)
            .where(Product.id == product_id)
        ).first()

        if not result:
            return None

        product, inventory = result
        if not inventory:
            # Create inventory record if it doesn't exist
            inventory = InventoryService.get_or_create_inventory(db, product_id)
            db.commit()

        return product, inventory

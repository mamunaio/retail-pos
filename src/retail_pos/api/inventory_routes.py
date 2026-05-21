"""API routes for inventory management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from retail_pos.api.schemas import (
    InventoryResponse,
    LowStockItem,
    ProductWithInventory,
    StockAdjustmentRequest,
    StockMovementResponse,
    StockSetRequest,
)
from retail_pos.db import get_db
from retail_pos.models import StockMovementType
from retail_pos.services.inventory_service import InventoryService

router = APIRouter()


@router.get("/inventory", response_model=list[ProductWithInventory])
def list_inventory(db: Annotated[Session, Depends(get_db)]) -> list[dict]:
    """List all products with their inventory levels."""
    from sqlalchemy import select

    from retail_pos.models import Inventory, Product

    results = db.execute(
        select(Product, Inventory)
        .outerjoin(Inventory, Product.id == Inventory.product_id)
        .where(Product.is_active == True)  # noqa: E712
        .order_by(Product.name)
    ).all()

    products_with_inventory = []
    for product, inventory in results:
        if not inventory:
            # Create inventory if it doesn't exist
            inventory = InventoryService.get_or_create_inventory(db, product.id)
            db.commit()

        product_dict = {
            **product.__dict__,
            "inventory": inventory,
        }
        products_with_inventory.append(product_dict)

    return products_with_inventory


@router.get("/inventory/low-stock", response_model=list[LowStockItem])
def get_low_stock(db: Annotated[Session, Depends(get_db)]) -> list[dict]:
    """Get products with low stock levels."""
    low_stock_items = InventoryService.get_low_stock_products(db)

    return [{"product": product, "inventory": inventory} for product, inventory in low_stock_items]


@router.get("/inventory/{product_id}", response_model=InventoryResponse)
def get_inventory(product_id: str, db: Annotated[Session, Depends(get_db)]) -> InventoryResponse:
    """Get inventory for a specific product."""
    result = InventoryService.get_inventory_with_product(db, product_id)
    if not result:
        raise HTTPException(status_code=404, detail="Product not found")

    _, inventory = result
    return inventory


@router.post("/inventory/adjust", response_model=InventoryResponse)
def adjust_stock(
    data: StockAdjustmentRequest, db: Annotated[Session, Depends(get_db)]
) -> InventoryResponse:
    """Adjust stock level (add or subtract)."""
    try:
        movement_type = StockMovementType(data.movement_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid movement type. Must be one of: {', '.join(StockMovementType)}",
        )

    try:
        inventory, _ = InventoryService.adjust_stock(
            db=db,
            product_id=data.product_id,
            quantity_change=data.quantity_change,
            movement_type=movement_type,
            notes=data.notes,
        )
        db.commit()
        return inventory
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/inventory/set", response_model=InventoryResponse)
def set_stock(
    data: StockSetRequest, db: Annotated[Session, Depends(get_db)]
) -> InventoryResponse:
    """Set stock to a specific quantity."""
    try:
        inventory, _ = InventoryService.set_stock(
            db=db,
            product_id=data.product_id,
            new_quantity=data.new_quantity,
            notes=data.notes,
        )
        db.commit()
        return inventory
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/inventory/{product_id}/movements", response_model=list[StockMovementResponse])
def get_stock_movements(
    product_id: str, db: Annotated[Session, Depends(get_db)], limit: int = 50
) -> list[StockMovementResponse]:
    """Get stock movement history for a product."""
    movements = InventoryService.get_stock_movements(db, product_id=product_id, limit=limit)
    return movements


@router.get("/stock-movements", response_model=list[StockMovementResponse])
def list_all_stock_movements(
    db: Annotated[Session, Depends(get_db)], limit: int = 100
) -> list[StockMovementResponse]:
    """Get all stock movements (recent first)."""
    movements = InventoryService.get_stock_movements(db, limit=limit)
    return movements

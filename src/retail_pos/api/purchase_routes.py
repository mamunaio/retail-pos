"""API routes for purchase management."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from retail_pos.api.schemas import (
    PurchaseCancelRequest,
    PurchaseCreate,
    PurchaseItemResponse,
    PurchasePaymentRequest,
    PurchaseResponse,
    PurchaseStatusUpdate,
    PurchaseSummaryResponse,
)
from retail_pos.db.session import get_db
from retail_pos.services.purchase_service import PurchaseService
from retail_pos.utils.exceptions import ResourceNotFoundError, ValidationError

router = APIRouter()


@router.post("/purchases", response_model=PurchaseResponse, status_code=status.HTTP_201_CREATED)
def create_purchase(
    purchase_data: PurchaseCreate,
    created_by: str = Query(..., description="User ID who is creating the purchase"),
    db: Session = Depends(get_db),
) -> PurchaseResponse:
    """Create a new purchase order."""
    try:
        service = PurchaseService(db)
        
        # Convert items to dict format
        items = [
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_cost": item.unit_cost,
                "notes": item.notes,
            }
            for item in purchase_data.items
        ]
        
        purchase = service.create_purchase(
            supplier_id=purchase_data.supplier_id,
            items=items,
            created_by=created_by,
            purchase_date=purchase_data.purchase_date,
            expected_delivery_date=purchase_data.expected_delivery_date,
            tax_amount=purchase_data.tax_amount,
            shipping_cost=purchase_data.shipping_cost,
            discount_amount=purchase_data.discount_amount,
            reference_number=purchase_data.reference_number,
            notes=purchase_data.notes,
        )
        
        # Build response
        return PurchaseResponse(
            id=purchase.id,
            purchase_number=purchase.purchase_number,
            supplier_id=purchase.supplier_id,
            supplier_name=purchase.supplier.name,
            purchase_date=purchase.purchase_date,
            expected_delivery_date=purchase.expected_delivery_date,
            received_date=purchase.received_date,
            subtotal=purchase.subtotal,
            tax_amount=purchase.tax_amount,
            shipping_cost=purchase.shipping_cost,
            discount_amount=purchase.discount_amount,
            total_amount=purchase.total_amount,
            paid_amount=purchase.paid_amount,
            status=purchase.status,
            payment_status=purchase.payment_status,
            reference_number=purchase.reference_number,
            notes=purchase.notes,
            created_by=purchase.created_by,
            received_by=purchase.received_by,
            created_at=purchase.created_at,
            items=[PurchaseItemResponse.model_validate(item) for item in purchase.items],
        )
    except (ValidationError, ResourceNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/purchases", response_model=list[PurchaseResponse])
def list_purchases(
    supplier_id: str | None = Query(None, description="Filter by supplier"),
    status: str | None = Query(None, description="Filter by status"),
    payment_status: str | None = Query(None, description="Filter by payment status"),
    start_date: datetime | None = Query(None, description="Filter by start date"),
    end_date: datetime | None = Query(None, description="Filter by end date"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[PurchaseResponse]:
    """List purchases with optional filtering."""
    service = PurchaseService(db)
    purchases = service.list_purchases(
        supplier_id=supplier_id,
        status=status,
        payment_status=payment_status,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    
    return [
        PurchaseResponse(
            id=p.id,
            purchase_number=p.purchase_number,
            supplier_id=p.supplier_id,
            supplier_name=p.supplier.name,
            purchase_date=p.purchase_date,
            expected_delivery_date=p.expected_delivery_date,
            received_date=p.received_date,
            subtotal=p.subtotal,
            tax_amount=p.tax_amount,
            shipping_cost=p.shipping_cost,
            discount_amount=p.discount_amount,
            total_amount=p.total_amount,
            paid_amount=p.paid_amount,
            status=p.status,
            payment_status=p.payment_status,
            reference_number=p.reference_number,
            notes=p.notes,
            created_by=p.created_by,
            received_by=p.received_by,
            created_at=p.created_at,
            items=[PurchaseItemResponse.model_validate(item) for item in p.items],
        )
        for p in purchases
    ]


@router.get("/purchases/{purchase_id}", response_model=PurchaseResponse)
def get_purchase(
    purchase_id: str,
    db: Session = Depends(get_db),
) -> PurchaseResponse:
    """Get purchase by ID."""
    try:
        service = PurchaseService(db)
        purchase = service.get_purchase(purchase_id)
        
        return PurchaseResponse(
            id=purchase.id,
            purchase_number=purchase.purchase_number,
            supplier_id=purchase.supplier_id,
            supplier_name=purchase.supplier.name,
            purchase_date=purchase.purchase_date,
            expected_delivery_date=purchase.expected_delivery_date,
            received_date=purchase.received_date,
            subtotal=purchase.subtotal,
            tax_amount=purchase.tax_amount,
            shipping_cost=purchase.shipping_cost,
            discount_amount=purchase.discount_amount,
            total_amount=purchase.total_amount,
            paid_amount=purchase.paid_amount,
            status=purchase.status,
            payment_status=purchase.payment_status,
            reference_number=purchase.reference_number,
            notes=purchase.notes,
            created_by=purchase.created_by,
            received_by=purchase.received_by,
            created_at=purchase.created_at,
            items=[PurchaseItemResponse.model_validate(item) for item in purchase.items],
        )
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/purchases/{purchase_id}/status", response_model=PurchaseResponse)
def update_purchase_status(
    purchase_id: str,
    status_data: PurchaseStatusUpdate,
    db: Session = Depends(get_db),
) -> PurchaseResponse:
    """Update purchase status."""
    try:
        service = PurchaseService(db)
        purchase = service.update_purchase_status(
            purchase_id=purchase_id,
            status=status_data.status,
            received_by=status_data.received_by,
        )
        
        return PurchaseResponse(
            id=purchase.id,
            purchase_number=purchase.purchase_number,
            supplier_id=purchase.supplier_id,
            supplier_name=purchase.supplier.name,
            purchase_date=purchase.purchase_date,
            expected_delivery_date=purchase.expected_delivery_date,
            received_date=purchase.received_date,
            subtotal=purchase.subtotal,
            tax_amount=purchase.tax_amount,
            shipping_cost=purchase.shipping_cost,
            discount_amount=purchase.discount_amount,
            total_amount=purchase.total_amount,
            paid_amount=purchase.paid_amount,
            status=purchase.status,
            payment_status=purchase.payment_status,
            reference_number=purchase.reference_number,
            notes=purchase.notes,
            created_by=purchase.created_by,
            received_by=purchase.received_by,
            created_at=purchase.created_at,
            items=[PurchaseItemResponse.model_validate(item) for item in purchase.items],
        )
    except (ResourceNotFoundError, ValidationError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/purchases/{purchase_id}/payments", response_model=PurchaseResponse)
def record_payment(
    purchase_id: str,
    payment_data: PurchasePaymentRequest,
    db: Session = Depends(get_db),
) -> PurchaseResponse:
    """Record a payment for a purchase."""
    try:
        service = PurchaseService(db)
        purchase = service.record_payment(
            purchase_id=purchase_id,
            amount=payment_data.amount,
            payment_date=payment_data.payment_date,
            notes=payment_data.notes,
        )
        
        return PurchaseResponse(
            id=purchase.id,
            purchase_number=purchase.purchase_number,
            supplier_id=purchase.supplier_id,
            supplier_name=purchase.supplier.name,
            purchase_date=purchase.purchase_date,
            expected_delivery_date=purchase.expected_delivery_date,
            received_date=purchase.received_date,
            subtotal=purchase.subtotal,
            tax_amount=purchase.tax_amount,
            shipping_cost=purchase.shipping_cost,
            discount_amount=purchase.discount_amount,
            total_amount=purchase.total_amount,
            paid_amount=purchase.paid_amount,
            status=purchase.status,
            payment_status=purchase.payment_status,
            reference_number=purchase.reference_number,
            notes=purchase.notes,
            created_by=purchase.created_by,
            received_by=purchase.received_by,
            created_at=purchase.created_at,
            items=[PurchaseItemResponse.model_validate(item) for item in purchase.items],
        )
    except (ResourceNotFoundError, ValidationError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/purchases/{purchase_id}/cancel", response_model=PurchaseResponse)
def cancel_purchase(
    purchase_id: str,
    cancel_data: PurchaseCancelRequest,
    db: Session = Depends(get_db),
) -> PurchaseResponse:
    """Cancel a purchase order."""
    try:
        service = PurchaseService(db)
        purchase = service.cancel_purchase(
            purchase_id=purchase_id,
            reason=cancel_data.reason,
        )
        
        return PurchaseResponse(
            id=purchase.id,
            purchase_number=purchase.purchase_number,
            supplier_id=purchase.supplier_id,
            supplier_name=purchase.supplier.name,
            purchase_date=purchase.purchase_date,
            expected_delivery_date=purchase.expected_delivery_date,
            received_date=purchase.received_date,
            subtotal=purchase.subtotal,
            tax_amount=purchase.tax_amount,
            shipping_cost=purchase.shipping_cost,
            discount_amount=purchase.discount_amount,
            total_amount=purchase.total_amount,
            paid_amount=purchase.paid_amount,
            status=purchase.status,
            payment_status=purchase.payment_status,
            reference_number=purchase.reference_number,
            notes=purchase.notes,
            created_by=purchase.created_by,
            received_by=purchase.received_by,
            created_at=purchase.created_at,
            items=[PurchaseItemResponse.model_validate(item) for item in purchase.items],
        )
    except (ResourceNotFoundError, ValidationError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/purchases/reports/summary", response_model=PurchaseSummaryResponse)
def get_purchase_summary(
    start_date: datetime | None = Query(None, description="Start date for filtering"),
    end_date: datetime | None = Query(None, description="End date for filtering"),
    db: Session = Depends(get_db),
) -> PurchaseSummaryResponse:
    """Get purchase summary statistics."""
    service = PurchaseService(db)
    summary = service.get_purchase_summary(
        start_date=start_date,
        end_date=end_date,
    )
    return PurchaseSummaryResponse(**summary)

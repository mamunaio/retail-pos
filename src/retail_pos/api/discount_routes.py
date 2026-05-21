"""API routes for discount management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from retail_pos.api.schemas import (
    DiscountCreate,
    DiscountResponse,
    DiscountStatsResponse,
    DiscountUpdate,
    DiscountValidateRequest,
    DiscountValidateResponse,
)
from retail_pos.db.session import get_db
from retail_pos.services.discount_service import DiscountService
from retail_pos.utils.exceptions import ResourceNotFoundError, ValidationError

router = APIRouter()


@router.post("/discounts", response_model=DiscountResponse, status_code=status.HTTP_201_CREATED)
def create_discount(
    discount_data: DiscountCreate,
    created_by: str = Query(..., description="User ID who is creating the discount"),
    db: Session = Depends(get_db),
) -> DiscountResponse:
    """Create a new discount."""
    try:
        service = DiscountService(db)
        discount = service.create_discount(
            code=discount_data.code,
            name=discount_data.name,
            discount_type=discount_data.discount_type,
            discount_scope=discount_data.discount_scope,
            discount_value=discount_data.discount_value,
            valid_from=discount_data.valid_from,
            created_by=created_by,
            description=discount_data.description,
            max_discount_amount=discount_data.max_discount_amount,
            buy_quantity=discount_data.buy_quantity,
            get_quantity=discount_data.get_quantity,
            min_purchase_amount=discount_data.min_purchase_amount,
            min_quantity=discount_data.min_quantity,
            category=discount_data.category,
            product_ids=discount_data.product_ids,
            valid_until=discount_data.valid_until,
            usage_limit=discount_data.usage_limit,
            usage_limit_per_customer=discount_data.usage_limit_per_customer,
            is_automatic=discount_data.is_automatic,
            requires_code=discount_data.requires_code,
            is_stackable=discount_data.is_stackable,
            priority=discount_data.priority,
            notes=discount_data.notes,
        )
        return DiscountResponse.model_validate(discount)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/discounts", response_model=list[DiscountResponse])
def list_discounts(
    active_only: bool = Query(True, description="Only return active discounts"),
    valid_only: bool = Query(False, description="Only return currently valid discounts"),
    automatic_only: bool = Query(False, description="Only return automatic discounts"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[DiscountResponse]:
    """List discounts with optional filtering."""
    service = DiscountService(db)
    discounts = service.list_discounts(
        active_only=active_only,
        valid_only=valid_only,
        automatic_only=automatic_only,
        limit=limit,
        offset=offset,
    )
    return [DiscountResponse.model_validate(d) for d in discounts]


@router.get("/discounts/{discount_id}", response_model=DiscountResponse)
def get_discount(
    discount_id: str,
    db: Session = Depends(get_db),
) -> DiscountResponse:
    """Get discount by ID."""
    try:
        service = DiscountService(db)
        discount = service.get_discount(discount_id)
        return DiscountResponse.model_validate(discount)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/discounts/code/{code}", response_model=DiscountResponse)
def get_discount_by_code(
    code: str,
    db: Session = Depends(get_db),
) -> DiscountResponse:
    """Get discount by code."""
    try:
        service = DiscountService(db)
        discount = service.get_discount_by_code(code)
        return DiscountResponse.model_validate(discount)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/discounts/{discount_id}", response_model=DiscountResponse)
def update_discount(
    discount_id: str,
    discount_data: DiscountUpdate,
    db: Session = Depends(get_db),
) -> DiscountResponse:
    """Update discount."""
    try:
        service = DiscountService(db)
        discount = service.update_discount(
            discount_id=discount_id,
            name=discount_data.name,
            description=discount_data.description,
            discount_value=discount_data.discount_value,
            max_discount_amount=discount_data.max_discount_amount,
            min_purchase_amount=discount_data.min_purchase_amount,
            valid_from=discount_data.valid_from,
            valid_until=discount_data.valid_until,
            usage_limit=discount_data.usage_limit,
            usage_limit_per_customer=discount_data.usage_limit_per_customer,
            is_active=discount_data.is_active,
            is_automatic=discount_data.is_automatic,
            is_stackable=discount_data.is_stackable,
            priority=discount_data.priority,
            notes=discount_data.notes,
        )
        return DiscountResponse.model_validate(discount)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/discounts/validate", response_model=DiscountValidateResponse)
def validate_discount(
    validate_data: DiscountValidateRequest,
    db: Session = Depends(get_db),
) -> DiscountValidateResponse:
    """Validate if a discount code can be applied."""
    try:
        service = DiscountService(db)
        discount = service.get_discount_by_code(validate_data.code)

        is_valid, error_message = service.validate_discount(
            discount=discount,
            order_amount=validate_data.order_amount,
            customer_id=validate_data.customer_id,
            category=validate_data.category,
            product_ids=validate_data.product_ids,
        )

        if is_valid:
            discount_amount = service.calculate_discount(
                discount=discount,
                amount=validate_data.order_amount,
            )
            return DiscountValidateResponse(
                is_valid=True,
                discount=DiscountResponse.model_validate(discount),
                discount_amount=discount_amount,
                error_message=None,
            )
        else:
            return DiscountValidateResponse(
                is_valid=False,
                discount=None,
                discount_amount=None,
                error_message=error_message,
            )
    except ResourceNotFoundError:
        return DiscountValidateResponse(
            is_valid=False,
            discount=None,
            discount_amount=None,
            error_message="Invalid discount code",
        )


@router.get("/discounts/{discount_id}/stats", response_model=DiscountStatsResponse)
def get_discount_stats(
    discount_id: str,
    db: Session = Depends(get_db),
) -> DiscountStatsResponse:
    """Get discount statistics."""
    try:
        service = DiscountService(db)
        stats = service.get_discount_stats(discount_id)
        return DiscountStatsResponse(**stats)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

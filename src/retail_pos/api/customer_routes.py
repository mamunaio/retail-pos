"""API routes for customer management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from retail_pos.api.schemas import (
    CustomerCreate,
    CustomerResponse,
    CustomerStatsResponse,
    CustomerUpdate,
    LoyaltyPointsRequest,
    SaleResponse,
)
from retail_pos.db import get_db
from retail_pos.services.customer_service import CustomerService
from retail_pos.utils.exceptions import DuplicateResourceError, ResourceNotFoundError

router = APIRouter()


@router.post("/customers", response_model=CustomerResponse, status_code=201)
def create_customer(
    data: CustomerCreate, db: Annotated[Session, Depends(get_db)]
) -> CustomerResponse:
    """Create a new customer."""
    try:
        customer = CustomerService.create_customer(
            db=db,
            name=data.name,
            phone=data.phone,
            email=data.email,
            address=data.address,
            notes=data.notes,
        )
        db.commit()
        db.refresh(customer)
        return CustomerResponse.model_validate(customer)
    except DuplicateResourceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/customers", response_model=list[CustomerResponse])
def list_customers(
    db: Annotated[Session, Depends(get_db)],
    query: str | None = Query(None, description="Search by name, phone, or code"),
    active_only: bool = Query(True, description="Show only active customers"),
    limit: int = Query(50, ge=1, le=200),
) -> list[CustomerResponse]:
    """List and search customers."""
    customers = CustomerService.search_customers(
        db=db, query=query, active_only=active_only, limit=limit
    )
    return [CustomerResponse.model_validate(c) for c in customers]


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: str, db: Annotated[Session, Depends(get_db)]
) -> CustomerResponse:
    """Get a customer by ID."""
    try:
        customer = CustomerService.get_customer(db, customer_id)
        return CustomerResponse.model_validate(customer)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/customers/code/{customer_code}", response_model=CustomerResponse)
def get_customer_by_code(
    customer_code: str, db: Annotated[Session, Depends(get_db)]
) -> CustomerResponse:
    """Get a customer by customer code."""
    customer = CustomerService.get_customer_by_code(db, customer_code)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CustomerResponse.model_validate(customer)


@router.get("/customers/phone/{phone}", response_model=CustomerResponse)
def get_customer_by_phone(
    phone: str, db: Annotated[Session, Depends(get_db)]
) -> CustomerResponse:
    """Get a customer by phone number."""
    customer = CustomerService.get_customer_by_phone(db, phone)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CustomerResponse.model_validate(customer)


@router.patch("/customers/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: str,
    data: CustomerUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> CustomerResponse:
    """Update customer information."""
    try:
        customer = CustomerService.update_customer(
            db=db,
            customer_id=customer_id,
            name=data.name,
            phone=data.phone,
            email=data.email,
            address=data.address,
            notes=data.notes,
            is_active=data.is_active,
        )
        db.commit()
        db.refresh(customer)
        return CustomerResponse.model_validate(customer)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DuplicateResourceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/customers/{customer_id}/loyalty-points", response_model=CustomerResponse)
def adjust_loyalty_points(
    customer_id: str,
    data: LoyaltyPointsRequest,
    db: Annotated[Session, Depends(get_db)],
) -> CustomerResponse:
    """Add or deduct loyalty points."""
    try:
        customer = CustomerService.add_loyalty_points(db, customer_id, data.points)
        db.commit()
        db.refresh(customer)
        return CustomerResponse.model_validate(customer)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/customers/{customer_id}/stats", response_model=CustomerStatsResponse)
def get_customer_stats(
    customer_id: str, db: Annotated[Session, Depends(get_db)]
) -> CustomerStatsResponse:
    """Get customer statistics."""
    try:
        stats = CustomerService.get_customer_stats(db, customer_id)
        return CustomerStatsResponse(**stats)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/customers/{customer_id}/purchases", response_model=list[SaleResponse])
def get_customer_purchases(
    customer_id: str,
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(50, ge=1, le=200),
) -> list[SaleResponse]:
    """Get customer purchase history."""
    try:
        # Verify customer exists
        CustomerService.get_customer(db, customer_id)
        
        purchases = CustomerService.get_customer_purchase_history(
            db, customer_id, limit
        )
        return [SaleResponse.model_validate(sale) for sale in purchases]
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/customers/reports/top", response_model=list[CustomerResponse])
def get_top_customers(
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(10, ge=1, le=50),
    by: str = Query("total_purchases", pattern="^(total_purchases|purchase_count)$"),
) -> list[CustomerResponse]:
    """Get top customers by total purchases or purchase count."""
    customers = CustomerService.get_top_customers(db, limit, by)
    return [CustomerResponse.model_validate(c) for c in customers]

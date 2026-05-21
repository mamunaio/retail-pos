"""API routes for supplier management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from retail_pos.api.schemas import (
    SupplierCreate,
    SupplierResponse,
    SupplierStatsResponse,
    SupplierUpdate,
)
from retail_pos.db.session import get_db
from retail_pos.services.supplier_service import SupplierService
from retail_pos.utils.exceptions import ResourceNotFoundError, ValidationError

router = APIRouter()


@router.post("/suppliers", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
def create_supplier(
    supplier_data: SupplierCreate,
    db: Session = Depends(get_db),
) -> SupplierResponse:
    """Create a new supplier."""
    try:
        service = SupplierService(db)
        supplier = service.create_supplier(
            name=supplier_data.name,
            company_name=supplier_data.company_name,
            phone=supplier_data.phone,
            email=supplier_data.email,
            address=supplier_data.address,
            contact_person=supplier_data.contact_person,
            payment_terms=supplier_data.payment_terms,
            credit_limit=supplier_data.credit_limit,
            notes=supplier_data.notes,
        )
        return SupplierResponse.model_validate(supplier)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/suppliers", response_model=list[SupplierResponse])
def list_suppliers(
    active_only: bool = Query(True, description="Only return active suppliers"),
    search: str | None = Query(None, description="Search by name, code, or phone"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[SupplierResponse]:
    """List suppliers with optional filtering."""
    service = SupplierService(db)
    suppliers = service.list_suppliers(
        active_only=active_only,
        search=search,
        limit=limit,
        offset=offset,
    )
    return [SupplierResponse.model_validate(s) for s in suppliers]


@router.get("/suppliers/{supplier_id}", response_model=SupplierResponse)
def get_supplier(
    supplier_id: str,
    db: Session = Depends(get_db),
) -> SupplierResponse:
    """Get supplier by ID."""
    try:
        service = SupplierService(db)
        supplier = service.get_supplier(supplier_id)
        return SupplierResponse.model_validate(supplier)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/suppliers/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
    supplier_id: str,
    supplier_data: SupplierUpdate,
    db: Session = Depends(get_db),
) -> SupplierResponse:
    """Update supplier information."""
    try:
        service = SupplierService(db)
        supplier = service.update_supplier(
            supplier_id=supplier_id,
            name=supplier_data.name,
            company_name=supplier_data.company_name,
            phone=supplier_data.phone,
            email=supplier_data.email,
            address=supplier_data.address,
            contact_person=supplier_data.contact_person,
            payment_terms=supplier_data.payment_terms,
            credit_limit=supplier_data.credit_limit,
            is_active=supplier_data.is_active,
            notes=supplier_data.notes,
        )
        return SupplierResponse.model_validate(supplier)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/suppliers/{supplier_id}/stats", response_model=SupplierStatsResponse)
def get_supplier_stats(
    supplier_id: str,
    db: Session = Depends(get_db),
) -> SupplierStatsResponse:
    """Get supplier statistics."""
    try:
        service = SupplierService(db)
        stats = service.get_supplier_stats(supplier_id)
        return SupplierStatsResponse(**stats)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/suppliers/reports/top", response_model=list[SupplierStatsResponse])
def get_top_suppliers(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[SupplierStatsResponse]:
    """Get top suppliers by purchase value."""
    service = SupplierService(db)
    suppliers = service.get_top_suppliers(limit=limit)
    return [SupplierStatsResponse(**s) for s in suppliers]

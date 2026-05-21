"""API routes for sales and POS operations."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from retail_pos.api.schemas import (
    CashierPerformanceResponse,
    CategorySalesResponse,
    DailySummaryResponse,
    HourlySalesResponse,
    PeriodSummaryResponse,
    ProfitAnalysisResponse,
    SaleCancelRequest,
    SaleCreate,
    SaleResponse,
    TopProductResponse,
)
from retail_pos.db import get_db
from retail_pos.models import PaymentMethod, SaleStatus
from retail_pos.services.reports_service import ReportsService
from retail_pos.services.sales_service import SalesService

router = APIRouter()


@router.post("/sales", response_model=SaleResponse, status_code=201)
def create_sale(data: SaleCreate, db: Annotated[Session, Depends(get_db)]) -> SaleResponse:
    """Create a new sale (complete a transaction)."""
    try:
        # Validate payment method
        try:
            payment_method = PaymentMethod(data.payment_method)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid payment method. Must be one of: {', '.join(PaymentMethod)}",
            )

        # Convert items to dict format
        items = [item.model_dump() for item in data.items]

        sale = SalesService.create_sale(
            db=db,
            terminal_id=data.terminal_id,
            cashier_id=data.cashier_id,
            items=items,
            payment_method=payment_method,
            amount_paid=data.amount_paid,
            customer_id=data.customer_id,
            customer_name=data.customer_name,
            customer_phone=data.customer_phone,
            discount_amount=data.discount_amount,
            notes=data.notes,
        )
        db.commit()
        db.refresh(sale)

        return SaleResponse.model_validate(sale)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sales", response_model=list[SaleResponse])
def list_sales(
    db: Annotated[Session, Depends(get_db)],
    status: str | None = None,
    cashier_id: str | None = None,
    terminal_id: str | None = None,
    limit: int = Query(default=50, le=200),
) -> list[SaleResponse]:
    """List sales with optional filters."""
    sale_status = None
    if status:
        try:
            sale_status = SaleStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(SaleStatus)}",
            )

    sales = SalesService.list_sales(
        db=db,
        status=sale_status,
        cashier_id=cashier_id,
        terminal_id=terminal_id,
        limit=limit,
    )

    return [SaleResponse.model_validate(sale) for sale in sales]


@router.get("/sales/{sale_id}", response_model=SaleResponse)
def get_sale(sale_id: str, db: Annotated[Session, Depends(get_db)]) -> SaleResponse:
    """Get a sale by ID with all items."""
    sale = SalesService.get_sale(db, sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")

    return SaleResponse.model_validate(sale)


@router.get("/sales/invoice/{invoice_number}", response_model=SaleResponse)
def get_sale_by_invoice(
    invoice_number: str, db: Annotated[Session, Depends(get_db)]
) -> SaleResponse:
    """Get a sale by invoice number."""
    sale = SalesService.get_sale_by_invoice(db, invoice_number)
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")

    return SaleResponse.model_validate(sale)


@router.post("/sales/{sale_id}/cancel", response_model=SaleResponse)
def cancel_sale(
    sale_id: str,
    data: SaleCancelRequest,
    db: Annotated[Session, Depends(get_db)],
    user_id: str = Query(..., description="User ID performing the cancellation"),
) -> SaleResponse:
    """Cancel a sale and restore stock."""
    try:
        sale = SalesService.cancel_sale(db, sale_id, user_id, data.reason)
        db.commit()
        db.refresh(sale)

        return SaleResponse.model_validate(sale)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sales/reports/daily", response_model=DailySummaryResponse)
def get_daily_summary(
    db: Annotated[Session, Depends(get_db)],
    date: str | None = Query(None, description="Date in YYYY-MM-DD format (defaults to today)"),
) -> DailySummaryResponse:
    """Get daily sales summary."""
    target_date = None
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    summary = SalesService.get_daily_summary(db, target_date)
    return DailySummaryResponse(**summary)


@router.get("/sales/reports/weekly", response_model=PeriodSummaryResponse)
def get_weekly_summary(
    db: Annotated[Session, Depends(get_db)],
    date: str | None = Query(None, description="Date in YYYY-MM-DD format (defaults to today)"),
) -> PeriodSummaryResponse:
    """Get weekly sales summary."""
    target_date = None
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    summary = ReportsService.get_weekly_summary(db, target_date)
    return PeriodSummaryResponse(**summary)


@router.get("/sales/reports/monthly", response_model=PeriodSummaryResponse)
def get_monthly_summary(
    db: Annotated[Session, Depends(get_db)],
    year: int = Query(..., description="Year (e.g., 2026)"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
) -> PeriodSummaryResponse:
    """Get monthly sales summary."""
    summary = ReportsService.get_monthly_summary(db, year, month)
    return PeriodSummaryResponse(**summary)


@router.get("/sales/reports/top-products", response_model=list[TopProductResponse])
def get_top_products(
    db: Annotated[Session, Depends(get_db)],
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    limit: int = Query(10, ge=1, le=50),
) -> list[TopProductResponse]:
    """Get top selling products."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    products = ReportsService.get_top_selling_products(db, start, end, limit)
    return [TopProductResponse(**p) for p in products]


@router.get("/sales/reports/category-sales", response_model=list[CategorySalesResponse])
def get_category_sales(
    db: Annotated[Session, Depends(get_db)],
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
) -> list[CategorySalesResponse]:
    """Get sales breakdown by category."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    categories = ReportsService.get_category_sales(db, start, end)
    return [CategorySalesResponse(**c) for c in categories]


@router.get("/sales/reports/cashier-performance", response_model=list[CashierPerformanceResponse])
def get_cashier_performance(
    db: Annotated[Session, Depends(get_db)],
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
) -> list[CashierPerformanceResponse]:
    """Get cashier performance report."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    cashiers = ReportsService.get_cashier_performance(db, start, end)
    return [CashierPerformanceResponse(**c) for c in cashiers]


@router.get("/sales/reports/hourly", response_model=list[HourlySalesResponse])
def get_hourly_sales(
    db: Annotated[Session, Depends(get_db)],
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
) -> list[HourlySalesResponse]:
    """Get hourly sales breakdown for a specific date."""
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    hourly = ReportsService.get_hourly_sales(db, target_date)
    return [HourlySalesResponse(**h) for h in hourly]


@router.get("/sales/reports/profit", response_model=ProfitAnalysisResponse)
def get_profit_analysis(
    db: Annotated[Session, Depends(get_db)],
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
) -> ProfitAnalysisResponse:
    """Get profit analysis for a period."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    profit = ReportsService.get_profit_analysis(db, start, end)
    return ProfitAnalysisResponse(**profit)

"""Reports and analytics service."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from retail_pos.models import Product, Sale, SaleItem, SaleStatus, User


class ReportsService:
    """Service for generating reports and analytics."""

    @staticmethod
    def get_sales_by_date_range(
        db: Session, start_date: datetime, end_date: datetime, status: SaleStatus | None = None
    ) -> list[Sale]:
        """Get sales within a date range."""
        query = select(Sale).where(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
        )

        if status:
            query = query.where(Sale.status == status)

        return list(db.scalars(query.order_by(Sale.created_at)).all())

    @staticmethod
    def get_period_summary(
        db: Session, start_date: datetime, end_date: datetime
    ) -> dict:
        """Get sales summary for a period (week, month, etc.)."""
        sales = ReportsService.get_sales_by_date_range(
            db, start_date, end_date, SaleStatus.COMPLETED
        )

        total_sales = len(sales)
        total_revenue = sum(sale.total_amount for sale in sales)
        total_tax = sum(sale.tax_amount for sale in sales)
        total_discount = sum(sale.discount_amount for sale in sales)

        # Count by payment method
        payment_methods = {}
        for sale in sales:
            method = sale.payment_method
            if method not in payment_methods:
                payment_methods[method] = {"count": 0, "amount": Decimal("0.00")}
            payment_methods[method]["count"] += 1
            payment_methods[method]["amount"] += sale.total_amount

        # Daily breakdown
        daily_sales = {}
        for sale in sales:
            date_key = sale.created_at.strftime("%Y-%m-%d")
            if date_key not in daily_sales:
                daily_sales[date_key] = {"count": 0, "revenue": Decimal("0.00")}
            daily_sales[date_key]["count"] += 1
            daily_sales[date_key]["revenue"] += sale.total_amount

        return {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "total_sales": total_sales,
            "total_revenue": float(total_revenue),
            "total_tax": float(total_tax),
            "total_discount": float(total_discount),
            "average_sale": float(total_revenue / total_sales) if total_sales > 0 else 0,
            "payment_methods": {
                k: {"count": v["count"], "amount": float(v["amount"])}
                for k, v in payment_methods.items()
            },
            "daily_breakdown": {
                k: {"count": v["count"], "revenue": float(v["revenue"])}
                for k, v in sorted(daily_sales.items())
            },
        }

    @staticmethod
    def get_top_selling_products(
        db: Session, start_date: datetime, end_date: datetime, limit: int = 10
    ) -> list[dict]:
        """Get top selling products by quantity and revenue."""
        # Query to get product sales
        result = (
            db.execute(
                select(
                    SaleItem.product_id,
                    Product.name,
                    Product.barcode,
                    Product.category,
                    func.sum(SaleItem.quantity).label("total_quantity"),
                    func.sum(SaleItem.line_total).label("total_revenue"),
                    func.count(SaleItem.id).label("transaction_count"),
                )
                .join(Sale, SaleItem.sale_id == Sale.id)
                .join(Product, SaleItem.product_id == Product.id)
                .where(
                    Sale.created_at >= start_date,
                    Sale.created_at <= end_date,
                    Sale.status == SaleStatus.COMPLETED,
                )
                .group_by(
                    SaleItem.product_id, Product.name, Product.barcode, Product.category
                )
                .order_by(func.sum(SaleItem.line_total).desc())
                .limit(limit)
            )
            .all()
        )

        return [
            {
                "product_id": row[0],
                "product_name": row[1],
                "barcode": row[2],
                "category": row[3],
                "total_quantity": float(row[4]),
                "total_revenue": float(row[5]),
                "transaction_count": row[6],
            }
            for row in result
        ]

    @staticmethod
    def get_category_sales(
        db: Session, start_date: datetime, end_date: datetime
    ) -> list[dict]:
        """Get sales breakdown by product category."""
        result = (
            db.execute(
                select(
                    Product.category,
                    func.sum(SaleItem.quantity).label("total_quantity"),
                    func.sum(SaleItem.line_total).label("total_revenue"),
                    func.count(func.distinct(SaleItem.product_id)).label("unique_products"),
                )
                .join(Sale, SaleItem.sale_id == Sale.id)
                .join(Product, SaleItem.product_id == Product.id)
                .where(
                    Sale.created_at >= start_date,
                    Sale.created_at <= end_date,
                    Sale.status == SaleStatus.COMPLETED,
                )
                .group_by(Product.category)
                .order_by(func.sum(SaleItem.line_total).desc())
            )
            .all()
        )

        return [
            {
                "category": row[0] or "Uncategorized",
                "total_quantity": float(row[1]),
                "total_revenue": float(row[2]),
                "unique_products": row[3],
            }
            for row in result
        ]

    @staticmethod
    def get_cashier_performance(
        db: Session, start_date: datetime, end_date: datetime
    ) -> list[dict]:
        """Get sales performance by cashier."""
        result = (
            db.execute(
                select(
                    Sale.cashier_id,
                    User.username,
                    User.full_name,
                    func.count(Sale.id).label("total_sales"),
                    func.sum(Sale.total_amount).label("total_revenue"),
                    func.avg(Sale.total_amount).label("average_sale"),
                )
                .join(User, Sale.cashier_id == User.id)
                .where(
                    Sale.created_at >= start_date,
                    Sale.created_at <= end_date,
                    Sale.status == SaleStatus.COMPLETED,
                )
                .group_by(Sale.cashier_id, User.username, User.full_name)
                .order_by(func.sum(Sale.total_amount).desc())
            )
            .all()
        )

        return [
            {
                "cashier_id": row[0],
                "username": row[1],
                "full_name": row[2],
                "total_sales": row[3],
                "total_revenue": float(row[4]),
                "average_sale": float(row[5]),
            }
            for row in result
        ]

    @staticmethod
    def get_hourly_sales(db: Session, date: datetime) -> list[dict]:
        """Get sales breakdown by hour for a specific date."""
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)

        sales = ReportsService.get_sales_by_date_range(
            db, start_of_day, end_of_day, SaleStatus.COMPLETED
        )

        # Group by hour
        hourly_data = {hour: {"count": 0, "revenue": Decimal("0.00")} for hour in range(24)}

        for sale in sales:
            hour = sale.created_at.hour
            hourly_data[hour]["count"] += 1
            hourly_data[hour]["revenue"] += sale.total_amount

        return [
            {
                "hour": hour,
                "time_range": f"{hour:02d}:00 - {hour:02d}:59",
                "count": data["count"],
                "revenue": float(data["revenue"]),
            }
            for hour, data in hourly_data.items()
        ]

    @staticmethod
    def get_weekly_summary(db: Session, date: datetime | None = None) -> dict:
        """Get summary for the week containing the given date."""
        if date is None:
            date = datetime.now()

        # Get start of week (Monday)
        start_of_week = date - timedelta(days=date.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

        # Get end of week (Sunday)
        end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)

        return ReportsService.get_period_summary(db, start_of_week, end_of_week)

    @staticmethod
    def get_monthly_summary(db: Session, year: int, month: int) -> dict:
        """Get summary for a specific month."""
        start_of_month = datetime(year, month, 1, 0, 0, 0)

        # Get last day of month
        if month == 12:
            end_of_month = datetime(year + 1, 1, 1, 0, 0, 0) - timedelta(seconds=1)
        else:
            end_of_month = datetime(year, month + 1, 1, 0, 0, 0) - timedelta(seconds=1)

        return ReportsService.get_period_summary(db, start_of_month, end_of_month)

    @staticmethod
    def get_profit_analysis(
        db: Session, start_date: datetime, end_date: datetime
    ) -> dict:
        """Calculate profit margins for the period."""
        result = (
            db.execute(
                select(
                    func.sum(SaleItem.line_total).label("total_revenue"),
                    func.sum(Product.cost_price * SaleItem.quantity).label("total_cost"),
                )
                .join(Sale, SaleItem.sale_id == Sale.id)
                .join(Product, SaleItem.product_id == Product.id)
                .where(
                    Sale.created_at >= start_date,
                    Sale.created_at <= end_date,
                    Sale.status == SaleStatus.COMPLETED,
                )
            )
            .first()
        )

        if not result or result[0] is None:
            return {
                "total_revenue": 0.0,
                "total_cost": 0.0,
                "gross_profit": 0.0,
                "profit_margin": 0.0,
            }

        total_revenue = float(result[0])
        total_cost = float(result[1])
        gross_profit = total_revenue - total_cost
        profit_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0

        return {
            "total_revenue": total_revenue,
            "total_cost": total_cost,
            "gross_profit": gross_profit,
            "profit_margin": round(profit_margin, 2),
        }

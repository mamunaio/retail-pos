"""Add sales, sale_items, payments tables

Revision ID: 0004_sales
Revises: 0003_inventory
Create Date: 2026-05-20

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_sales"
down_revision: str | None = "0003_inventory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sales",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("terminal_id", sa.String(length=36), nullable=False),
        sa.Column("cashier_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=True),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False),
        sa.Column("cart_discount", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("amount_tendered", sa.Numeric(10, 2), nullable=False),
        sa.Column("change_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("receipt_number", sa.String(length=40), nullable=True),
        sa.Column("void_reason", sa.String(length=200), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["terminal_id"], ["terminals.id"],
            name="fk_sales_terminal", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cashier_id"], ["users.id"],
            name="fk_sales_cashier", ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("receipt_number", name="uq_sales_receipt_number"),
    )
    op.create_index("ix_sales_terminal_id", "sales", ["terminal_id"], unique=False)
    op.create_index("ix_sales_cashier_id", "sales", ["cashier_id"], unique=False)
    op.create_index("ix_sales_status", "sales", ["status"], unique=False)
    op.create_index(
        "ix_sales_receipt_number", "sales", ["receipt_number"], unique=False
    )

    op.create_table(
        "sale_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("sale_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("barcode_snapshot", sa.String(length=50), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(10, 2), nullable=False),
        sa.Column("synced", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["sale_id"], ["sales.id"],
            name="fk_sale_items_sale", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name="fk_sale_items_product", ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_sale_items_sale_id", "sale_items", ["sale_id"], unique=False)
    op.create_index(
        "ix_sale_items_product_id", "sale_items", ["product_id"], unique=False
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("sale_id", sa.String(length=36), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("synced", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["sale_id"], ["sales.id"],
            name="fk_payments_sale", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_payments_sale_id", "payments", ["sale_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_payments_sale_id", table_name="payments")
    op.drop_table("payments")

    op.drop_index("ix_sale_items_product_id", table_name="sale_items")
    op.drop_index("ix_sale_items_sale_id", table_name="sale_items")
    op.drop_table("sale_items")

    op.drop_index("ix_sales_receipt_number", table_name="sales")
    op.drop_index("ix_sales_status", table_name="sales")
    op.drop_index("ix_sales_cashier_id", table_name="sales")
    op.drop_index("ix_sales_terminal_id", table_name="sales")
    op.drop_table("sales")

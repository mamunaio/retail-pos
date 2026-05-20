"""Add inventory and stock_movements tables

Revision ID: 0003_inventory
Revises: 0002_login_lockout
Create Date: 2026-05-20

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_inventory"
down_revision: str | None = "0002_login_lockout"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inventory",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("reorder_level", sa.Numeric(12, 3), nullable=False),
        sa.Column("synced", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_inventory_product",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("product_id", name="uq_inventory_product"),
    )
    op.create_index("ix_inventory_product_id", "inventory", ["product_id"], unique=False)

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("movement_type", sa.String(length=20), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(12, 3), nullable=False),
        sa.Column("reference_id", sa.String(length=36), nullable=True),
        sa.Column("reference_type", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("synced", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_stock_movements_product",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_stock_movements_user",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_stock_movements_product_id", "stock_movements", ["product_id"], unique=False
    )
    op.create_index(
        "ix_stock_movements_movement_type",
        "stock_movements",
        ["movement_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_stock_movements_movement_type", table_name="stock_movements")
    op.drop_index("ix_stock_movements_product_id", table_name="stock_movements")
    op.drop_table("stock_movements")

    op.drop_index("ix_inventory_product_id", table_name="inventory")
    op.drop_table("inventory")

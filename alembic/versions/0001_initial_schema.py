"""Initial schema: users, terminals, products

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-20

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("pin_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("synced", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=False)

    op.create_table(
        "terminals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("terminal_code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("device_fingerprint", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("synced", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("terminal_code", name="uq_terminals_code"),
    )
    op.create_index(
        "ix_terminals_terminal_code", "terminals", ["terminal_code"], unique=False
    )

    op.create_table(
        "products",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("barcode", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("cost_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("selling_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("synced", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("barcode", name="uq_products_barcode"),
    )
    op.create_index("ix_products_barcode", "products", ["barcode"], unique=False)
    op.create_index("ix_products_category", "products", ["category"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_products_category", table_name="products")
    op.drop_index("ix_products_barcode", table_name="products")
    op.drop_table("products")

    op.drop_index("ix_terminals_terminal_code", table_name="terminals")
    op.drop_table("terminals")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")

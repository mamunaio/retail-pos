"""ORM models.

Importing this package registers every model with SQLAlchemy's metadata,
which is required for Alembic autogenerate and for ``Base.metadata.create_all``
to see all tables.
"""

from retail_pos.models.inventory import Inventory
from retail_pos.models.product import Product, ProductUnit
from retail_pos.models.stock_movement import MovementType, StockMovement
from retail_pos.models.terminal import Terminal
from retail_pos.models.user import User, UserRole

__all__ = [
    "Inventory",
    "MovementType",
    "Product",
    "ProductUnit",
    "StockMovement",
    "Terminal",
    "User",
    "UserRole",
]

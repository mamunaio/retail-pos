"""ORM models.

Importing this package registers every model with SQLAlchemy's metadata,
which is required for Alembic autogenerate and for ``Base.metadata.create_all``
to see all tables.
"""

from retail_pos.models.product import Product, ProductUnit
from retail_pos.models.terminal import Terminal
from retail_pos.models.user import User, UserRole

__all__ = [
    "Product",
    "ProductUnit",
    "Terminal",
    "User",
    "UserRole",
]

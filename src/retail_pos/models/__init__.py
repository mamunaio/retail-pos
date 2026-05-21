"""ORM models.

Importing this package registers every model with SQLAlchemy's metadata,
which is required for Alembic autogenerate and for ``Base.metadata.create_all``
to see all tables.
"""

from retail_pos.models.activity_log import ActivityLog, ActivityType
from retail_pos.models.customer import Customer
from retail_pos.models.discount import Discount, DiscountScope, DiscountType, DiscountUsage
from retail_pos.models.inventory import Inventory, StockMovement, StockMovementType
from retail_pos.models.product import Product, ProductUnit
from retail_pos.models.purchase import PaymentStatus, Purchase, PurchaseItem, PurchaseStatus
from retail_pos.models.sale import PaymentMethod, Sale, SaleItem, SaleStatus
from retail_pos.models.supplier import Supplier
from retail_pos.models.terminal import Terminal
from retail_pos.models.user import User, UserRole

__all__ = [
    "Product",
    "ProductUnit",
    "Terminal",
    "User",
    "UserRole",
    "Inventory",
    "StockMovement",
    "StockMovementType",
    "Sale",
    "SaleItem",
    "SaleStatus",
    "PaymentMethod",
    "ActivityLog",
    "ActivityType",
    "Customer",
    "Supplier",
    "Purchase",
    "PurchaseItem",
    "PurchaseStatus",
    "PaymentStatus",
    "Discount",
    "DiscountType",
    "DiscountScope",
    "DiscountUsage",
]

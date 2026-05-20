"""Business logic / service layer.

Each module (auth, products, sales, etc.) lives here as a separate file.
Services depend on models and the DB session, never on the UI.
"""

from retail_pos.services.auth import (
    AccountInactiveError,
    AccountLockedError,
    AuthenticatedUser,
    AuthError,
    InvalidCredentialsError,
    authenticate,
    change_pin,
    reset_failed_attempts,
    unlock_user,
)
from retail_pos.services.products import (
    DuplicateBarcodeError,
    ProductError,
    ProductNotFoundError,
    count_products,
    create_product,
    deactivate_product,
    get_product,
    get_product_by_barcode,
    list_categories,
    list_products,
    reactivate_product,
    update_product,
)
from retail_pos.services.session import (
    NotLoggedInError,
    PermissionDeniedError,
    Session,
    current_session,
)

__all__ = [
    # auth
    "AccountInactiveError",
    "AccountLockedError",
    "AuthError",
    "AuthenticatedUser",
    "InvalidCredentialsError",
    "authenticate",
    "change_pin",
    "reset_failed_attempts",
    "unlock_user",
    # products
    "DuplicateBarcodeError",
    "ProductError",
    "ProductNotFoundError",
    "count_products",
    "create_product",
    "deactivate_product",
    "get_product",
    "get_product_by_barcode",
    "list_categories",
    "list_products",
    "reactivate_product",
    "update_product",
    # session
    "NotLoggedInError",
    "PermissionDeniedError",
    "Session",
    "current_session",
]

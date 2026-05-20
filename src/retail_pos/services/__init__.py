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
from retail_pos.services.session import (
    NotLoggedInError,
    PermissionDeniedError,
    Session,
    current_session,
)

__all__ = [
    "AccountInactiveError",
    "AccountLockedError",
    "AuthError",
    "AuthenticatedUser",
    "InvalidCredentialsError",
    "NotLoggedInError",
    "PermissionDeniedError",
    "Session",
    "authenticate",
    "change_pin",
    "current_session",
    "reset_failed_attempts",
    "unlock_user",
]

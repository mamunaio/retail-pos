"""Custom exceptions for the application."""

from __future__ import annotations


class RetailPOSException(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, code: str | None = None) -> None:
        self.message = message
        self.code = code or "GENERAL_ERROR"
        super().__init__(self.message)


class ValidationError(RetailPOSException):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: str | None = None) -> None:
        self.field = field
        super().__init__(message, "VALIDATION_ERROR")


class AuthenticationError(RetailPOSException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, "AUTH_ERROR")


class AuthorizationError(RetailPOSException):
    """Raised when user lacks permission."""

    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__(message, "PERMISSION_DENIED")


class ResourceNotFoundError(RetailPOSException):
    """Raised when a requested resource is not found."""

    def __init__(self, resource: str, identifier: str | None = None) -> None:
        message = f"{resource} not found"
        if identifier:
            message += f": {identifier}"
        super().__init__(message, "NOT_FOUND")


class InsufficientStockError(RetailPOSException):
    """Raised when there is insufficient stock for an operation."""

    def __init__(
        self, product_name: str, available: float, requested: float
    ) -> None:
        message = (
            f"Insufficient stock for {product_name}. "
            f"Available: {available}, Requested: {requested}"
        )
        super().__init__(message, "INSUFFICIENT_STOCK")


class InvalidOperationError(RetailPOSException):
    """Raised when an operation is not allowed in the current state."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "INVALID_OPERATION")


class DuplicateResourceError(RetailPOSException):
    """Raised when attempting to create a duplicate resource."""

    def __init__(self, resource: str, field: str, value: str) -> None:
        message = f"{resource} with {field} '{value}' already exists"
        super().__init__(message, "DUPLICATE_RESOURCE")

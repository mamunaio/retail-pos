"""Password / PIN hashing and validation utilities."""

from __future__ import annotations

import bcrypt

from retail_pos.config import settings

PIN_MIN_LENGTH = 4
PIN_MAX_LENGTH = 6


def validate_pin_format(pin: str) -> None:
    """Raise :class:`ValueError` if ``pin`` is not a valid PIN.

    A valid PIN is a string of digits, length :data:`PIN_MIN_LENGTH`–
    :data:`PIN_MAX_LENGTH`.
    """
    if not isinstance(pin, str) or not pin:
        raise ValueError("PIN must be a non-empty string")
    if not pin.isdigit():
        raise ValueError("PIN must contain digits only")
    if not (PIN_MIN_LENGTH <= len(pin) <= PIN_MAX_LENGTH):
        raise ValueError(
            f"PIN must be {PIN_MIN_LENGTH}-{PIN_MAX_LENGTH} digits long"
        )


def hash_pin(pin: str) -> str:
    """Validate and hash a numeric PIN using bcrypt."""
    validate_pin_format(pin)
    salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    return bcrypt.hashpw(pin.encode("utf-8"), salt).decode("utf-8")


def verify_pin(pin: str, pin_hash: str) -> bool:
    """Check whether ``pin`` matches the stored bcrypt ``pin_hash``.

    Returns ``False`` (instead of raising) for any input problem so the caller
    can treat all failures uniformly as "wrong PIN".
    """
    if not pin or not pin_hash:
        return False
    try:
        return bcrypt.checkpw(pin.encode("utf-8"), pin_hash.encode("utf-8"))
    except ValueError:
        # Raised if the stored hash is malformed.
        return False

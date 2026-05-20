"""Password / PIN hashing utilities."""

from __future__ import annotations

import bcrypt

from retail_pos.config import settings


def hash_pin(pin: str) -> str:
    """Hash a numeric PIN using bcrypt and return the hash as a UTF-8 string."""
    if not pin:
        raise ValueError("pin must be a non-empty string")
    salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    return bcrypt.hashpw(pin.encode("utf-8"), salt).decode("utf-8")


def verify_pin(pin: str, pin_hash: str) -> bool:
    """Check whether ``pin`` matches the stored bcrypt ``pin_hash``."""
    if not pin or not pin_hash:
        return False
    try:
        return bcrypt.checkpw(pin.encode("utf-8"), pin_hash.encode("utf-8"))
    except ValueError:
        # Raised if the stored hash is malformed.
        return False

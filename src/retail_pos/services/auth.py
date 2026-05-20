"""Authentication service.

Responsible for verifying user credentials, enforcing account lockout after
repeated failed PIN attempts, and changing PINs.

Public API:
    authenticate(db, username, pin) -> User
    change_pin(db, user, old_pin, new_pin) -> None
    unlock_user(db, user) -> None       (admin operation)
    reset_failed_attempts(db, user)     (admin operation)

All operations work against an existing :class:`~sqlalchemy.orm.Session` so the
caller controls transaction boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from retail_pos.models.user import User
from retail_pos.utils.security import hash_pin, validate_pin_format, verify_pin

# --- Lockout policy -----------------------------------------------------------
#
# After this many consecutive wrong PINs the account is locked for
# ``LOCK_DURATION``. The counter is reset on the next successful login or by
# an admin action. Tuned for a retail counter where typos are common but a
# brute-force attack against a 4-digit PIN would otherwise succeed quickly.
MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION = timedelta(minutes=15)


# --- Exceptions ---------------------------------------------------------------


class AuthError(Exception):
    """Base class for all authentication failures."""


class InvalidCredentialsError(AuthError):
    """Username does not exist or PIN is wrong."""


class AccountInactiveError(AuthError):
    """User exists but ``is_active`` is False."""


class AccountLockedError(AuthError):
    """Too many failed attempts; account is locked until ``locked_until``."""

    def __init__(self, locked_until: datetime) -> None:
        super().__init__(f"Account locked until {locked_until.isoformat()}")
        self.locked_until = locked_until


# --- Helpers ------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _ensure_aware(dt: datetime) -> datetime:
    """Return ``dt`` with UTC tzinfo if it was stored naive (SQLite quirk).

    SQLite does not preserve timezone info, so values round-tripped through
    the database can come back as naive datetimes. We treat them as UTC
    because that is what we store.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _is_locked(user: User, now: datetime) -> bool:
    if user.locked_until is None:
        return False
    return _ensure_aware(user.locked_until) > now


def _record_failed_attempt(user: User, now: datetime) -> None:
    """Increment the failed-attempt counter and lock the account if needed."""
    user.failed_pin_attempts += 1
    if user.failed_pin_attempts >= MAX_FAILED_ATTEMPTS:
        user.locked_until = now + LOCK_DURATION
    user.synced = False  # auth state changed; needs to be pushed to cloud


def _record_successful_login(user: User) -> None:
    user.failed_pin_attempts = 0
    user.locked_until = None
    user.synced = False


# --- Public API ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """Lightweight DTO returned by :func:`authenticate`.

    Holds just the fields the UI / session manager needs, decoupled from the
    ORM object so callers cannot accidentally mutate the database row.
    """

    id: str
    username: str
    full_name: str
    role: str


def authenticate(db: Session, username: str, pin: str) -> AuthenticatedUser:
    """Verify credentials and return the authenticated user.

    On a successful authentication, the user's failed-attempt counter is
    cleared. On failure, the counter is incremented and the account is
    locked for :data:`LOCK_DURATION` once :data:`MAX_FAILED_ATTEMPTS` is
    reached.

    The caller is responsible for committing the session.

    Raises:
        InvalidCredentialsError: username does not exist or PIN is wrong.
        AccountInactiveError: the user is marked inactive.
        AccountLockedError: account is currently locked.
    """
    if not username or not pin:
        raise InvalidCredentialsError("username and pin are required")

    user = db.scalar(select(User).where(User.username == username))
    now = _utcnow()

    # We deliberately do NOT distinguish "no such user" from "wrong pin" in
    # the error message, but we still need to short-circuit if the user does
    # not exist (no row to update).
    if user is None:
        raise InvalidCredentialsError("invalid username or PIN")

    if not user.is_active:
        raise AccountInactiveError("account is inactive")

    if _is_locked(user, now):
        assert user.locked_until is not None  # for type checkers
        raise AccountLockedError(_ensure_aware(user.locked_until))

    if not verify_pin(pin, user.pin_hash):
        _record_failed_attempt(user, now)
        db.flush()
        # If this attempt just tripped the lockout, surface that to the caller
        # so the UI can show the right message.
        if _is_locked(user, now):
            assert user.locked_until is not None
            raise AccountLockedError(_ensure_aware(user.locked_until))
        raise InvalidCredentialsError("invalid username or PIN")

    _record_successful_login(user)
    db.flush()

    return AuthenticatedUser(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
    )


def change_pin(db: Session, user: User, old_pin: str, new_pin: str) -> None:
    """Change ``user``'s PIN after verifying the old PIN.

    Raises:
        InvalidCredentialsError: ``old_pin`` does not match the current PIN.
        ValueError: ``new_pin`` is not a valid PIN format.
    """
    if not verify_pin(old_pin, user.pin_hash):
        raise InvalidCredentialsError("current PIN is incorrect")
    validate_pin_format(new_pin)  # raises ValueError on bad format
    user.pin_hash = hash_pin(new_pin)
    user.synced = False
    db.flush()


def reset_failed_attempts(db: Session, user: User) -> None:
    """Clear failed-attempt counter without unlocking. Admin-only operation."""
    user.failed_pin_attempts = 0
    user.synced = False
    db.flush()


def unlock_user(db: Session, user: User) -> None:
    """Clear lock and failed-attempt counter. Admin-only operation."""
    user.failed_pin_attempts = 0
    user.locked_until = None
    user.synced = False
    db.flush()

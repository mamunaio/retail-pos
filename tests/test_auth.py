"""Tests for the authentication service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from retail_pos.models import User, UserRole
from retail_pos.services.auth import (
    LOCK_DURATION,
    MAX_FAILED_ATTEMPTS,
    AccountInactiveError,
    AccountLockedError,
    InvalidCredentialsError,
    authenticate,
    change_pin,
    reset_failed_attempts,
    unlock_user,
)
from retail_pos.utils.security import hash_pin, verify_pin


def _make_user(
    db: Session,
    *,
    username: str = "cashier1",
    pin: str = "1234",
    role: UserRole = UserRole.CASHIER,
    is_active: bool = True,
) -> User:
    user = User(
        username=username,
        pin_hash=hash_pin(pin),
        full_name="Test User",
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# --- authenticate -------------------------------------------------------------


def test_authenticate_success_returns_user(db_session: Session) -> None:
    _make_user(db_session, username="cashier1", pin="1234")

    result = authenticate(db_session, "cashier1", "1234")

    assert result.username == "cashier1"
    assert result.role == UserRole.CASHIER


def test_authenticate_clears_failed_attempts_on_success(db_session: Session) -> None:
    user = _make_user(db_session, pin="1234")
    user.failed_pin_attempts = 3
    db_session.commit()

    authenticate(db_session, user.username, "1234")
    db_session.commit()
    db_session.refresh(user)

    assert user.failed_pin_attempts == 0
    assert user.locked_until is None


def test_authenticate_wrong_pin_increments_counter(db_session: Session) -> None:
    user = _make_user(db_session, pin="1234")

    with pytest.raises(InvalidCredentialsError):
        authenticate(db_session, user.username, "9999")
    db_session.commit()
    db_session.refresh(user)

    assert user.failed_pin_attempts == 1
    assert user.locked_until is None


def test_authenticate_unknown_user_raises(db_session: Session) -> None:
    with pytest.raises(InvalidCredentialsError):
        authenticate(db_session, "nobody", "1234")


def test_authenticate_inactive_user_raises(db_session: Session) -> None:
    _make_user(db_session, username="bob", pin="1234", is_active=False)

    with pytest.raises(AccountInactiveError):
        authenticate(db_session, "bob", "1234")


def test_authenticate_locks_after_max_attempts(db_session: Session) -> None:
    user = _make_user(db_session, pin="1234")

    # Trip the threshold. The Nth wrong attempt itself raises AccountLocked.
    for _ in range(MAX_FAILED_ATTEMPTS - 1):
        with pytest.raises(InvalidCredentialsError):
            authenticate(db_session, user.username, "0000")
    with pytest.raises(AccountLockedError):
        authenticate(db_session, user.username, "0000")
    db_session.commit()
    db_session.refresh(user)

    assert user.failed_pin_attempts == MAX_FAILED_ATTEMPTS
    assert user.locked_until is not None


def test_authenticate_blocked_while_locked_even_with_correct_pin(
    db_session: Session,
) -> None:
    user = _make_user(db_session, pin="1234")
    user.failed_pin_attempts = MAX_FAILED_ATTEMPTS
    user.locked_until = datetime.now(UTC) + LOCK_DURATION
    db_session.commit()

    with pytest.raises(AccountLockedError):
        authenticate(db_session, user.username, "1234")


def test_authenticate_succeeds_after_lock_expires(db_session: Session) -> None:
    user = _make_user(db_session, pin="1234")
    user.failed_pin_attempts = MAX_FAILED_ATTEMPTS
    # Already-expired lock
    user.locked_until = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()

    result = authenticate(db_session, user.username, "1234")
    db_session.commit()
    db_session.refresh(user)

    assert result.username == user.username
    assert user.failed_pin_attempts == 0
    assert user.locked_until is None


# --- change_pin ---------------------------------------------------------------


def test_change_pin_updates_hash(db_session: Session) -> None:
    user = _make_user(db_session, pin="1234")

    change_pin(db_session, user, old_pin="1234", new_pin="5678")
    db_session.commit()
    db_session.refresh(user)

    assert verify_pin("5678", user.pin_hash) is True
    assert verify_pin("1234", user.pin_hash) is False


def test_change_pin_rejects_wrong_old_pin(db_session: Session) -> None:
    user = _make_user(db_session, pin="1234")

    with pytest.raises(InvalidCredentialsError):
        change_pin(db_session, user, old_pin="0000", new_pin="5678")


def test_change_pin_rejects_invalid_new_pin(db_session: Session) -> None:
    user = _make_user(db_session, pin="1234")

    with pytest.raises(ValueError):
        change_pin(db_session, user, old_pin="1234", new_pin="abc")
    with pytest.raises(ValueError):
        change_pin(db_session, user, old_pin="1234", new_pin="12")  # too short


# --- admin helpers ------------------------------------------------------------


def test_reset_failed_attempts(db_session: Session) -> None:
    user = _make_user(db_session, pin="1234")
    user.failed_pin_attempts = 3
    db_session.commit()

    reset_failed_attempts(db_session, user)
    db_session.commit()
    db_session.refresh(user)

    assert user.failed_pin_attempts == 0


def test_unlock_user_clears_lock(db_session: Session) -> None:
    user = _make_user(db_session, pin="1234")
    user.failed_pin_attempts = MAX_FAILED_ATTEMPTS
    user.locked_until = datetime.now(UTC) + LOCK_DURATION
    db_session.commit()

    unlock_user(db_session, user)
    db_session.commit()
    db_session.refresh(user)

    assert user.failed_pin_attempts == 0
    assert user.locked_until is None

"""Tests for the in-memory Session manager."""

from __future__ import annotations

import pytest

from retail_pos.services.auth import AuthenticatedUser
from retail_pos.services.session import (
    NotLoggedInError,
    PermissionDeniedError,
    Session,
)


def _admin() -> AuthenticatedUser:
    return AuthenticatedUser(id="u-1", username="admin", full_name="Admin", role="admin")


def _cashier() -> AuthenticatedUser:
    return AuthenticatedUser(id="u-2", username="c1", full_name="Cashier", role="cashier")


def test_initial_state_is_unauthenticated() -> None:
    s = Session()
    assert s.is_authenticated is False
    assert s.terminal_id is None
    with pytest.raises(NotLoggedInError):
        _ = s.user


def test_login_sets_user_and_terminal() -> None:
    s = Session()
    s.login(_admin(), terminal_id="t-1")

    assert s.is_authenticated is True
    assert s.user.username == "admin"
    assert s.terminal_id == "t-1"


def test_logout_clears_user_but_keeps_terminal() -> None:
    s = Session()
    s.login(_admin(), terminal_id="t-1")
    s.logout()

    assert s.is_authenticated is False
    assert s.terminal_id == "t-1"  # terminal binding survives logout


def test_login_replaces_previous_user() -> None:
    s = Session()
    s.login(_admin())
    s.login(_cashier())

    assert s.user.username == "c1"


def test_has_role() -> None:
    s = Session()
    s.login(_admin())

    assert s.has_role("admin") is True
    assert s.has_role("cashier") is False


def test_require_role_passes_for_matching_role() -> None:
    s = Session()
    s.login(_admin())

    s.require_role("admin")  # does not raise


def test_require_role_raises_for_wrong_role() -> None:
    s = Session()
    s.login(_cashier())

    with pytest.raises(PermissionDeniedError):
        s.require_role("admin")


def test_require_role_raises_when_logged_out() -> None:
    s = Session()
    with pytest.raises(NotLoggedInError):
        s.require_role("admin")

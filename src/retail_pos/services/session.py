"""In-memory session for the running POS application.

Tracks who is logged in and which terminal the app is bound to. The UI layer
reads from this module to render role-specific menus, attribute sales to a
cashier, etc.

This is intentionally a per-process singleton: a single desktop app instance
serves one cashier on one terminal at a time.
"""

from __future__ import annotations

from threading import RLock

from retail_pos.services.auth import AuthenticatedUser


class NotLoggedInError(RuntimeError):
    """Raised when a caller asks for the current user but no one is logged in."""


class PermissionDeniedError(RuntimeError):
    """Raised by :meth:`Session.require_role` when the role check fails."""


class Session:
    """Holds the currently logged-in user and the bound terminal id.

    Thread-safe so background workers (e.g. the future sync worker) can read
    the current user without racing the UI thread.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._user: AuthenticatedUser | None = None
        self._terminal_id: str | None = None

    # --- Login / logout ------------------------------------------------------

    def login(self, user: AuthenticatedUser, terminal_id: str | None = None) -> None:
        """Mark ``user`` as logged in. Replaces any previous session."""
        with self._lock:
            self._user = user
            if terminal_id is not None:
                self._terminal_id = terminal_id

    def logout(self) -> None:
        """Clear the current user (terminal binding stays)."""
        with self._lock:
            self._user = None

    def bind_terminal(self, terminal_id: str) -> None:
        """Associate this app instance with a terminal row."""
        with self._lock:
            self._terminal_id = terminal_id

    # --- Queries -------------------------------------------------------------

    @property
    def is_authenticated(self) -> bool:
        with self._lock:
            return self._user is not None

    @property
    def user(self) -> AuthenticatedUser:
        """Return the current user or raise :class:`NotLoggedInError`."""
        with self._lock:
            if self._user is None:
                raise NotLoggedInError("no user is currently logged in")
            return self._user

    @property
    def terminal_id(self) -> str | None:
        with self._lock:
            return self._terminal_id

    # --- Role checks ---------------------------------------------------------

    def has_role(self, role: str) -> bool:
        with self._lock:
            return self._user is not None and self._user.role == role

    def require_role(self, role: str) -> None:
        """Raise :class:`PermissionDeniedError` unless the current user has ``role``."""
        with self._lock:
            if self._user is None:
                raise NotLoggedInError("no user is currently logged in")
            if self._user.role != role:
                raise PermissionDeniedError(
                    f"requires role={role!r}, current role={self._user.role!r}"
                )


# Module-level singleton used by the UI and services.
current_session = Session()

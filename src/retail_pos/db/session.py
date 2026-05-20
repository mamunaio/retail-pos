"""SQLAlchemy engine and session management."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from retail_pos.config import settings


def _make_engine() -> Engine:
    """Create the SQLAlchemy engine for the local SQLite database.

    Ensures the data directory exists before opening the database file.
    """
    settings.ensure_data_dir()
    engine = create_engine(
        settings.sqlalchemy_url,
        echo=settings.debug,
        future=True,
    )

    # Enable foreign-key enforcement in SQLite (off by default).
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
        if settings.sqlalchemy_url.startswith("sqlite"):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine: Engine = _make_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session() -> Session:
    """Return a new database session.

    Caller is responsible for closing it. Prefer :func:`session_scope` for most
    use cases.
    """
    return SessionLocal()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context-managed session that commits on success and rolls back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

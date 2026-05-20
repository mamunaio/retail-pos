"""Shared pytest fixtures.

The test suite uses an in-memory SQLite database so it is fast and leaves no
state on disk. The fixture below creates all tables from the SQLAlchemy
metadata directly (no Alembic) so individual tests do not need to run
migrations.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Importing the models package registers every table on Base.metadata.
import retail_pos.models  # noqa: F401
from retail_pos.db.base import Base


@pytest.fixture()
def db_session() -> Iterator[Session]:
    """Yield a fresh in-memory SQLite session for one test."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()

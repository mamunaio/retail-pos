"""Application configuration.

Centralizes all runtime settings. Values can be overridden via environment
variables (prefix: ``POS_``) or a ``.env`` file at the project root.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    """Return the directory where local data (SQLite DB, logs) is stored."""
    return Path.home() / ".retail_pos"


class Settings(BaseSettings):
    """Application settings loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_prefix="POS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Paths ---
    data_dir: Path = Field(default_factory=_default_data_dir)
    db_filename: str = "retail_pos.db"

    # --- Database ---
    # Allow overriding the full SQLAlchemy URL (useful for testing with :memory:).
    database_url: str | None = None

    # --- Bcrypt ---
    bcrypt_rounds: int = 12

    # --- Environment ---
    environment: str = "development"
    debug: bool = True

    @property
    def db_path(self) -> Path:
        """Absolute path to the SQLite database file."""
        return self.data_dir / self.db_filename

    @property
    def sqlalchemy_url(self) -> str:
        """SQLAlchemy connection URL for the local SQLite database."""
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.db_path}"

    def ensure_data_dir(self) -> None:
        """Create the data directory if it doesn't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()

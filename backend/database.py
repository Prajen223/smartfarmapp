"""Database abstraction and persistent storage engine for FarmSaathi.

Supports:
1. Local SQLite (`data/farm_sessions.db`) by default for local development, CI, and test suites.
2. Cloud PostgreSQL (Neon, Supabase, Render Postgres) when `DATABASE_URL` is provided.
Provides schema definitions, connection management, and table initializers.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR = Path(__file__).parent / "data"
DEFAULT_SQLITE_PATH = DEFAULT_DATA_DIR / "farm_sessions.db"

# PostgreSQL Table DDL (ANSI SQL / PostgreSQL compatible)
PG_TABLES_DDL = {
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            user_id VARCHAR(64) PRIMARY KEY,
            username VARCHAR(64) UNIQUE NOT NULL,
            hashed_password VARCHAR(256) NOT NULL,
            role VARCHAR(32) NOT NULL DEFAULT 'farmer',
            created_at VARCHAR(64) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        );
        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
    """,
    "farmer_sessions": """
        CREATE TABLE IF NOT EXISTS farmer_sessions (
            session_id VARCHAR(64) PRIMARY KEY,
            farmer_id VARCHAR(64),
            created_at VARCHAR(64) NOT NULL,
            updated_at VARCHAR(64) NOT NULL,
            last_activity VARCHAR(64) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            metadata TEXT DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_farmer ON farmer_sessions(farmer_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON farmer_sessions(last_activity);
    """,
    "conversation_messages": """
        CREATE TABLE IF NOT EXISTS conversation_messages (
            message_id VARCHAR(64) PRIMARY KEY,
            session_id VARCHAR(64) NOT NULL REFERENCES farmer_sessions(session_id) ON DELETE CASCADE,
            sender VARCHAR(16) NOT NULL,
            message_text TEXT NOT NULL,
            timestamp VARCHAR(64) NOT NULL,
            metadata TEXT DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_messages_session ON conversation_messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON conversation_messages(timestamp);
    """,
    "farmer_feedback": """
        CREATE TABLE IF NOT EXISTS farmer_feedback (
            feedback_id VARCHAR(64) PRIMARY KEY,
            session_id VARCHAR(64) NOT NULL,
            message_id VARCHAR(64) UNIQUE NOT NULL,
            farmer_id VARCHAR(64),
            rating VARCHAR(16) NOT NULL,
            comment TEXT,
            language VARCHAR(16) DEFAULT 'en',
            intent VARCHAR(64),
            query_text TEXT,
            answer_text TEXT,
            review_id VARCHAR(64),
            created_at VARCHAR(64) NOT NULL,
            updated_at VARCHAR(64) NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_feedback_session ON farmer_feedback(session_id);
        CREATE INDEX IF NOT EXISTS idx_feedback_rating ON farmer_feedback(rating);
        CREATE INDEX IF NOT EXISTS idx_feedback_created ON farmer_feedback(created_at);
    """,
}


def get_database_url() -> Optional[str]:
    """Retrieve configured database connection URL, if any."""
    return os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or None


def is_postgres_configured() -> bool:
    """Check whether a valid PostgreSQL connection URL is configured."""
    url = get_database_url()
    if not url:
        return False
    return url.startswith("postgresql://") or url.startswith("postgres://")


class DatabaseEngine:
    """Manages database connectivity across SQLite and optional PostgreSQL."""

    def __init__(self, db_url: Optional[str] = None, sqlite_path: Optional[Path] = None):
        self.db_url = db_url or get_database_url()
        self.sqlite_path = sqlite_path or Path(os.getenv("FARM_SESSIONS_DB_PATH", str(DEFAULT_SQLITE_PATH)))
        self._is_postgres = is_postgres_configured() and bool(self.db_url)
        self._pg_driver_available = False

        if self._is_postgres:
            try:
                import psycopg2  # type: ignore # noqa: F401
                self._pg_driver_available = True
                logger.info("PostgreSQL driver (psycopg2) is available.")
            except ImportError:
                try:
                    import psycopg  # type: ignore # noqa: F401
                    self._pg_driver_available = True
                    logger.info("PostgreSQL driver (psycopg 3) is available.")
                except ImportError:
                    logger.warning(
                        "DATABASE_URL is set to PostgreSQL, but neither 'psycopg2' nor 'psycopg' is installed. "
                        "Falling back to local SQLite at %s.",
                        self.sqlite_path,
                    )
                    self._is_postgres = False

    @property
    def is_postgres(self) -> bool:
        return self._is_postgres and self._pg_driver_available

    def get_sqlite_connection(self) -> sqlite3.Connection:
        """Create and return a configured SQLite connection."""
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.sqlite_path), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def get_postgres_connection(self) -> Any:
        """Create and return a configured PostgreSQL connection."""
        if not self.is_postgres or not self.db_url:
            raise RuntimeError("PostgreSQL is not configured or driver is missing.")

        clean_url = self.db_url
        if clean_url.startswith("postgres://"):
            clean_url = clean_url.replace("postgres://", "postgresql://", 1)

        try:
            import psycopg2
            return psycopg2.connect(clean_url)
        except ImportError:
            import psycopg
            return psycopg.connect(clean_url)

    def init_postgres_schema(self) -> None:
        """Initialize all relational tables in the target PostgreSQL database."""
        if not self.is_postgres:
            return

        conn = self.get_postgres_connection()
        try:
            with conn.cursor() as cur:
                for table_name, ddl in PG_TABLES_DDL.items():
                    cur.execute(ddl)
                    logger.info("Initialized PostgreSQL table: %s", table_name)
            conn.commit()
        finally:
            conn.close()


# Module singleton
db_engine = DatabaseEngine()

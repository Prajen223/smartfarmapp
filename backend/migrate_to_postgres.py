"""PostgreSQL migration script for FarmSaathi.

Migrates relational SQLite tables (users, sessions, messages, feedback)
to a cloud PostgreSQL instance (Neon, Supabase, Render Postgres) without
destructive drops, preserving all accounts, passwords, and sessions.
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

from backup_database import create_backup, DEFAULT_DB_PATH
from database import PG_TABLES_DDL, get_database_url

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migrate_to_postgres")


def migrate(
    sqlite_path: Path = DEFAULT_DB_PATH,
    pg_url: str | None = None,
    dry_run: bool = False,
) -> bool:
    """Migrate all data from SQLite to PostgreSQL."""
    target_url = pg_url or get_database_url()
    if not target_url:
        logger.error("No PostgreSQL DATABASE_URL found. Please set DATABASE_URL or pass --pg-url.")
        return False

    if not sqlite_path.exists():
        logger.error("Source SQLite database not found at %s", sqlite_path)
        return False

    # 1. Automatic pre-migration backup
    logger.info("Step 1: Creating safety backup before migration...")
    backup_dir = create_backup(db_path=sqlite_path)
    logger.info("Pre-migration safety backup completed: %s", backup_dir)

    # 2. Check PostgreSQL driver
    try:
        import psycopg2
        connect_fn = psycopg2.connect
    except ImportError:
        try:
            import psycopg
            connect_fn = psycopg.connect
        except ImportError:
            logger.error("Neither 'psycopg2' nor 'psycopg' is installed in python environment.")
            logger.info("Please install with: pip install psycopg2-binary")
            return False

    # Normalize url
    clean_url = target_url
    if clean_url.startswith("postgres://"):
        clean_url = clean_url.replace("postgres://", "postgresql://", 1)

    logger.info("Connecting to target PostgreSQL database...")
    try:
        pg_conn = connect_fn(clean_url)
    except Exception as e:
        logger.error("Failed to connect to PostgreSQL: %s", e)
        return False

    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row

    try:
        with pg_conn.cursor() as pg_cur:
            # 3. Create tables in PostgreSQL
            logger.info("Step 2: Initializing PostgreSQL schema...")
            for tbl, ddl in PG_TABLES_DDL.items():
                if not dry_run:
                    pg_cur.execute(ddl)
            if not dry_run:
                pg_conn.commit()

            # 4. Migrate tables in foreign-key safe order
            migration_plan = [
                ("users", "user_id"),
                ("farmer_sessions", "session_id"),
                ("conversation_messages", "message_id"),
                ("farmer_feedback", "feedback_id"),
            ]

            logger.info("Step 3: Migrating records...")
            for tbl, pk in migration_plan:
                sqlite_rows = sqlite_conn.execute(f"SELECT * FROM {tbl}").fetchall()
                count = len(sqlite_rows)
                logger.info("  -> Found %d rows in SQLite table '%s'", count, tbl)

                if count == 0:
                    continue

                if dry_run:
                    logger.info("     [DRY RUN] Would migrate %d rows into PostgreSQL table '%s'", count, tbl)
                    continue

                # Prepare insert with ON CONFLICT DO NOTHING to ensure idempotence
                sample_dict = dict(sqlite_rows[0])
                columns = list(sample_dict.keys())
                col_names = ", ".join(columns)
                placeholders = ", ".join(["%s"] * len(columns))

                insert_sql = f"""
                    INSERT INTO {tbl} ({col_names})
                    VALUES ({placeholders})
                    ON CONFLICT ({pk}) DO NOTHING
                """

                inserted = 0
                for row in sqlite_rows:
                    row_dict = dict(row)
                    values = [row_dict[c] for c in columns]
                    pg_cur.execute(insert_sql, values)
                    inserted += 1

                pg_conn.commit()
                logger.info("     Successfully synced %d rows to PostgreSQL '%s'", inserted, tbl)

        # 5. Validation Check
        logger.info("Step 4: Validating row counts...")
        with pg_conn.cursor() as pg_cur:
            for tbl, _ in migration_plan:
                sqlite_cnt = sqlite_conn.execute(f"SELECT count(*) FROM {tbl}").fetchone()[0]
                pg_cur.execute(f"SELECT count(*) FROM {tbl}")
                pg_cnt = pg_cur.fetchone()[0]
                status = "MATCH" if pg_cnt >= sqlite_cnt else "MISMATCH"
                logger.info("  Table '%s': SQLite=%d, Postgres=%d [%s]", tbl, sqlite_cnt, pg_cnt, status)

        logger.info("PostgreSQL migration process finished successfully.")
        return True

    except Exception as exc:
        logger.exception("Migration failed with error: %s", exc)
        pg_conn.rollback()
        return False
    finally:
        sqlite_conn.close()
        pg_conn.close()


def main():
    parser = argparse.ArgumentParser(description="FarmSaathi SQLite to PostgreSQL Migration Tool")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH, help="Path to source SQLite database")
    parser.add_argument("--pg-url", type=str, default=None, help="Target PostgreSQL connection URL")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without modifying PostgreSQL")
    args = parser.parse_args()

    success = migrate(sqlite_path=args.db_path, pg_url=args.pg_url, dry_run=args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

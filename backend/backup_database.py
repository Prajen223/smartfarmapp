"""Database and state backup utility for FarmSaathi.

Exports all relational SQLite tables (users, sessions, messages, feedback)
and JSON knowledge/review stores into a timestamped, verified backup directory.
Never executes destructive operations.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backup_database")

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_DB_PATH = DATA_DIR / "farm_sessions.db"
BACKUPS_ROOT = DATA_DIR / "backups"


def compute_file_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of a file for integrity verification."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def export_sqlite_table(conn: sqlite3.Connection, table_name: str) -> list[dict[str, Any]]:
    """Export all rows from an SQLite table as a list of dictionaries."""
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError as e:
        logger.warning("Table '%s' could not be exported: %s", table_name, e)
        return []


def create_backup(
    db_path: Path = DEFAULT_DB_PATH,
    output_dir: Path | None = None,
) -> Path:
    """Create a complete, non-destructive backup of FarmSaathi relational and file data.

    Returns the Path to the generated backup directory.
    """
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    target_dir = output_dir or (BACKUPS_ROOT / f"backup_{timestamp}")
    target_dir.mkdir(parents=True, exist_ok=True)

    manifest: Dict[str, Any] = {
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_db": str(db_path),
        "tables": {},
        "files": {},
    }

    # 1. Export SQLite tables
    if db_path.exists():
        logger.info("Exporting relational tables from %s ...", db_path)
        # Copy the raw database binary
        raw_copy = target_dir / "farm_sessions.db"
        shutil.copy2(db_path, raw_copy)
        manifest["files"]["farm_sessions.db"] = {
            "size_bytes": raw_copy.stat().st_size,
            "sha256": compute_file_sha256(raw_copy),
        }

        # Dump tables as JSON
        conn = sqlite3.connect(str(db_path))
        tables_to_export = ["users", "farmer_sessions", "conversation_messages", "farmer_feedback"]
        for tbl in tables_to_export:
            rows = export_sqlite_table(conn, tbl)
            table_file = target_dir / f"{tbl}.json"
            with open(table_file, "w", encoding="utf-8") as f:
                json.dump(rows, f, indent=2, ensure_ascii=False)
            manifest["tables"][tbl] = {
                "count": len(rows),
                "export_file": f"{tbl}.json",
            }
            logger.info("  -> Table '%s': %d records exported.", tbl, len(rows))
        conn.close()
    else:
        logger.warning("SQLite database not found at %s. Skipping table exports.", db_path)

    # 2. Export Human Reviews and Ingested Knowledge JSON stores
    files_to_backup = [
        "human_reviews.json",
        "ingested_knowledge.json",
        "low_confidence_queries.jsonl",
    ]
    for fname in files_to_backup:
        fpath = DATA_DIR / fname
        if fpath.exists():
            dest = target_dir / fname
            shutil.copy2(fpath, dest)
            manifest["files"][fname] = {
                "size_bytes": dest.stat().st_size,
                "sha256": compute_file_sha256(dest),
            }
            logger.info("  -> Data file '%s' backed up.", fname)

    # 3. Write Manifest
    manifest_path = target_dir / "backup_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("FarmSaathi backup completed successfully at: %s", target_dir)
    return target_dir


if __name__ == "__main__":
    b_dir = create_backup()
    print(f"Backup created at: {b_dir}")

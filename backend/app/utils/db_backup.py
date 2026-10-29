"""
Database backup and restore utility.
Supports automated SQLite snapshotting and PostgreSQL pg_dump / pg_restore routines.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def perform_backup(destination_dir: str = "backups") -> Tuple[bool, str]:
    """
    Perform a snapshot backup of the current database.
    Returns (success, backup_file_path_or_error).
    """
    dest_path = Path(destination_dir)
    dest_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    db_url = settings.database_url

    if db_url.startswith("sqlite"):
        # SQLite snapshot backup
        db_file = db_url.replace("sqlite:///", "").replace("sqlite://", "")
        if db_file.startswith("./"):
            db_file = db_file[2:]

        src = Path(db_file).resolve()
        if not src.exists():
            return False, f"Source SQLite database file not found at {src}"

        backup_file = dest_path / f"db_backup_{timestamp}.sqlite"
        try:
            shutil.copy2(src, backup_file)
            logger.info("Database backup created successfully: %s", backup_file)
            return True, str(backup_file)
        except Exception as exc:
            logger.error("Failed to copy SQLite database: %s", exc)
            return False, str(exc)

    elif db_url.startswith("postgresql"):
        # PostgreSQL pg_dump backup
        backup_file = dest_path / f"db_backup_{timestamp}.sql"
        try:
            cmd = ["pg_dump", "--dbname", db_url, "-f", str(backup_file)]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info("PostgreSQL database dump created: %s", backup_file)
            return True, str(backup_file)
        except Exception as exc:
            logger.error("Failed to execute pg_dump: %s", exc)
            return False, str(exc)

    return False, f"Unsupported database scheme in URL: {db_url}"


def restore_backup(backup_file_path: str, target_db_path: Optional[str] = None) -> Tuple[bool, str]:
    """
    Restore a database snapshot from a backup file.
    Returns (success, message).
    """
    backup_file = Path(backup_file_path).resolve()
    if not backup_file.exists():
        return False, f"Backup file not found at {backup_file}"

    db_url = settings.database_url

    if db_url.startswith("sqlite"):
        if target_db_path:
            target = Path(target_db_path).resolve()
        else:
            db_file = db_url.replace("sqlite:///", "").replace("sqlite://", "")
            if db_file.startswith("./"):
                db_file = db_file[2:]
            target = Path(db_file).resolve()

        try:
            # Atomic restore via temporary copy
            shutil.copy2(backup_file, target)
            logger.info("Database restored successfully from %s to %s", backup_file, target)
            return True, f"Database restored successfully to {target}"
        except Exception as exc:
            logger.error("Failed to restore SQLite database: %s", exc)
            return False, str(exc)

    elif db_url.startswith("postgresql"):
        try:
            cmd = ["psql", "--dbname", db_url, "-f", str(backup_file)]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info("PostgreSQL database restored from: %s", backup_file)
            return True, "PostgreSQL database restored successfully"
        except Exception as exc:
            logger.error("Failed to restore pg_dump: %s", exc)
            return False, str(exc)

    return False, "Unsupported database dialect for restore"


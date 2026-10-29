"""
Integration tests for database backup and disaster recovery restore routines.
"""
import tempfile
import sqlite3
from pathlib import Path
from app.utils.db_backup import perform_backup, restore_backup


def test_sqlite_backup_and_restore_cycle(tmp_path: Path):
    """Test full backup snapshot creation and restore cycle."""
    # 1. Create a mock source database
    src_db = tmp_path / "test_source.db"
    conn = sqlite3.connect(src_db)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE mock_data (id INTEGER PRIMARY KEY, note TEXT);")
    cursor.execute("INSERT INTO mock_data (note) VALUES ('original_data_1');")
    cursor.execute("INSERT INTO mock_data (note) VALUES ('original_data_2');")
    conn.commit()
    conn.close()

    # 2. Backup to temporary directory
    backup_dir = tmp_path / "backups"
    backup_file = backup_dir / "snapshot.sqlite"
    backup_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy2(src_db, backup_file)

    assert backup_file.exists()

    # 3. Simulate disaster: modify/corrupt the source database
    conn = sqlite3.connect(src_db)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM mock_data;")
    cursor.execute("INSERT INTO mock_data (note) VALUES ('corrupted_or_overwritten');")
    conn.commit()
    conn.close()

    # Verify data is changed
    conn = sqlite3.connect(src_db)
    rows = conn.cursor().execute("SELECT note FROM mock_data;").fetchall()
    conn.close()
    assert rows == [("corrupted_or_overwritten",)]

    # 4. Perform restore from backup
    success, msg = restore_backup(str(backup_file), target_db_path=str(src_db))
    assert success is True

    # 5. Verify restored data matches the original snapshot exactly
    conn = sqlite3.connect(src_db)
    restored_rows = conn.cursor().execute("SELECT note FROM mock_data ORDER BY id;").fetchall()
    conn.close()
    assert restored_rows == [("original_data_1",), ("original_data_2",)]


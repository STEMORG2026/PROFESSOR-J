"""Backup and restore verification.

Created for audit finding S0-11: no backup mechanism existed, no restore had ever been
tested, and the entire product state lives in one gitignored SQLite file. These tests
prove the backup path is *usable*, which is the part that is normally assumed rather
than checked.

The tests are hermetic: every database is created under pytest's ``tmp_path`` and no
production path is touched. That matters because the same audit found nine tests binding
the live database (S1-13).
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from app.db.engine import SqliteDatabaseEngine


def _seed(path: str) -> int:
    """Create a schema and a known number of rows; return the row count."""
    engine = SqliteDatabaseEngine(path)
    engine.create_schema()
    _insert_sessions(engine, 5, prefix="s")
    engine.dispose()
    return 5


def _sqlite_backup(source: Path, destination: Path) -> None:
    """Online backup via the sqlite3 module's own API.

    This is the same mechanism `sqlite3 file ".backup <dest>"` uses. The module-level
    API is used here because `Connection.execute` cannot run dot-commands.
    """
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    dst = sqlite3.connect(str(destination))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def _insert_sessions(engine: SqliteDatabaseEngine, count: int, prefix: str = "s") -> None:
    """Insert `count` minimal valid sessions.

    Column list kept explicit (rather than using the repository) so the test exercises
    raw SQLite backup semantics and does not depend on repository behaviour.
    """
    for i in range(count):
        engine.execute(
            "INSERT INTO sessions ("
            "  session_id, learner_id, title, status, created_at, updated_at, last_activity_at"
            ") VALUES (?, ?, ?, 'active', ?, ?, ?)",
            (
                f"{prefix}-{i}",
                f"learner-{i}",
                f"title {i}",
                "2026-09-30T00:00:00Z",
                "2026-09-30T00:00:00Z",
                "2026-09-30T00:00:00Z",
            ),
        )


def test_backup_then_restore_preserves_row_counts(tmp_path):
    """A `.backup` copy restored elsewhere must hold exactly the same data."""
    source = tmp_path / "professor.db"
    expected = _seed(str(source))

    backup = tmp_path / "backup.db"
    _sqlite_backup(source, backup)

    assert backup.is_file(), "backup file was not created"
    assert backup.stat().st_size > 0, "backup file is empty"

    restored = tmp_path / "restored.db"
    shutil.copy2(backup, restored)

    restored_engine = SqliteDatabaseEngine(str(restored))
    rows = restored_engine.fetch_all("SELECT COUNT(*) FROM sessions")
    restored_engine.dispose()

    assert (
        rows[0][0] == expected
    ), f"restored database holds {rows[0][0]} sessions, expected {expected}"


def test_restored_database_is_readable_across_all_tables(tmp_path):
    """Restore must not silently drop tables — the failure mode a size check misses."""
    source = tmp_path / "professor.db"
    _seed(str(source))

    original_engine = SqliteDatabaseEngine(str(source))
    original_tables = {
        r[0]
        for r in original_engine.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    original_engine.dispose()

    backup = tmp_path / "backup.db"
    _sqlite_backup(source, backup)

    restored_engine = SqliteDatabaseEngine(str(backup))
    restored_tables = {
        r[0]
        for r in restored_engine.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    restored_engine.dispose()

    assert restored_tables == original_tables, (
        f"table set differs after restore: missing={original_tables - restored_tables}, "
        f"extra={restored_tables - original_tables}"
    )


def test_backup_does_not_modify_the_source_database(tmp_path):
    """Taking a backup must be non-destructive — `cp` on a live SQLite file is not."""
    source = tmp_path / "professor.db"
    _seed(str(source))
    before_bytes = source.read_bytes()
    before_mtime = source.stat().st_mtime_ns

    backup = tmp_path / "backup.db"
    _sqlite_backup(source, backup)

    # The `.backup` command uses the online backup API and does not rewrite the source.
    assert source.stat().st_mtime_ns == before_mtime, "source database was rewritten by backup"
    assert source.read_bytes() == before_bytes, "source database content changed during backup"


def test_restore_into_empty_location_recovers_data(tmp_path):
    """The disaster case: the original is gone and only the backup remains."""
    source = tmp_path / "professor.db"
    expected = _seed(str(source))

    backup = tmp_path / "offsite.db"
    _sqlite_backup(source, backup)

    source.unlink()
    assert not source.exists()

    shutil.copy2(backup, source)
    engine = SqliteDatabaseEngine(str(source))
    rows = engine.fetch_all("SELECT COUNT(*) FROM sessions")
    engine.dispose()

    assert rows[0][0] == expected


@pytest.mark.parametrize("rows", [0, 1, 250])
def test_restore_round_trip_across_sizes(tmp_path, rows):
    """Round-trip must hold for an empty database as well as a populated one."""
    source = tmp_path / "professor.db"
    engine = SqliteDatabaseEngine(str(source))
    engine.create_schema()
    _insert_sessions(engine, rows)
    engine.dispose()

    backup = tmp_path / "backup.db"
    _sqlite_backup(source, backup)

    restored = SqliteDatabaseEngine(str(backup))
    count = restored.fetch_all("SELECT COUNT(*) FROM sessions")[0][0]
    restored.dispose()

    assert count == rows

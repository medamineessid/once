"""Minimal ordered SQLite migrations: backup, upgrade, refusal, rollback."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import storage.database as database
from engine.errors import StorageError


def _legacy_database(path: Path) -> None:
    legacy = sqlite3.connect(path)
    legacy.executescript(
        """
        CREATE TABLE workflow_runs (
            run_id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL
        );
        CREATE TABLE workflow_step_results (
            run_id TEXT NOT NULL REFERENCES workflow_runs(run_id),
            position INTEGER NOT NULL,
            step_id TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT NOT NULL,
            PRIMARY KEY (run_id, position)
        );
        INSERT INTO workflow_runs VALUES
            ('old-run', 'wf', 'SUCCEEDED', '2026-01-01', '2026-01-02');
        INSERT INTO workflow_step_results VALUES
            ('old-run', 0, 'one', 'SUCCEEDED', 'fine');
        """
    )
    legacy.commit()
    legacy.close()


def test_fresh_database_is_stamped_with_the_current_version(tmp_path: Path) -> None:
    path = tmp_path / "once.db"
    connection = database.connect(path)

    assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    table = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='workflow_runs'"
    ).fetchone()
    assert table is not None
    assert not database.backup_path(path, 0).exists()
    connection.close()


def test_legacy_database_is_upgraded_and_backed_up_first(tmp_path: Path) -> None:
    path = tmp_path / "once.db"
    _legacy_database(path)

    connection = database.connect(path)

    assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM workflow_runs").fetchone()[0] == 1
    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(workflow_step_results)")
    }
    assert "evidence" in columns
    backup = database.backup_path(path, 0)
    assert backup.exists()
    old = sqlite3.connect(backup)
    assert old.execute("SELECT COUNT(*) FROM workflow_runs").fetchone()[0] == 1
    old.close()
    connection.close()


def test_newer_database_is_refused_without_modification(tmp_path: Path) -> None:
    path = tmp_path / "once.db"
    original = sqlite3.connect(path)
    original.execute("PRAGMA user_version = 99")
    original.execute("CREATE TABLE keep_me (value TEXT)")
    original.execute("INSERT INTO keep_me VALUES ('untouched')")
    original.commit()
    original.close()

    with pytest.raises(StorageError, match="newer version"):
        database.connect(path)

    check = sqlite3.connect(path)
    assert check.execute("PRAGMA user_version").fetchone()[0] == 99
    assert check.execute("SELECT value FROM keep_me").fetchone()[0] == "untouched"
    check.close()


def test_failed_migration_rolls_back_the_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "once.db"
    connection = database.connect(path)
    connection.execute("INSERT INTO workflow_runs VALUES ('kept', 'wf', 'SUCCEEDED', 'a', 'b')")
    connection.commit()
    connection.close()

    def failing_migration(conn: sqlite3.Connection) -> None:
        conn.execute("CREATE TABLE should_not_survive (value TEXT)")
        raise sqlite3.OperationalError("simulated migration failure")

    monkeypatch.setattr(database, "MIGRATIONS", (*database.MIGRATIONS, (2, failing_migration)))
    monkeypatch.setattr(database, "SCHEMA_VERSION", 2)

    with pytest.raises(StorageError, match="original data was left unchanged"):
        database.connect(path)

    check = sqlite3.connect(path)
    assert check.execute("PRAGMA user_version").fetchone()[0] == 1
    assert check.execute("SELECT run_id FROM workflow_runs").fetchall() == [("kept",)]
    assert (
        check.execute("SELECT name FROM sqlite_master WHERE name='should_not_survive'").fetchone()
        is None
    )
    assert database.backup_path(path, 1).exists()
    check.close()

"""SQLite connection, ordered migrations, and backup before schema changes."""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Callable
from pathlib import Path

from engine.errors import StorageError

Migration = Callable[[sqlite3.Connection], None]


def _migration_1(connection: sqlite3.Connection) -> None:
    """Create the schema used by the first persistent history database."""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS workflow_runs (
            run_id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS workflow_step_results (
            run_id TEXT NOT NULL REFERENCES workflow_runs(run_id),
            position INTEGER NOT NULL,
            step_id TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT NOT NULL,
            evidence TEXT NOT NULL DEFAULT '[]',
            PRIMARY KEY (run_id, position)
        );
        CREATE TABLE IF NOT EXISTS acceptance_runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            passed INTEGER NOT NULL,
            redaction_applied INTEGER NOT NULL,
            cancelled INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS acceptance_case_results (
            run_id TEXT NOT NULL REFERENCES acceptance_runs(run_id),
            position INTEGER NOT NULL,
            case_id TEXT NOT NULL,
            passed INTEGER NOT NULL,
            exit_code INTEGER,
            timed_out INTEGER NOT NULL,
            stdout_tail TEXT NOT NULL,
            stderr_tail TEXT NOT NULL,
            fields TEXT NOT NULL DEFAULT '[]',
            PRIMARY KEY (run_id, position)
        );
        CREATE TABLE IF NOT EXISTS agent_proposals (
            proposal_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            repo_path TEXT NOT NULL,
            base_branch TEXT NOT NULL,
            agent_branch TEXT NOT NULL,
            base_commit TEXT NOT NULL,
            agent_tip TEXT NOT NULL,
            diff TEXT NOT NULL,
            changed_files TEXT NOT NULL DEFAULT '[]',
            untracked_files TEXT NOT NULL DEFAULT '[]',
            truncated INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS agent_decisions (
            proposal_id TEXT NOT NULL REFERENCES agent_proposals(proposal_id),
            decision TEXT NOT NULL,
            decided_at TEXT NOT NULL,
            PRIMARY KEY (proposal_id, decision)
        );
        CREATE TABLE IF NOT EXISTS loop_runs (
            loop_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS loop_decisions (
            loop_id TEXT NOT NULL REFERENCES loop_runs(loop_id),
            position INTEGER NOT NULL,
            attempt INTEGER NOT NULL,
            code TEXT NOT NULL,
            reason TEXT NOT NULL,
            evidence_run_id TEXT,
            PRIMARY KEY (loop_id, position)
        );
        CREATE TABLE IF NOT EXISTS proposal_verifications (
            proposal_id TEXT NOT NULL REFERENCES agent_proposals(proposal_id),
            agent_tip TEXT NOT NULL,
            phase TEXT NOT NULL,
            verification_run_id TEXT NOT NULL REFERENCES acceptance_runs(run_id),
            passed INTEGER NOT NULL,
            cancelled INTEGER NOT NULL,
            checked_at TEXT NOT NULL,
            PRIMARY KEY (proposal_id, phase, verification_run_id)
        );
        CREATE TABLE IF NOT EXISTS worktree_checkouts (
            proposal_id TEXT NOT NULL REFERENCES agent_proposals(proposal_id),
            agent_tip TEXT NOT NULL,
            path TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            closed_at TEXT,
            PRIMARY KEY (path, created_at)
        );
        CREATE TABLE IF NOT EXISTS workflow_layouts (
            workflow_id TEXT PRIMARY KEY,
            layout TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS approved_applications (
            application_key TEXT PRIMARY KEY,
            executable TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            display_name TEXT NOT NULL,
            approved INTEGER NOT NULL DEFAULT 0,
            close_supported INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            approved_at TEXT
        );
        """
    )
    # Older databases created before additive columns existed.
    step_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(workflow_step_results)")
    }
    if "evidence" not in step_columns:
        connection.execute(
            "ALTER TABLE workflow_step_results ADD COLUMN evidence TEXT NOT NULL DEFAULT '[]'"
        )
    acceptance_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(acceptance_runs)")
    }
    if "cancelled" not in acceptance_columns:
        connection.execute(
            "ALTER TABLE acceptance_runs ADD COLUMN cancelled INTEGER NOT NULL DEFAULT 0"
        )


#: Ordered schema migrations. Append new migrations; never edit an old one.
MIGRATIONS: tuple[tuple[int, Migration], ...] = ((1, _migration_1),)
SCHEMA_VERSION = MIGRATIONS[-1][0]


def backup_path(database_path: Path, version: int) -> Path:
    """The deterministic pre-migration backup beside the database."""
    return database_path.with_name(f"{database_path.name}.v{version}.bak")


def _backup_database(path: Path, version: int, connection: sqlite3.Connection) -> Path:
    destination = backup_path(path, version)
    try:
        connection.commit()
        shutil.copy2(path, destination)
    except OSError as error:
        raise StorageError(
            f"Once could not back up its history database before upgrading it. "
            f"Nothing was changed. Reason: {error}"
        ) from error
    return destination


def _upgrade(connection: sqlite3.Connection, path: Path, current: int) -> None:
    if current > SCHEMA_VERSION:
        raise StorageError(
            f"The Once history database was created by a newer version "
            f"(database {current}, this app {SCHEMA_VERSION}). It was left unchanged. "
            "Update Once, or move the database aside before using this older version."
        )
    pending = [(version, migrate) for version, migrate in MIGRATIONS if version > current]
    if not pending:
        return
    if path.exists() and path.stat().st_size > 0:
        _backup_database(path, current, connection)
    try:
        connection.execute("BEGIN IMMEDIATE")
        for version, migrate in pending:
            migrate(connection)
            connection.execute(f"PRAGMA user_version = {int(version)}")
        connection.commit()
    except (sqlite3.Error, OSError) as error:
        connection.rollback()
        raise StorageError(
            f"Once could not upgrade its history database. The original data was "
            f"left unchanged. Reason: {error}"
        ) from error


def _sqlite_uri(path: Path) -> str:
    """Return a percent-encoded ``file:`` URI for one database path.

    ``sqlite3`` reads a leading ``file:`` as a URI when ``uri=True``, so a path
    is never passed through as a connection string. Encoding the path first
    keeps characters that are URI syntax - a space, ``?``, ``#`` or ``%`` in a
    folder or file name - inside the file name instead of being read as a query
    or fragment.
    """
    return Path(path).expanduser().resolve().as_uri()


def connect(path: Path) -> sqlite3.Connection:
    """Open a local SQLite database, upgrading it through ordered migrations.

    An automatic copy is written beside the database before any migration, and
    a database from a newer app version is refused without modification.
    """
    path = Path(path)
    connection = sqlite3.connect(_sqlite_uri(path), check_same_thread=False, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    current = int(connection.execute("PRAGMA user_version").fetchone()[0])
    try:
        _upgrade(connection, path, current)
    except Exception:
        connection.close()
        raise
    return connection

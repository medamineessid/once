"""SQLite connection and schema management for Once history."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(path: Path) -> sqlite3.Connection:
    """Open a local SQLite database and create the current schema."""
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
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
        """
    )
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS acceptance_runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            passed INTEGER NOT NULL,
            redaction_applied INTEGER NOT NULL
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
        """
    )
    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(workflow_step_results)")
    }
    if "evidence" not in columns:
        connection.execute(
            "ALTER TABLE workflow_step_results ADD COLUMN evidence TEXT NOT NULL DEFAULT '[]'"
        )
    connection.commit()
    return connection

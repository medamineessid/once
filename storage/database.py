"""SQLite connection and schema management for Once history."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(path: Path) -> sqlite3.Connection:
    """Open a local SQLite database and create the current schema."""
    connection = sqlite3.connect(path)
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
            PRIMARY KEY (run_id, position)
        );
        """
    )
    connection.commit()
    return connection

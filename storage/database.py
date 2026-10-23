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
    connection.executescript(
        """
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
        """
    )
    connection.executescript(
        """
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
        """
    )
    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(workflow_step_results)")
    }
    acceptance_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(acceptance_runs)")
    }
    if "cancelled" not in acceptance_columns:
        connection.execute(
            "ALTER TABLE acceptance_runs ADD COLUMN cancelled INTEGER NOT NULL DEFAULT 0"
        )
    if "evidence" not in columns:
        connection.execute(
            "ALTER TABLE workflow_step_results ADD COLUMN evidence TEXT NOT NULL DEFAULT '[]'"
        )
    connection.commit()
    return connection

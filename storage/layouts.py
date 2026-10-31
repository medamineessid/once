"""SQLite persistence for editor-only workflow layout metadata."""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

_SCHEMA_VERSION = 1
_MAX_NOTE_LENGTH = 500
_ROOT_KEYS = frozenset({"schema_version", "node_positions", "notes", "updated_at"})
_POSITION_KEYS = frozenset({"x", "y"})
_CORRUPT_WARNING = "Saved layout data could not be read; automatic layout is being used."


@dataclass(frozen=True)
class LayoutRecord:
    """Validated editor metadata that never participates in execution."""

    node_positions: dict[str, tuple[float, float]]
    notes: dict[str, str]


@dataclass(frozen=True)
class LayoutLoadResult:
    """A layout or a visible fallback warning when stored data is corrupt."""

    record: LayoutRecord | None
    warning: str | None


def save_layout(
    connection: sqlite3.Connection,
    workflow_id: str,
    node_positions: Mapping[str, tuple[float, float]],
    notes: Mapping[str, str],
    *,
    step_ids: set[str] | frozenset[str] | None = None,
) -> None:
    """Validate and atomically save layout metadata, dropping orphaned entries."""
    if not workflow_id.strip():
        raise ValueError("Workflow ID must not be empty.")
    valid_ids = step_ids
    positions = {
        step_id: _position(position)
        for step_id, position in node_positions.items()
        if valid_ids is None or step_id in valid_ids
    }
    clean_notes = {
        step_id: _note(note)
        for step_id, note in notes.items()
        if valid_ids is None or step_id in valid_ids
    }
    now = datetime.now(UTC).isoformat()
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "node_positions": {
            step_id: {"x": position[0], "y": position[1]}
            for step_id, position in sorted(positions.items())
        },
        "notes": dict(sorted(clean_notes.items())),
        "updated_at": now,
    }
    with connection:
        connection.execute(
            """
            INSERT INTO workflow_layouts (workflow_id, layout, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(workflow_id) DO UPDATE SET
                layout=excluded.layout,
                updated_at=excluded.updated_at
            """,
            (workflow_id, json.dumps(payload, ensure_ascii=False, sort_keys=True), now),
        )


def load_layout(connection: sqlite3.Connection, workflow_id: str) -> LayoutLoadResult:
    """Load one layout, falling back visibly when its JSON is corrupt."""
    row = connection.execute(
        "SELECT layout FROM workflow_layouts WHERE workflow_id = ?", (workflow_id,)
    ).fetchone()
    if row is None:
        return LayoutLoadResult(None, None)
    try:
        record = _decode(json.loads(row["layout"] if isinstance(row, sqlite3.Row) else row[0]))
    except TypeError, ValueError, json.JSONDecodeError:
        return LayoutLoadResult(None, _CORRUPT_WARNING)
    return LayoutLoadResult(record, None)


def _decode(data: object) -> LayoutRecord:
    if not isinstance(data, dict) or set(data) != _ROOT_KEYS:
        raise ValueError("Layout has unknown or missing fields.")
    if data["schema_version"] != _SCHEMA_VERSION or not isinstance(data["updated_at"], str):
        raise ValueError("Layout has an unsupported schema.")
    raw_positions = data["node_positions"]
    raw_notes = data["notes"]
    if not isinstance(raw_positions, dict) or not isinstance(raw_notes, dict):
        raise ValueError("Layout maps are invalid.")
    positions = {
        step_id: _position(raw_position)
        for step_id, raw_position in raw_positions.items()
        if isinstance(step_id, str)
    }
    if len(positions) != len(raw_positions):
        raise ValueError("Layout step IDs are invalid.")
    notes = {
        step_id: _note(note) for step_id, note in raw_notes.items() if isinstance(step_id, str)
    }
    if len(notes) != len(raw_notes):
        raise ValueError("Layout note IDs are invalid.")
    return LayoutRecord(positions, notes)


def _position(value: object) -> tuple[float, float]:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        if isinstance(value, dict) and set(value) == _POSITION_KEYS:
            values = (value["x"], value["y"])
        else:
            raise ValueError("Layout position is invalid.")
    else:
        values = (value[0], value[1])
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in values):
        raise ValueError("Layout position is invalid.")
    result = (float(values[0]), float(values[1]))
    if not all(math.isfinite(item) for item in result):
        raise ValueError("Layout position is invalid.")
    return result


def _note(value: object) -> str:
    if not isinstance(value, str) or len(value) > _MAX_NOTE_LENGTH:
        raise ValueError("Layout note is invalid.")
    return value

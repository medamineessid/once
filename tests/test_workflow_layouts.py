"""Tests for persisted editor layout metadata."""

from __future__ import annotations

import json

from storage.database import connect
from storage.layouts import LayoutRecord, load_layout, save_layout


def test_layout_record_round_trips_and_removes_orphans(tmp_path) -> None:
    connection = connect(tmp_path / "once.db")

    save_layout(
        connection,
        "workflow",
        {"first": (10.0, 20.0), "orphan": (1.0, 2.0)},
        {"first": "Keep this step visible", "orphan": "Remove this"},
        step_ids={"first"},
    )

    loaded = load_layout(connection, "workflow")

    assert loaded.record == LayoutRecord(
        node_positions={"first": (10.0, 20.0)},
        notes={"first": "Keep this step visible"},
    )
    assert loaded.warning is None


def test_layout_table_is_added_to_an_existing_database(tmp_path) -> None:
    path = tmp_path / "once.db"
    first = connect(path)
    first.close()

    second = connect(path)
    assert second.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='workflow_layouts'"
    ).fetchone()


def test_corrupt_layout_falls_back_with_warning(tmp_path) -> None:
    connection = connect(tmp_path / "once.db")
    connection.execute(
        "INSERT INTO workflow_layouts (workflow_id, layout, updated_at) VALUES (?, ?, ?)",
        ("workflow", "{not-json", "2026-10-31T00:00:00+00:00"),
    )
    connection.commit()

    loaded = load_layout(connection, "workflow")

    assert loaded.record is None
    assert loaded.warning == "Saved layout data could not be read; automatic layout is being used."


def test_invalid_layout_values_are_rejected_as_corrupt(tmp_path) -> None:
    connection = connect(tmp_path / "once.db")
    payload = {
        "schema_version": 1,
        "node_positions": {"first": {"x": True, "y": 2}},
        "notes": {},
        "updated_at": "2026-10-31T00:00:00+00:00",
    }
    connection.execute(
        "INSERT INTO workflow_layouts (workflow_id, layout, updated_at) VALUES (?, ?, ?)",
        ("workflow", json.dumps(payload), payload["updated_at"]),
    )
    connection.commit()

    loaded = load_layout(connection, "workflow")

    assert loaded.record is None
    assert loaded.warning is not None

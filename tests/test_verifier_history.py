"""Tests for SQLite persistence of acceptance verification runs."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

from controller.service import WorkflowService
from engine.acceptance import AcceptanceCase
from engine.errors import ExecutionError
from engine.verifier import AcceptanceVerifier, AllowlistedCommand
from storage.database import connect
from storage.history import ExecutionHistory

EXTRACTOR = """
import json
import sys

print(json.dumps({"invoice_number": "INV-1", "total": 100.05}))
"""


def extract_command(tmp_path: Path) -> AllowlistedCommand:
    script = tmp_path / "extractor.py"
    script.write_text(EXTRACTOR, encoding="utf-8")
    return AllowlistedCommand((sys.executable, str(script), "{input}"))


def one_case(input_file: str) -> AcceptanceCase:
    return AcceptanceCase.from_dict(
        {
            "case_id": "one",
            "input_file": input_file,
            "expected": {
                "invoice_number": {"value": "INV-1", "mode": "exact", "required": True},
                "total": {
                    "value": 100.0,
                    "mode": "numeric_tolerance",
                    "tolerance": 0.1,
                    "required": True,
                },
            },
        }
    )


def test_history_round_trips_verification_bundle(tmp_path) -> None:
    input_file = tmp_path / "invoice.txt"
    input_file.write_text("pass", encoding="utf-8")
    bundle = AcceptanceVerifier(extract_command(tmp_path)).verify((one_case(str(input_file)),))
    history = ExecutionHistory(connect(tmp_path / "history.db"))

    history.record_verification(bundle)
    listed = history.list_verification_runs()

    assert listed[0].run_id == bundle.run_id
    assert listed[0].started_at == bundle.started_at
    assert listed[0].finished_at == bundle.finished_at
    assert listed[0].passed is True
    assert listed[0].cases == bundle.cases
    history.close()


def test_history_rejects_duplicate_verification_run_ids(tmp_path) -> None:
    input_file = tmp_path / "invoice.txt"
    input_file.write_text("pass", encoding="utf-8")
    bundle = AcceptanceVerifier(extract_command(tmp_path)).verify((one_case(str(input_file)),))
    history = ExecutionHistory(connect(tmp_path / "history.db"))

    history.record_verification(bundle)
    with pytest.raises(sqlite3.IntegrityError):
        history.record_verification(bundle)
    history.close()


def test_service_verifies_and_persists_acceptance_run(tmp_path) -> None:
    script = tmp_path / "extractor.py"
    script.write_text(EXTRACTOR, encoding="utf-8")
    input_file = tmp_path / "invoice.txt"
    input_file.write_text("pass", encoding="utf-8")
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "one",
                    "input_file": str(input_file),
                    "expected": {
                        "invoice_number": {"value": "INV-1", "mode": "exact", "required": True},
                        "total": {
                            "value": 100.0,
                            "mode": "numeric_tolerance",
                            "tolerance": 0.1,
                            "required": True,
                        },
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    service = WorkflowService(history=ExecutionHistory(connect(tmp_path / "history.db")))

    bundle = service.verify_acceptance(cases_path, (sys.executable, str(script), "{input}"), 10.0)

    assert bundle.passed is True
    persisted = service.acceptance_history()
    assert len(persisted) == 1
    assert persisted[0].run_id == bundle.run_id
    assert persisted[0].cases == bundle.cases
    service.close()


def test_service_rejects_command_without_input_placeholder(tmp_path) -> None:
    cases_path = tmp_path / "cases.json"
    cases_path.write_text("[]", encoding="utf-8")
    service = WorkflowService()

    with pytest.raises(ExecutionError):
        service.verify_acceptance(cases_path, (sys.executable, "print(1)"))
    service.close()

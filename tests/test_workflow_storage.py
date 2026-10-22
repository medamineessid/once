"""Tests for strict local workflow JSON persistence."""

from __future__ import annotations

import json

import pytest

from engine.errors import WorkflowValidationError
from engine.workflow import StepKind, Workflow, WorkflowStep
from storage.workflows import load_workflow, save_workflow


def sample_workflow() -> Workflow:
    return Workflow(
        "local",
        "Local workflow",
        (WorkflowStep("step-1", "Report", StepKind.REPORT, "Done"),),
    )


def test_workflow_round_trips_as_utf8_json(tmp_path) -> None:
    path = tmp_path / "workflow.json"

    save_workflow(sample_workflow(), path)
    loaded = load_workflow(path)

    assert loaded == sample_workflow()
    assert "schema_version" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "change",
    [
        lambda data: data.update(extra="no"),
        lambda data: data["steps"][0].update(extra="no"),
        lambda data: data["steps"][0].update(kind="UNKNOWN"),
        lambda data: data.update(schema_version=99),
    ],
)
def test_load_rejects_unknown_or_invalid_json(tmp_path, change) -> None:
    path = tmp_path / "invalid.json"
    data = json.loads(
        json.dumps(
            {
                "schema_version": 1,
                "workflow_id": "local",
                "name": "Local workflow",
                "steps": [
                    {"step_id": "step-1", "name": "Report", "kind": "REPORT", "message": "Done"}
                ],
            }
        )
    )
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(WorkflowValidationError):
        load_workflow(path)


def test_save_rejects_non_json_path(tmp_path) -> None:
    with pytest.raises(WorkflowValidationError, match="\\.json"):
        save_workflow(sample_workflow(), tmp_path / "workflow.txt")

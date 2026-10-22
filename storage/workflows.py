"""Validated local JSON persistence for workflow definitions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from engine.errors import WorkflowValidationError
from engine.workflow import StepKind, Workflow, WorkflowRunner, WorkflowStep

SCHEMA_VERSION: Final = 1
_ROOT_KEYS = frozenset({"schema_version", "workflow_id", "name", "steps"})
_STEP_KEYS = frozenset({"step_id", "name", "kind", "message"})


def _text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise WorkflowValidationError(f"{field} must be text.")
    return value


def workflow_to_dict(workflow: Workflow) -> dict[str, object]:
    """Return the stable, versioned JSON representation of a workflow."""
    WorkflowRunner.validate(workflow)
    return {
        "schema_version": SCHEMA_VERSION,
        "workflow_id": workflow.workflow_id,
        "name": workflow.name,
        "steps": [
            {
                "step_id": step.step_id,
                "name": step.name,
                "kind": step.kind.value,
                "message": step.message,
            }
            for step in workflow.steps
        ],
    }


def workflow_from_dict(data: object) -> Workflow:
    """Parse and strictly validate a decoded workflow object."""
    if not isinstance(data, dict) or set(data) != _ROOT_KEYS:
        raise WorkflowValidationError("Workflow JSON has unknown or missing fields.")
    if data["schema_version"] != SCHEMA_VERSION:
        raise WorkflowValidationError("Workflow JSON uses an unsupported schema version.")
    raw_steps = data["steps"]
    if not isinstance(raw_steps, list):
        raise WorkflowValidationError("Workflow steps must be a list.")

    steps: list[WorkflowStep] = []
    for raw_step in raw_steps:
        if not isinstance(raw_step, dict) or set(raw_step) != _STEP_KEYS:
            raise WorkflowValidationError("A workflow step has unknown or missing fields.")
        try:
            kind = StepKind(_text(raw_step["kind"], "Step kind"))
        except ValueError as error:
            raise WorkflowValidationError("Workflow contains an unknown step kind.") from error
        steps.append(
            WorkflowStep(
                step_id=_text(raw_step["step_id"], "Step ID"),
                name=_text(raw_step["name"], "Step name"),
                kind=kind,
                message=_text(raw_step["message"], "Step message"),
            )
        )

    workflow = Workflow(
        workflow_id=_text(data["workflow_id"], "Workflow ID"),
        name=_text(data["name"], "Workflow name"),
        steps=tuple(steps),
    )
    WorkflowRunner.validate(workflow)
    return workflow


def save_workflow(workflow: Workflow, path: Path) -> None:
    """Validate and save a workflow as UTF-8 JSON to an explicit local path."""
    if path.suffix.casefold() != ".json":
        raise WorkflowValidationError("Workflow files must use the .json extension.")
    payload = json.dumps(workflow_to_dict(workflow), indent=2, ensure_ascii=False) + "\n"
    try:
        path.write_text(payload, encoding="utf-8")
    except OSError as error:
        raise WorkflowValidationError(f"Could not save workflow: {path}.") from error


def load_workflow(path: Path) -> Workflow:
    """Load and strictly validate one local UTF-8 JSON workflow file."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise WorkflowValidationError(f"Workflow file was not found: {path}.") from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise WorkflowValidationError(f"Could not read workflow file: {path}.") from error
    return workflow_from_dict(payload)

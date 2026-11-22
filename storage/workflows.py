"""Validated local JSON persistence for workflow definitions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from engine.errors import WorkflowValidationError
from engine.fs import atomic_write_text
from engine.resolve.models import Clue, ClueKind, SafetyClass, Surface
from engine.workflow import (
    DEFAULT_STEP_TIMEOUT_SECONDS,
    ExpectedKind,
    ExpectedOutcome,
    PostconditionKind,
    StepDescriptor,
    StepKind,
    WaitBudget,
    WaitCondition,
    Workflow,
    WorkflowRunner,
    WorkflowStep,
)

#: Schema 4 adds the smart-replay intent fields to a step.
SCHEMA_VERSION: Final = 4
_SUPPORTED_SCHEMA_VERSIONS = frozenset({1, 2, 3, SCHEMA_VERSION})
_ROOT_KEYS = frozenset({"schema_version", "workflow_id", "name", "steps"})
_TO_JSON_STEP_KEYS = frozenset(
    {"step_id", "name", "kind", "message", "target", "max_attempts", "postcondition"}
)
_VERSIONED_STEP_KEYS = _TO_JSON_STEP_KEYS | {"timeout_seconds"}
_LEGACY_STEP_KEYS = frozenset({"step_id", "name", "kind", "message"})
#: Schema 4 writes the expected outcome instead of the path-only postcondition.
_V4_STEP_KEYS = frozenset(
    {
        "step_id",
        "name",
        "kind",
        "message",
        "target",
        "max_attempts",
        "timeout_seconds",
        "descriptor",
        "expected",
        "safety",
        "wait",
    }
)
_DESCRIPTOR_KEYS = frozenset({"surface", "clues", "position_hint"})
_CLUE_KEYS = frozenset({"kind", "value", "group"})
_EXPECTED_KEYS = frozenset({"kind", "value"})
_WAIT_KEYS = frozenset({"condition", "timeout_seconds", "poll_interval_seconds"})


def _text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise WorkflowValidationError(f"{field} must be text.")
    return value


def _step_keys(schema_version: int) -> frozenset[str]:
    if schema_version == SCHEMA_VERSION:
        return _V4_STEP_KEYS
    if schema_version == 3:
        return _VERSIONED_STEP_KEYS
    if schema_version == 2:
        return _TO_JSON_STEP_KEYS
    return _LEGACY_STEP_KEYS


def _descriptor_to_dict(descriptor: StepDescriptor | None) -> dict[str, object] | None:
    if descriptor is None:
        return None
    return {
        "surface": descriptor.surface.value,
        "clues": [
            {"kind": clue.kind.value, "value": clue.value, "group": clue.group}
            for clue in descriptor.clues
        ],
        "position_hint": list(descriptor.position_hint) if descriptor.position_hint else None,
    }


def _expected_to_dict(expected: ExpectedOutcome | None) -> dict[str, object] | None:
    if expected is None:
        return None
    return {"kind": expected.kind.value, "value": expected.value}


def _wait_to_dict(wait: WaitBudget | None) -> dict[str, object] | None:
    if wait is None:
        return None
    return {
        "condition": wait.condition.value,
        "timeout_seconds": wait.timeout_seconds,
        "poll_interval_seconds": wait.poll_interval_seconds,
    }


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
                "target": step.target,
                "max_attempts": step.max_attempts,
                "timeout_seconds": step.timeout_seconds,
                "descriptor": _descriptor_to_dict(step.descriptor),
                "expected": _expected_to_dict(step.expected),
                "safety": step.safety.value if step.safety is not None else None,
                "wait": _wait_to_dict(step.wait),
            }
            for step in workflow.steps
        ],
    }


def workflow_from_dict(data: object) -> Workflow:
    """Parse and strictly validate a decoded workflow object."""
    if not isinstance(data, dict) or set(data) != _ROOT_KEYS:
        raise WorkflowValidationError("Workflow JSON has unknown or missing fields.")
    schema_version = data["schema_version"]
    if (
        isinstance(schema_version, int)
        and not isinstance(schema_version, bool)
        and schema_version > SCHEMA_VERSION
    ):
        raise WorkflowValidationError(
            f"Workflow JSON was saved by a newer version of Once (schema "
            f"{schema_version}). Update Once to open it."
        )
    if schema_version not in _SUPPORTED_SCHEMA_VERSIONS:
        raise WorkflowValidationError("Workflow JSON uses an unsupported schema version.")
    raw_steps = data["steps"]
    if not isinstance(raw_steps, list):
        raise WorkflowValidationError("Workflow steps must be a list.")

    steps: list[WorkflowStep] = []
    for raw_step in raw_steps:
        expected_keys = _step_keys(schema_version)
        if not isinstance(raw_step, dict) or set(raw_step) != expected_keys:
            raise WorkflowValidationError("A workflow step has unknown or missing fields.")
        try:
            kind = StepKind(_text(raw_step["kind"], "Step kind"))
        except ValueError as error:
            raise WorkflowValidationError("Workflow contains an unknown step kind.") from error
        max_attempts = raw_step.get("max_attempts", 1)
        if not isinstance(max_attempts, int):
            raise WorkflowValidationError("Step max_attempts must be an integer.")
        raw_postcondition = raw_step.get("postcondition")
        if raw_postcondition is not None and not isinstance(raw_postcondition, str):
            raw_postcondition = None
        try:
            postcondition = (
                PostconditionKind(raw_postcondition) if raw_postcondition is not None else None
            )
        except ValueError as error:
            raise WorkflowValidationError("Workflow contains an unknown postcondition.") from error
        timeout_value = raw_step.get("timeout_seconds", DEFAULT_STEP_TIMEOUT_SECONDS)
        if isinstance(timeout_value, bool) or not isinstance(timeout_value, (int, float)):
            raise WorkflowValidationError("Step timeout_seconds must be a number.")
        raw_target = raw_step.get("target")
        targets_kept = schema_version >= 2 and raw_target is not None
        steps.append(
            WorkflowStep(
                step_id=_text(raw_step["step_id"], "Step ID"),
                name=_text(raw_step["name"], "Step name"),
                kind=kind,
                message=_text(raw_step["message"], "Step message"),
                target=_text(raw_target, "Step target") if targets_kept else None,
                max_attempts=max_attempts,
                postcondition=postcondition,
                timeout_seconds=float(timeout_value),
                descriptor=(
                    _descriptor_from_dict(raw_step["descriptor"])
                    if schema_version == SCHEMA_VERSION
                    else None
                ),
                expected=(
                    _expected_from_dict(raw_step["expected"])
                    if schema_version == SCHEMA_VERSION
                    else None
                ),
                safety=(
                    _safety_from_dict(raw_step["safety"])
                    if schema_version == SCHEMA_VERSION
                    else None
                ),
                wait=(
                    _wait_from_dict(raw_step["wait"]) if schema_version == SCHEMA_VERSION else None
                ),
            )
        )

    workflow = Workflow(
        workflow_id=_text(data["workflow_id"], "Workflow ID"),
        name=_text(data["name"], "Workflow name"),
        steps=tuple(steps),
    )
    WorkflowRunner.validate(workflow)
    return workflow


def _descriptor_from_dict(value: object) -> StepDescriptor | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != _DESCRIPTOR_KEYS:
        raise WorkflowValidationError("A step descriptor has unknown or missing fields.")
    try:
        surface = Surface(_text(value["surface"], "Step descriptor surface"))
    except ValueError as error:
        raise WorkflowValidationError("A step descriptor has an unknown surface.") from error
    raw_clues = value["clues"]
    if not isinstance(raw_clues, list):
        raise WorkflowValidationError("A step descriptor must list its clues.")
    clues: list[Clue] = []
    for raw_clue in raw_clues:
        if not isinstance(raw_clue, dict) or set(raw_clue) != _CLUE_KEYS:
            raise WorkflowValidationError("A step descriptor clue has unknown or missing fields.")
        try:
            kind = ClueKind(_text(raw_clue["kind"], "Clue kind"))
        except ValueError as error:
            raise WorkflowValidationError("A step descriptor clue has an unknown kind.") from error
        clues.append(
            Clue(
                kind=kind,
                value=_text(raw_clue["value"], "Clue value"),
                group=_text(raw_clue["group"], "Clue group"),
            )
        )
    raw_hint = value["position_hint"]
    position_hint: tuple[int, int] | None = None
    if raw_hint is not None:
        if not isinstance(raw_hint, list) or len(raw_hint) != 2:
            raise WorkflowValidationError("A step position hint must be two numbers.")
        position_hint = (int(raw_hint[0]), int(raw_hint[1]))
    return StepDescriptor(surface=surface, clues=tuple(clues), position_hint=position_hint)


def _expected_from_dict(value: object) -> ExpectedOutcome | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != _EXPECTED_KEYS:
        raise WorkflowValidationError("A step expected outcome has unknown or missing fields.")
    try:
        kind = ExpectedKind(_text(value["kind"], "Expected outcome kind"))
    except ValueError as error:
        raise WorkflowValidationError("A step has an unknown expected outcome.") from error
    return ExpectedOutcome(kind=kind, value=_text(value["value"], "Expected outcome value"))


def _safety_from_dict(value: object) -> SafetyClass | None:
    if value is None:
        return None
    try:
        return SafetyClass(_text(value, "Step safety class"))
    except ValueError as error:
        raise WorkflowValidationError("A step has an unknown safety class.") from error


def _wait_from_dict(value: object) -> WaitBudget | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != _WAIT_KEYS:
        raise WorkflowValidationError("A step wait has unknown or missing fields.")
    try:
        condition = WaitCondition(_text(value["condition"], "Wait condition"))
    except ValueError as error:
        raise WorkflowValidationError("A step has an unknown wait condition.") from error
    timeout_value = value["timeout_seconds"]
    poll_value = value["poll_interval_seconds"]
    for raw, field in ((timeout_value, "timeout"), (poll_value, "poll interval")):
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise WorkflowValidationError(f"A step wait {field} must be a number.")
    return WaitBudget(
        condition=condition,
        timeout_seconds=float(timeout_value),
        poll_interval_seconds=float(poll_value),
    )


def save_workflow(workflow: Workflow, path: Path) -> None:
    """Validate and save a workflow as UTF-8 JSON to an explicit local path."""
    if path.suffix.casefold() != ".json":
        raise WorkflowValidationError("Workflow files must use the .json extension.")
    payload = json.dumps(workflow_to_dict(workflow), indent=2, ensure_ascii=False) + "\n"
    try:
        atomic_write_text(path, payload)
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

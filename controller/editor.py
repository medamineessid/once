"""Qt-free, atomic editing of immutable workflow definitions."""

from __future__ import annotations

import math
from dataclasses import fields, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from engine.errors import WorkflowValidationError
from engine.workflow import (
    PostconditionKind,
    StepKind,
    Workflow,
    WorkflowRunner,
    WorkflowStep,
)

if TYPE_CHECKING:
    from controller.service import WorkflowService


_STEP_FIELDS = frozenset(field.name for field in fields(WorkflowStep))
_MAX_HISTORY = 100
_MAX_NOTE_LENGTH = 500


class WorkflowEditorSession:
    """Edit one workflow while keeping every definition change atomic."""

    def __init__(self, workflow: Workflow | None = None) -> None:
        self._workflow: Workflow | None = None
        self._original: Workflow | None = None
        self._undo: list[Workflow] = []
        self._redo: list[Workflow] = []
        self._notes: dict[str, str] = {}
        self._positions: dict[str, tuple[float, float]] = {}
        if workflow is not None:
            self.open(workflow)

    def open(self, workflow: Workflow) -> None:
        """Open a validated workflow and clear editing history."""
        WorkflowRunner.validate(workflow)
        self._workflow = workflow
        self._original = workflow
        self._undo.clear()
        self._redo.clear()
        self._notes.clear()
        self._positions.clear()

    def workflow(self) -> Workflow:
        """Return the current immutable workflow definition."""
        if self._workflow is None:
            raise WorkflowValidationError("No workflow is open.")
        return self._workflow

    def is_dirty(self) -> bool:
        """Whether the definition differs from the last opened or saved version."""
        return self._workflow != self._original

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def describe_undo(self) -> str:
        """Return a short label suitable for an undo button."""
        return "Undo last change" if self.can_undo else "Nothing to undo"

    def rename_workflow(self, name: str) -> None:
        if not isinstance(name, str):
            raise WorkflowValidationError("Workflow name must be text.")
        self._apply(replace(self.workflow(), name=name))

    def rename_step(self, step_id: str, name: str) -> None:
        self.update_step(step_id, name=name)

    def update_step(self, step_id: str, **changes: Any) -> None:
        """Update known step fields, validating the complete new workflow."""
        unknown = set(changes) - _STEP_FIELDS - {"step_id"}
        if unknown:
            names = ", ".join(sorted(unknown))
            raise WorkflowValidationError(f"Unknown step fields: {names}.")
        if "step_id" in changes:
            raise WorkflowValidationError("Step IDs cannot be changed in the editor.")
        self._validate_step_changes(changes)
        index = self._step_index(step_id)
        step = replace(self.workflow().steps[index], **changes)
        steps = (
            *self.workflow().steps[:index],
            step,
            *self.workflow().steps[index + 1 :],
        )
        self._apply(replace(self.workflow(), steps=steps))

    def insert_step(self, step: WorkflowStep, index: int) -> None:
        """Insert a validated step at the chain position represented by an edge."""
        if not isinstance(step, WorkflowStep):
            raise WorkflowValidationError("Only workflow steps can be inserted.")
        steps = self.workflow().steps
        if not 0 <= index <= len(steps):
            raise WorkflowValidationError("The insertion position is outside the workflow.")
        if any(existing.step_id == step.step_id for existing in steps):
            raise WorkflowValidationError(f"Step ID is duplicated: {step.step_id}.")
        self._apply(replace(self.workflow(), steps=(*steps[:index], step, *steps[index:])))

    def add_step_after(self, step_id: str | None) -> WorkflowStep:
        """Insert a new REPORT step after a selected step or after Start."""
        index = 0 if step_id is None else self._step_index(step_id) + 1
        step = WorkflowStep(
            step_id=self._fresh_step_id(),
            name="New step",
            kind=StepKind.REPORT,
            message="",
        )
        self.insert_step(step, index)
        return step

    def delete_step(self, step_id: str) -> None:
        index = self._step_index(step_id)
        steps = self.workflow().steps
        self._apply(replace(self.workflow(), steps=steps[:index] + steps[index + 1 :]))
        self._notes.pop(step_id, None)
        self._positions.pop(step_id, None)

    def duplicate_step(self, step_id: str) -> WorkflowStep:
        index = self._step_index(step_id)
        original = self.workflow().steps[index]
        base_id = f"{original.step_id}-copy"
        new_id = base_id
        suffix = 2
        existing_ids = {step.step_id for step in self.workflow().steps}
        while new_id in existing_ids:
            new_id = f"{base_id}-{suffix}"
            suffix += 1
        duplicate = replace(original, step_id=new_id)
        self.insert_step(duplicate, index + 1)
        return duplicate

    def move_step(self, step_id: str, delta: int) -> None:
        if not isinstance(delta, int) or isinstance(delta, bool):
            raise WorkflowValidationError("Step movement must be a whole number.")
        index = self._step_index(step_id)
        target = max(0, min(len(self.workflow().steps) - 1, index + delta))
        if target == index:
            return
        steps = list(self.workflow().steps)
        step = steps.pop(index)
        steps.insert(target, step)
        self._apply(replace(self.workflow(), steps=tuple(steps)))

    def set_note(self, step_id: str, text: str) -> None:
        self._step_index(step_id)
        if not isinstance(text, str) or len(text) > _MAX_NOTE_LENGTH:
            raise WorkflowValidationError("A step note must be at most 500 characters.")
        if text:
            self._notes[step_id] = text
        else:
            self._notes.pop(step_id, None)

    def note(self, step_id: str) -> str | None:
        self._step_index(step_id)
        return self._notes.get(step_id)

    def move_node(self, step_id: str, x: float, y: float) -> None:
        self._step_index(step_id)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in (x, y)):
            raise WorkflowValidationError("Node position must use numbers.")
        if not math.isfinite(float(x)) or not math.isfinite(float(y)):
            raise WorkflowValidationError("Node position must be finite.")
        self._positions[step_id] = (float(x), float(y))

    def node_position(self, step_id: str) -> tuple[float, float] | None:
        self._step_index(step_id)
        return self._positions.get(step_id)

    @property
    def notes(self) -> dict[str, str]:
        return dict(self._notes)

    @property
    def node_positions(self) -> dict[str, tuple[float, float]]:
        return dict(self._positions)

    def undo(self) -> None:
        if not self._undo:
            raise WorkflowValidationError("There is nothing to undo.")
        current = self.workflow()
        self._redo.append(current)
        self._workflow = self._undo.pop()

    def redo(self) -> None:
        if not self._redo:
            raise WorkflowValidationError("There is nothing to redo.")
        current = self.workflow()
        self._undo.append(current)
        self._workflow = self._redo.pop()

    def save(self, service: WorkflowService, path: Path | None = None) -> Path:
        """Save through the controller service and mark the definition clean."""
        saved_path = service.save(self.workflow(), path)
        self._original = self.workflow()
        return saved_path

    @classmethod
    def load(cls, service: WorkflowService, path: Path) -> WorkflowEditorSession:
        """Load a validated workflow through the controller service."""
        return cls(service.load(path))

    def _apply(self, workflow: Workflow) -> None:
        WorkflowRunner.validate(workflow)
        current = self.workflow()
        if workflow == current:
            return
        self._undo.append(current)
        del self._undo[:-_MAX_HISTORY]
        self._redo.clear()
        self._workflow = workflow

    @staticmethod
    def _validate_step_changes(changes: dict[str, Any]) -> None:
        for field in ("name", "message"):
            if field in changes and not isinstance(changes[field], str):
                raise WorkflowValidationError(f"Step {field} must be text.")
        if "kind" in changes and not isinstance(changes["kind"], StepKind):
            raise WorkflowValidationError("Step kind is not recognised.")
        if (
            "target" in changes
            and changes["target"] is not None
            and not isinstance(changes["target"], str)
        ):
            raise WorkflowValidationError("Step target must be text.")
        if "max_attempts" in changes and (
            isinstance(changes["max_attempts"], bool)
            or not isinstance(changes["max_attempts"], int)
        ):
            raise WorkflowValidationError("Step max_attempts must be an integer.")
        if (
            "postcondition" in changes
            and changes["postcondition"] is not None
            and not isinstance(changes["postcondition"], PostconditionKind)
        ):
            raise WorkflowValidationError("Step postcondition is not recognised.")
        if "timeout_seconds" in changes and (
            isinstance(changes["timeout_seconds"], bool)
            or not isinstance(changes["timeout_seconds"], (int, float))
        ):
            raise WorkflowValidationError("Step timeout_seconds must be a number.")

    def _step_index(self, step_id: str) -> int:
        for index, step in enumerate(self.workflow().steps):
            if step.step_id == step_id:
                return index
        raise WorkflowValidationError(f"Step was not found: {step_id}.")

    def _fresh_step_id(self) -> str:
        existing = {step.step_id for step in self.workflow().steps}
        index = 1
        while f"step-{index}" in existing:
            index += 1
        return f"step-{index}"

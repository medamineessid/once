"""One asked-at-run-time value for an automation that needs it.

An author writes ``{name}`` where the value belongs. The step keeps that
placeholder until the moment it is about to run, so nothing is guessed and the
value is always typed by the person starting the run. Substitution happens
before the approval gate, which means the approved workflow is exactly what runs.
"""

from __future__ import annotations

import re
from dataclasses import replace

from engine.workflow import Workflow

#: ``{name}``: lowercase, short, and never nested.
PARAMETER_PATTERN = re.compile(r"\{([a-z][a-z0-9_]{0,30})\}")


def parameter_names(workflow: Workflow) -> tuple[str, ...]:
    """Every distinct placeholder in the workflow, in first-seen order."""
    seen: list[str] = []
    for text in (workflow.name,):
        for match in PARAMETER_PATTERN.finditer(text):
            if match.group(1) not in seen:
                seen.append(match.group(1))
    for step in workflow.steps:
        for text in (step.name, step.message, step.target or ""):
            for match in PARAMETER_PATTERN.finditer(text):
                name = match.group(1)
                if name not in seen:
                    seen.append(name)
    return tuple(seen)


def apply_parameter_values(workflow: Workflow, values: dict[str, str]) -> Workflow:
    """Return the same workflow with every placeholder replaced by its value."""

    def fill(text: str) -> str:
        return PARAMETER_PATTERN.sub(lambda match: values[match.group(1)], text)

    steps = tuple(
        replace(
            step,
            name=fill(step.name),
            message=fill(step.message),
            target=fill(step.target) if step.target else step.target,
        )
        for step in workflow.steps
    )
    # The title may name the value too ("Save a note called today"); the
    # workflow id is identity and is never rewritten.
    return replace(workflow, name=fill(workflow.name), steps=steps)


def missing_values(workflow: Workflow, values: dict[str, str]) -> tuple[str, ...]:
    """Placeholders that would still be empty or unsubstituted after filling."""
    return tuple(
        name
        for name in parameter_names(workflow)
        if not str(values.get(name, "")).strip() or "{" in str(values.get(name, ""))
    )

"""Strict, JSON-backed acceptance cases for headless verification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from .errors import WorkflowValidationError

MAX_CASES: Final = 100
MAX_FIELDS: Final = 100
MAX_TEXT_LENGTH: Final = 500


class ComparisonMode(StrEnum):
    """Supported deterministic field comparison modes."""

    EXACT = "exact"
    NUMERIC_TOLERANCE = "numeric_tolerance"
    CASE_INSENSITIVE = "case_insensitive"


@dataclass(frozen=True)
class ExpectedField:
    """One expected output field and its comparison policy."""

    value: object
    mode: ComparisonMode
    required: bool
    tolerance: float | None = None


@dataclass(frozen=True)
class AcceptanceCase:
    """One controlled input and its expected structured output."""

    case_id: str
    input_file: Path
    expected: dict[str, ExpectedField]

    @classmethod
    def from_dict(cls, data: object) -> AcceptanceCase:
        if not isinstance(data, dict) or set(data) != {"case_id", "input_file", "expected"}:
            raise WorkflowValidationError("Acceptance case has unknown or missing fields.")
        case_id = _text(data["case_id"], "Case ID")
        input_file = Path(_text(data["input_file"], "Input file"))
        if not input_file.is_absolute():
            raise WorkflowValidationError("Input file must be an absolute path.")
        raw_expected = data["expected"]
        if not isinstance(raw_expected, dict) or not raw_expected:
            raise WorkflowValidationError(
                "Acceptance case expected fields must be a non-empty object."
            )
        if len(raw_expected) > MAX_FIELDS:
            raise WorkflowValidationError("Acceptance case has too many expected fields.")
        expected: dict[str, ExpectedField] = {}
        for field_name, raw_field in raw_expected.items():
            if not isinstance(field_name, str) or not field_name.strip():
                raise WorkflowValidationError("Expected field names must be non-empty text.")
            if not isinstance(raw_field, dict) or set(raw_field) not in (
                {"value", "mode", "required"},
                {"value", "mode", "required", "tolerance"},
            ):
                raise WorkflowValidationError(f"Field {field_name} has unknown or missing fields.")
            try:
                mode = ComparisonMode(raw_field["mode"])
            except (KeyError, ValueError) as error:
                raise WorkflowValidationError(
                    f"Field {field_name} has an unknown comparison mode."
                ) from error
            required = raw_field["required"]
            if not isinstance(required, bool):
                raise WorkflowValidationError(f"Field {field_name} required must be boolean.")
            tolerance = raw_field.get("tolerance")
            if mode is ComparisonMode.NUMERIC_TOLERANCE:
                if (
                    not isinstance(tolerance, (int, float))
                    or isinstance(tolerance, bool)
                    or tolerance < 0
                ):
                    raise WorkflowValidationError(
                        f"Field {field_name} needs a non-negative numeric tolerance."
                    )
                if not isinstance(raw_field["value"], (int, float)) or isinstance(
                    raw_field["value"], bool
                ):
                    raise WorkflowValidationError(
                        f"Field {field_name} needs a numeric expected value."
                    )
            elif tolerance is not None:
                raise WorkflowValidationError(f"Field {field_name} cannot define a tolerance.")
            expected[field_name] = ExpectedField(
                raw_field["value"],
                mode,
                required,
                float(tolerance) if tolerance is not None else None,
            )
        return cls(case_id, input_file, expected)


def load_acceptance_cases(path: Path) -> tuple[AcceptanceCase, ...]:
    """Load a strictly validated JSON list of acceptance cases."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise WorkflowValidationError(f"Could not read acceptance cases: {path}.") from error
    if not isinstance(data, list) or not data or len(data) > MAX_CASES:
        raise WorkflowValidationError("Acceptance cases must be a non-empty bounded list.")
    cases = tuple(AcceptanceCase.from_dict(item) for item in data)
    ids = [case.case_id for case in cases]
    if len(set(ids)) != len(ids):
        raise WorkflowValidationError("Acceptance case IDs must be unique.")
    return cases


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT_LENGTH:
        raise WorkflowValidationError(f"{field} must be non-empty bounded text.")
    return value

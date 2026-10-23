"""Bounded, allowlisted headless command verification."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .acceptance import AcceptanceCase, ComparisonMode
from .errors import ExecutionError

MAX_OUTPUT_TAIL = 2_000
MAX_TIMEOUT_SECONDS = 300.0
INPUT_PLACEHOLDER = "{input}"
CHECKOUT_PLACEHOLDER = "{checkout}"


@dataclass(frozen=True)
class AllowlistedCommand:
    """An exact argv template; no shell or unbounded arguments are allowed."""

    argv: tuple[str, ...]
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if any(not isinstance(argument, str) or not argument for argument in self.argv):
            raise ExecutionError("Allowlisted command arguments must be non-empty text.")
        if sum(argument.count(INPUT_PLACEHOLDER) for argument in self.argv) != 1:
            raise ExecutionError("Allowlisted command must contain exactly one {input} argument.")
        checkout_count = sum(argument.count(CHECKOUT_PLACEHOLDER) for argument in self.argv)
        if checkout_count > 1:
            raise ExecutionError(
                "Allowlisted command may reference at most one {checkout} directory."
            )
        if not 0 < self.timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise ExecutionError("Command timeout must be between 0 and 300 seconds.")

    def for_input(self, input_file: Path, checkout: Path | None = None) -> tuple[str, ...]:
        arguments = list(self.argv)
        references_checkout = any(CHECKOUT_PLACEHOLDER in argument for argument in arguments)
        if references_checkout and checkout is None:
            raise ExecutionError("This allowlisted command requires a checkout directory to run.")
        if checkout is not None:
            arguments = [
                argument.replace(CHECKOUT_PLACEHOLDER, str(checkout)) for argument in arguments
            ]
        return tuple(argument.replace(INPUT_PLACEHOLDER, str(input_file)) for argument in arguments)


@dataclass(frozen=True)
class FieldResult:
    """One expected field comparison result."""

    field: str
    passed: bool
    status: str
    expected: object
    actual: object


@dataclass(frozen=True)
class CaseResult:
    """One command invocation and its field results."""

    case_id: str
    passed: bool
    fields: tuple[FieldResult, ...]
    exit_code: int | None
    timed_out: bool
    stdout_tail: str
    stderr_tail: str


@dataclass(frozen=True)
class EvidenceBundle:
    """Bounded JSON/Markdown-ready evidence for a verification run."""

    run_id: str
    started_at: str
    finished_at: str
    cases: tuple[CaseResult, ...]
    redaction_applied: bool = True
    cancelled: bool = False

    @property
    def passed(self) -> bool:
        return all(case.passed for case in self.cases)

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "passed": self.passed,
            "redaction_applied": self.redaction_applied,
            "cancelled": self.cancelled,
            "cases": [
                {
                    "case_id": case.case_id,
                    "passed": case.passed,
                    "exit_code": case.exit_code,
                    "timed_out": case.timed_out,
                    "stdout_tail": case.stdout_tail,
                    "stderr_tail": case.stderr_tail,
                    "fields": [
                        {
                            "field": field.field,
                            "passed": field.passed,
                            "status": field.status,
                            "expected": _redact_value(field.expected),
                            "actual": _redact_value(field.actual),
                        }
                        for field in case.fields
                    ],
                }
                for case in self.cases
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n"

    def to_markdown(self) -> str:
        lines = [
            f"# Verification run `{self.run_id}`",
            "",
            f"- Passed: **{self.passed}**",
            *(["- Cancelled: **True**"] if self.cancelled else []),
            f"- Started: `{self.started_at}`",
            f"- Finished: `{self.finished_at}`",
            "- Redaction applied: **True**",
            "",
        ]
        for case in self.cases:
            lines.extend(
                [
                    f"## Case `{case.case_id}`",
                    "",
                    f"- Passed: **{case.passed}**",
                    f"- Exit code: `{case.exit_code}`",
                    f"- Timed out: **{case.timed_out}**",
                    "",
                    "| Field | Status | Expected | Actual |",
                    "|---|---|---|---|",
                ]
            )
            lines.extend(
                f"| `{field.field}` | {field.status} | `{_markdown_value(field.expected)}` | "
                f"`{_markdown_value(field.actual)}` |"
                for field in case.fields
            )
            lines.extend(
                [
                    "",
                    "### Output tails",
                    "",
                    "```text",
                    case.stdout_tail,
                    case.stderr_tail,
                    "```",
                    "",
                ]
            )
        return "\n".join(lines)

    def write(self, directory: Path) -> tuple[Path, Path]:
        """Persist bounded JSON and Markdown evidence below an explicit directory."""
        directory.mkdir(parents=True, exist_ok=True)
        json_path = directory / f"{self.run_id}.json"
        markdown_path = directory / f"{self.run_id}.md"
        json_path.write_text(self.to_json(), encoding="utf-8")
        markdown_path.write_text(self.to_markdown(), encoding="utf-8")
        return json_path, markdown_path


class AcceptanceVerifier:
    """Run one exact configured command against bounded acceptance cases."""

    def __init__(self, command: AllowlistedCommand) -> None:
        self._command = command

    def verify(
        self,
        cases: tuple[AcceptanceCase, ...],
        cancel_check: Callable[[], bool] | None = None,
        checkout: Path | None = None,
    ) -> EvidenceBundle:
        """Run every case in order; cancellation skips the remaining cases."""
        started = datetime.now(UTC)
        results: list[CaseResult] = []
        cancelled = False
        for case in cases:
            if cancel_check is not None and cancel_check():
                cancelled = True
                results.append(
                    CaseResult(
                        case.case_id,
                        False,
                        (),
                        None,
                        False,
                        "",
                        "Cancelled before this case ran.",
                    )
                )
                continue
            results.append(self._run_case(case, checkout))
        return EvidenceBundle(
            str(uuid4()),
            started.isoformat(),
            datetime.now(UTC).isoformat(),
            tuple(results),
            cancelled=cancelled,
        )

    def _run_case(self, case: AcceptanceCase, checkout: Path | None = None) -> CaseResult:
        if not case.input_file.is_file():
            return CaseResult(
                case.case_id,
                False,
                tuple(
                    FieldResult(name, False, "input_missing", expected.value, None)
                    for name, expected in case.expected.items()
                ),
                None,
                False,
                "",
                "Input file was not found.",
            )
        try:
            completed = subprocess.run(  # noqa: S603 - exact configured argv, shell disabled
                self._command.for_input(case.input_file, checkout),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self._command.timeout_seconds,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as error:
            return CaseResult(
                case.case_id,
                False,
                tuple(
                    FieldResult(name, False, "timeout", expected.value, None)
                    for name, expected in case.expected.items()
                ),
                None,
                True,
                _tail(error.stdout),
                _tail(error.stderr),
            )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        if completed.returncode != 0:
            return CaseResult(
                case.case_id,
                False,
                tuple(
                    FieldResult(name, False, "command_failed", expected.value, None)
                    for name, expected in case.expected.items()
                ),
                completed.returncode,
                False,
                _tail(stdout),
                _tail(stderr),
            )
        try:
            actual = json.loads(stdout)
        except json.JSONDecodeError:
            return CaseResult(
                case.case_id,
                False,
                tuple(
                    FieldResult(name, False, "malformed_json", expected.value, None)
                    for name, expected in case.expected.items()
                ),
                completed.returncode,
                False,
                _tail(stdout),
                _tail(stderr),
            )
        if not isinstance(actual, dict):
            actual = {}
        fields = tuple(
            _compare_field(name, expected, actual) for name, expected in case.expected.items()
        )
        return CaseResult(
            case.case_id,
            all(field.passed for field in fields),
            fields,
            completed.returncode,
            False,
            _tail(stdout),
            _tail(stderr),
        )


def _compare_field(name: str, expected: object, actual: dict[str, object]) -> FieldResult:
    policy = expected
    if name not in actual:
        return FieldResult(
            name,
            not policy.required,
            "missing_optional" if not policy.required else "missing_required",
            policy.value,
            None,
        )
    value = actual[name]
    if policy.mode is ComparisonMode.EXACT:
        passed = value == policy.value
    elif policy.mode is ComparisonMode.CASE_INSENSITIVE:
        passed = (
            isinstance(value, str)
            and isinstance(policy.value, str)
            and value.casefold() == policy.value.casefold()
        )
    else:
        passed = (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and abs(value - policy.value) <= (policy.tolerance or 0.0)
        )
    return FieldResult(name, passed, "matched" if passed else "mismatch", policy.value, value)


def _tail(value: str | bytes | None) -> str:
    if value is None:
        return ""
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    return _redact(text[-MAX_OUTPUT_TAIL:])


_SECRET = re.compile(r"(?i)(api[_-]?key|secret|token|password|authorization)\s*[:=]\s*([^\s,;]+)")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")


def _redact(value: str) -> str:
    return _EMAIL.sub("[REDACTED_EMAIL]", _SECRET.sub(r"\1=[REDACTED_SECRET]", value))


def _redact_value(value: object) -> object:
    if isinstance(value, str):
        return _redact(value)
    if isinstance(value, dict):
        return {str(key): _redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _markdown_value(value: object) -> str:
    return str(_redact_value(value)).replace("`", "'").replace("\n", " ")

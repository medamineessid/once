"""Headless acceptance-case verifier tests with disposable fake extractors."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from engine.acceptance import AcceptanceCase, ExpectedField, load_acceptance_cases
from engine.errors import ExecutionError, WorkflowValidationError
from engine.verifier import AcceptanceVerifier, AllowlistedCommand

EXTRACTOR = """
import json
import pathlib
import sys
import time

mode = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
if mode == "crash":
    raise SystemExit(7)
if mode == "timeout":
    time.sleep(2)
if mode == "malformed":
    print("{not-json")
elif mode == "secret":
    print(json.dumps({"status": "ok", "note": "api_key=SECRET alice@example.com"}))
else:
    print(json.dumps({"invoice_number": "INV-1", "total": 100.05, "status": "Paid"}))
"""


def command(tmp_path: Path, timeout: float = 1.0) -> AllowlistedCommand:
    script = tmp_path / "extractor.py"
    script.write_text(EXTRACTOR, encoding="utf-8")
    return AllowlistedCommand((sys.executable, str(script), "{input}"), timeout)


def case(tmp_path: Path, mode: str = "pass") -> AcceptanceCase:
    input_file = tmp_path / f"{mode}.txt"
    input_file.write_text(mode, encoding="utf-8")
    return AcceptanceCase.from_dict(
        {
            "case_id": mode,
            "input_file": str(input_file),
            "expected": {
                "invoice_number": {"value": "INV-1", "mode": "exact", "required": True},
                "total": {
                    "value": 100.0,
                    "mode": "numeric_tolerance",
                    "tolerance": 0.1,
                    "required": True,
                },
                "status": {"value": "paid", "mode": "case_insensitive", "required": True},
            },
        }
    )


def test_verifier_passes_exact_tolerance_and_case_insensitive_fields(tmp_path) -> None:
    bundle = AcceptanceVerifier(command(tmp_path)).verify((case(tmp_path),))

    assert bundle.passed is True
    assert all(field.passed for field in bundle.cases[0].fields)
    assert bundle.cases[0].exit_code == 0
    assert bundle.to_dict()["redaction_applied"] is True
    json_path, markdown_path = bundle.write(tmp_path / "evidence")
    assert json_path.exists()
    assert markdown_path.exists()


def test_verifier_reports_mismatch_and_missing_required_field(tmp_path) -> None:
    current = case(tmp_path)
    mismatch = AcceptanceCase(
        current.case_id,
        current.input_file,
        {
            **current.expected,
            "status": ExpectedField("wrong", current.expected["status"].mode, True),
        },
    )
    missing = AcceptanceCase(
        "missing",
        current.input_file,
        {"missing": ExpectedField("x", current.expected["status"].mode, True)},
    )

    results = AcceptanceVerifier(command(tmp_path)).verify((mismatch, missing)).cases

    assert results[0].passed is False
    assert results[0].fields[-1].status == "mismatch"
    assert results[1].fields[0].status == "missing_required"


@pytest.mark.parametrize(
    ("mode", "status"),
    [("crash", "command_failed"), ("malformed", "malformed_json"), ("timeout", "timeout")],
)
def test_verifier_reports_process_failures(tmp_path, mode: str, status: str) -> None:
    timeout = 0.1 if mode == "timeout" else 2.0
    result = (
        AcceptanceVerifier(command(tmp_path, timeout=timeout))
        .verify((case(tmp_path, mode),))
        .cases[0]
    )

    assert result.passed is False
    assert result.fields[0].status == status


def test_verifier_redacts_secret_and_email_in_evidence(tmp_path) -> None:
    input_file = tmp_path / "secret.txt"
    input_file.write_text("secret", encoding="utf-8")
    expected = AcceptanceCase.from_dict(
        {
            "case_id": "secret",
            "input_file": str(input_file),
            "expected": {
                "status": {"value": "ok", "mode": "exact", "required": True},
                "note": {
                    "value": "api_key=SECRET alice@example.com",
                    "mode": "exact",
                    "required": True,
                },
            },
        }
    )

    bundle = AcceptanceVerifier(command(tmp_path)).verify((expected,))
    encoded = bundle.to_json() + bundle.to_markdown()

    assert bundle.passed is True
    assert "api_key=SECRET" not in encoded
    assert "alice@example.com" not in encoded
    assert "[REDACTED_SECRET]" in encoded
    assert "[REDACTED_EMAIL]" in encoded


def test_acceptance_case_validation_rejects_unknown_and_unsafe_shapes(tmp_path) -> None:
    base = {
        "case_id": "case",
        "input_file": str(tmp_path / "input.txt"),
        "expected": {"field": {"value": "x", "mode": "exact", "required": True}},
    }
    for invalid in (
        {**base, "extra": True},
        {**base, "input_file": "relative.txt"},
        {
            **base,
            "expected": {"field": {"value": "x", "mode": "unknown", "required": True}},
        },
        {
            **base,
            "expected": {
                "field": {"value": "x", "mode": "exact", "required": True, "tolerance": 1}
            },
        },
    ):
        with pytest.raises(WorkflowValidationError):
            AcceptanceCase.from_dict(invalid)


def test_acceptance_case_file_rejects_duplicate_ids_and_invalid_json(tmp_path) -> None:
    path = tmp_path / "cases.json"
    payload = json.dumps(
        [
            {
                "case_id": "same",
                "input_file": str(tmp_path / "one"),
                "expected": {"field": {"value": "x", "mode": "exact", "required": True}},
            },
            {
                "case_id": "same",
                "input_file": str(tmp_path / "two"),
                "expected": {"field": {"value": "x", "mode": "exact", "required": True}},
            },
        ]
    )
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(WorkflowValidationError, match="unique"):
        load_acceptance_cases(path)


def test_allowlisted_command_requires_one_input_and_bounded_timeout() -> None:
    with pytest.raises(ExecutionError):
        AllowlistedCommand((sys.executable, "-c", "print(1)"))
    with pytest.raises(ExecutionError):
        AllowlistedCommand((sys.executable, "{input}"), 301)

"""Tests for the user-configured acceptance checker used by the real session."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from controller.verifier_config import config_path, load_verifier_config
from engine.errors import WorkflowValidationError


def write_config(tmp_path: Path, document: object) -> Path:
    path = config_path(tmp_path)
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def defaults(tmp_path: Path) -> dict:
    cases = tmp_path / "cases.json"
    cases.write_text("[]", encoding="utf-8")
    return {
        "cases_path": str(cases),
        "argv": ["/opt/extractor", "{input}"],
        "timeout_seconds": 30.0,
        "worktree_root": str(tmp_path / "worktrees"),
    }


def test_missing_file_means_no_configuration(tmp_path: Path) -> None:
    assert load_verifier_config(tmp_path) is None
    assert config_path(tmp_path) == tmp_path / "verifier.json"


def test_valid_config_is_loaded_and_resolved(tmp_path: Path) -> None:
    write_config(tmp_path, defaults(tmp_path))
    config = load_verifier_config(tmp_path)
    assert config is not None
    assert config.argv == ("/opt/extractor", "{input}")
    assert config.timeout_seconds == 30.0
    assert config.cases_path.is_file()
    assert config.worktree_root.name == "worktrees"


def test_checkout_placeholder_is_allowed(tmp_path: Path) -> None:
    setup = defaults(tmp_path)
    setup["argv"] = ["python", "{checkout}/extractor.py", "{input}"]
    write_config(tmp_path, setup)
    config = load_verifier_config(tmp_path)
    assert "{checkout}/extractor.py" in config.argv


def test_broken_json_is_a_visible_error(tmp_path: Path) -> None:
    config_path(tmp_path).write_text("{ not json", encoding="utf-8")
    with pytest.raises(WorkflowValidationError, match="not valid JSON"):
        load_verifier_config(tmp_path)


def test_document_must_be_an_object_without_unknown_keys(tmp_path: Path) -> None:
    config_path(tmp_path).write_text(json.dumps(["not", "an object"]), encoding="utf-8")
    with pytest.raises(WorkflowValidationError, match="must be an object"):
        load_verifier_config(tmp_path)
    setup = defaults(tmp_path)
    setup["unknown_setting"] = "value"
    write_config(tmp_path, setup)
    with pytest.raises(WorkflowValidationError, match="unknown settings"):
        load_verifier_config(tmp_path)


def test_missing_input_placeholder_is_rejected(tmp_path: Path) -> None:
    setup = defaults(tmp_path)
    setup["argv"] = ["python", "no-placeholder"]
    write_config(tmp_path, setup)
    with pytest.raises(WorkflowValidationError, match="not a valid allowlisted"):
        load_verifier_config(tmp_path)


def test_double_checkout_placeholder_is_rejected(tmp_path: Path) -> None:
    setup = defaults(tmp_path)
    setup["argv"] = ["python", "{checkout}/a", "{checkout}/b", "{input}"]
    write_config(tmp_path, setup)
    with pytest.raises(WorkflowValidationError, match="not a valid allowlisted"):
        load_verifier_config(tmp_path)


def test_out_of_range_timeout_is_rejected(tmp_path: Path) -> None:
    setup = defaults(tmp_path)
    setup["timeout_seconds"] = 900.0
    write_config(tmp_path, setup)
    with pytest.raises(WorkflowValidationError, match="not a valid allowlisted"):
        load_verifier_config(tmp_path)


@pytest.mark.parametrize(
    "key, value",
    [
        ("cases_path", 42),
        ("argv", "not-a-list"),
        ("timeout_seconds", "50"),
        ("worktree_root", None),
    ],
)
def test_wrongly_typed_values_are_rejected(tmp_path: Path, key: str, value: object) -> None:
    setup = defaults(tmp_path)
    setup[key] = value
    write_config(tmp_path, setup)
    with pytest.raises(WorkflowValidationError):
        load_verifier_config(tmp_path)


def test_missing_cases_file_is_rejected_visibly(tmp_path: Path) -> None:
    setup = defaults(tmp_path)
    setup["cases_path"] = str(tmp_path / "missing.json")
    write_config(tmp_path, setup)
    with pytest.raises(WorkflowValidationError, match="could not be found"):
        load_verifier_config(tmp_path)

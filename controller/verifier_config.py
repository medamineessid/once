"""User-configured acceptance checker for the proposal review workflow.

The checker is an exactly configured argv template validated by the same
allowlist as every other verifier command: no shell, exactly one {input}
placeholder, at most one {checkout} placeholder, and a bounded timeout. The
configuration lives in the app data directory only; nothing is stored in the
repository and no secrets belong in this file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

from engine.errors import ExecutionError, WorkflowValidationError
from engine.verifier import AllowlistedCommand

CONFIG_FILENAME = "verifier.json"


class VerifierConfig(NamedTuple):
    """The configured acceptance checks and the worktree directory for reruns."""

    cases_path: Path
    argv: tuple[str, ...]
    timeout_seconds: float
    worktree_root: Path


def config_path(app_data_dir: Path) -> Path:
    """Return the checker configuration file location."""
    return Path(app_data_dir) / CONFIG_FILENAME


def load_verifier_config(app_data_dir: Path) -> VerifierConfig | None:
    """Load and validate the user's checker configuration, or None when absent.

    A missing file means the session has no acceptance checks configured; an
    existing but invalid file is a visible configuration error, never a
    silently ignored fallback.
    """
    path = config_path(app_data_dir)
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WorkflowValidationError(
            "The acceptance checker configuration is not valid JSON. Fix the "
            "file shown in the log, then restart Once."
        ) from error
    return document_to_config(document)


def document_to_config(document: object) -> VerifierConfig:
    """Validate one checker configuration document and return its typed form."""
    if not isinstance(document, dict):
        raise WorkflowValidationError(
            "The acceptance checker configuration must be an object with "
            "cases_path, argv, timeout_seconds, and worktree_root keys."
        )
    unknown = set(document) - {"cases_path", "argv", "timeout_seconds", "worktree_root"}
    if unknown:
        raise WorkflowValidationError(
            "The acceptance checker configuration contains unknown settings: "
            + ", ".join(sorted(str(name) for name in unknown))
            + "."
        )
    cases_value = document.get("cases_path")
    argv_value = document.get("argv")
    timeout_value = document.get("timeout_seconds")
    worktree_value = document.get("worktree_root")
    if not isinstance(cases_value, str) or not cases_value:
        raise WorkflowValidationError(
            "The acceptance checker configuration must set cases_path to the "
            "path of the synthetic acceptance cases file."
        )
    if (
        not isinstance(argv_value, list)
        or not argv_value
        or not all(isinstance(argument, str) and argument for argument in argv_value)
    ):
        raise WorkflowValidationError(
            "The acceptance checker configuration must set argv to a list of "
            "non-empty strings including exactly one {input} placeholder."
        )
    if not isinstance(timeout_value, (int, float)) or isinstance(timeout_value, bool):
        raise WorkflowValidationError(
            "The acceptance checker configuration must set timeout_seconds to "
            "a number between 0 and 300."
        )
    if not isinstance(worktree_value, str) or not worktree_value:
        raise WorkflowValidationError(
            "The acceptance checker configuration must set worktree_root to an "
            "empty directory outside the target repository."
        )
    try:
        AllowlistedCommand(tuple(argv_value), float(timeout_value))
    except ExecutionError as error:
        raise WorkflowValidationError(
            f"The acceptance checker configuration is not a valid allowlisted command: {error}"
        ) from error
    cases_path = Path(cases_value).expanduser().resolve()
    if not cases_path.is_file():
        raise WorkflowValidationError(
            "The acceptance cases file from the checker configuration could "
            "not be found. Fix the path in the configuration, then restart Once."
        )
    worktree_root = Path(worktree_value).expanduser().resolve()
    return VerifierConfig(cases_path, tuple(argv_value), float(timeout_value), worktree_root)


def save_verifier_config(
    app_data_dir: Path,
    cases_path: str,
    argv: list[str],
    timeout_seconds: float,
    worktree_root: str,
) -> VerifierConfig:
    """Validate and write the checker configuration atomically.

    The file is written only when the document passes exactly the same
    validation a restart would apply; a failed save never touches the
    existing file.
    """
    document = {
        "cases_path": cases_path,
        "argv": list(argv),
        "timeout_seconds": timeout_seconds,
        "worktree_root": worktree_root,
    }
    validated = document_to_config(document)
    path = config_path(app_data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return validated

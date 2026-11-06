"""One-time application launch approvals, checked against an identity database.

A recorded task may open an application; the launch decision must come from
the recording (exe path plus hash), never from a hardcoded name table. This
module is the single boundary between the review experience and approval
storage: the UI and controller ask only the Protocol.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from engine.workflow import StepKind
from recorder.models import RecordedEvent

CREATE_APPROVALS_TABLE = """
CREATE TABLE IF NOT EXISTS app_approvals (
    executable_path TEXT NOT NULL,
    executable_sha256 TEXT NOT NULL,
    name TEXT NOT NULL,
    signer TEXT,
    approved_at TEXT NOT NULL,
    PRIMARY KEY (executable_sha256, executable_path)
)
"""


@dataclass(frozen=True)
class ApplicationIdentity:
    """The launch identity of one recorded application."""

    name: str | None = None
    executable_path: str | None = None
    executable_sha256: str | None = None
    signer: str | None = None

    @property
    def display_name(self) -> str:
        """A plain-language name for review prompts and banners."""
        if self.name:
            stem = Path(self.name).stem if self.name.lower().endswith(".exe") else self.name
            return stem
        if self.executable_path:
            return Path(self.executable_path).stem
        return "the recorded application"

    def describes_something(self) -> bool:
        """Whether the identity has at least one meaningful key."""
        return bool(self.executable_path or self.executable_sha256)


class ApplicationApprovalStore(Protocol):
    """Where one-time application approvals live. UI never stores them."""

    def is_approved(self, identity: ApplicationIdentity) -> bool:
        """Whether this exact identity was already approved at least once."""
        ...

    def approve(self, identity: ApplicationIdentity) -> None:
        """Record one explicit human approval for this exact identity."""
        ...


class DatabaseApplicationApprovalStore:
    """SQLite-backed approvals; the key is the recorded exe hash and path."""

    def __init__(self, database_path: Path) -> None:
        self._connection = sqlite3.connect(database_path)
        self._connection.execute(CREATE_APPROVALS_TABLE)
        self._connection.commit()

    def is_approved(self, identity: ApplicationIdentity) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM app_approvals WHERE executable_sha256 = ? AND executable_path = ?",
            (identity.executable_sha256 or "", identity.executable_path or ""),
        ).fetchone()
        return row is not None

    def approve(self, identity: ApplicationIdentity) -> None:
        approved_at = datetime.now(UTC).isoformat(timespec="seconds")
        self._connection.execute(
            "INSERT OR REPLACE INTO app_approvals "
            "(executable_path, executable_sha256, name, signer, approved_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                identity.executable_path or "",
                identity.executable_sha256 or "",
                identity.name or "",
                identity.signer,
                approved_at,
            ),
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()


def launch_identities_from_events(
    events: Iterable[RecordedEvent],
) -> tuple[ApplicationIdentity, ...]:
    """Distinct launch identities observed in a recording's window events.

    Deterministic and de-duplicated on (hash, path): a task that opens the
    same application several times gets one identity.
    """
    identities: dict[tuple[str | None, str | None], ApplicationIdentity] = {}
    for event in events:
        if not event.executable_path and not event.executable_sha256:
            continue
        identity = ApplicationIdentity(
            name=event.process_name,
            executable_path=event.executable_path,
            executable_sha256=event.executable_sha256,
        )
        key = (identity.executable_sha256, identity.executable_path)
        identities.setdefault(key, identity)
    return tuple(
        identity
        for _, identity in sorted(
            identities.items(),
            key=lambda item: (item[0][0] or "", item[0][1] or ""),
        )
    )


def executable_launch_paths(workflow) -> tuple[str, ...]:
    """Absolute exe paths a saved workflow's launch steps open by identity.

    Name-based launches ride the engine's built-in allow-list and are not
    part of the recorded-identity approval set.
    """
    paths = set()
    for step in workflow.steps:
        if step.kind is not StepKind.LAUNCH_APPLICATION or not step.target:
            continue
        try:
            payload = json.loads(step.target)
        except json.JSONDecodeError:
            continue
        executable = payload.get("executable")
        if isinstance(executable, str) and executable.strip():
            paths.add(executable)
    return tuple(sorted(paths, key=str.casefold))

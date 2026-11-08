"""One-time application launch approvals, checked against an identity database.

A recorded task may open an application; the launch decision must come from
the recording (exe path plus hash), never from a hardcoded name table. This
module is the single boundary between the review experience and approval
storage: the UI and controller ask only the Protocol.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from engine.workflow import ApprovedApplication, StepKind
from recorder.models import RecordedEvent
from storage.app_registry import application_key, executable_sha256
from storage.database import connect

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
        self._connection = connect(database_path)
        self._connection.execute(CREATE_APPROVALS_TABLE)
        self._connection.commit()

    def is_approved(self, identity: ApplicationIdentity) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM app_approvals WHERE executable_sha256 = ? AND executable_path = ?",
            (identity.executable_sha256 or "", identity.executable_path or ""),
        ).fetchone()
        if row is not None:
            return True
        if identity.executable_path:
            reg = self.find(Path(identity.executable_path))
            if (
                reg is not None
                and reg.approved
                and (not identity.executable_sha256 or reg.sha256 == identity.executable_sha256)
            ):
                return True
        return False

    def approve(self, identity: ApplicationIdentity) -> None:
        approved_at = datetime.now(UTC).isoformat(timespec="seconds")
        sha256 = identity.executable_sha256 or ""
        if not sha256 and identity.executable_path:
            exe = Path(identity.executable_path)
            if exe.is_file():
                sha256 = executable_sha256(exe)
        self._connection.execute(
            "INSERT OR REPLACE INTO app_approvals "
            "(executable_path, executable_sha256, name, signer, approved_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                identity.executable_path or "",
                sha256,
                identity.name or "",
                identity.signer,
                approved_at,
            ),
        )
        if identity.executable_path:
            exe = Path(identity.executable_path)
            display = identity.display_name
            self._connection.execute(
                """
                INSERT INTO approved_applications (
                    application_key, executable, sha256, display_name,
                    approved, close_supported, created_at, approved_at
                ) VALUES (?, ?, ?, ?, 1, 1, ?, ?)
                ON CONFLICT(application_key) DO UPDATE SET
                    executable = excluded.executable,
                    sha256 = excluded.sha256,
                    display_name = excluded.display_name,
                    approved = 1,
                    approved_at = excluded.approved_at
                """,
                (
                    application_key(exe),
                    str(exe),
                    sha256,
                    display,
                    approved_at,
                    approved_at,
                ),
            )
        self._connection.commit()

    def find(self, executable: Path) -> ApprovedApplication | None:
        """Implement ApplicationApprovals.find for the desktop adapter."""
        key = application_key(executable)
        row = self._connection.execute(
            "SELECT * FROM approved_applications WHERE application_key = ?",
            (key,),
        ).fetchone()
        if row is not None:
            return ApprovedApplication(
                executable=Path(row["executable"]),
                sha256=row["sha256"],
                display_name=row["display_name"],
                approved=bool(row["approved"]),
                close_supported=bool(row["close_supported"]),
            )
        # Fallback: check app_approvals by case-insensitive path
        for app_row in self._connection.execute("SELECT * FROM app_approvals").fetchall():
            stored_path = app_row["executable_path"]
            if stored_path and application_key(Path(stored_path)) == key:
                return ApprovedApplication(
                    executable=Path(stored_path),
                    sha256=app_row["executable_sha256"],
                    display_name=app_row["name"] or Path(stored_path).stem,
                    approved=True,
                    close_supported=True,
                )
        return None

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

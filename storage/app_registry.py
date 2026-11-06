"""The approved-application registry: which executables may be launched, and how.

One row per executable path records the content hash seen when the user approved
it, the display name shown in review, whether approval is still in force, and
whether Once may close it. Nothing here is seeded from code: an application
exists in this registry only because a user approved it.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from engine.workflow import ApprovedApplication


def executable_sha256(path: Path) -> str:
    """Hash of the executable's contents, the identity Once approves."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def application_key(executable: Path) -> str:
    """Case-insensitive key for one executable path, as Windows sees it."""
    return os.path.normcase(str(Path(executable).absolute()))


class SqliteApplicationRegistry:
    """Approved applications, stored in Once's local database.

    Implements ``engine.workflow.ApplicationApprovals`` (``find``), which is all
    the desktop adapter needs, and adds the review/approval operations the UI
    calls.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._connection = connection
        self._clock = clock or (lambda: datetime.now(UTC))

    # ---------------------------------------------------------------- read

    def find(self, executable: Path) -> ApprovedApplication | None:
        """The stored record for this executable path, if the user ever recorded one."""
        row = self._connection.execute(
            "SELECT * FROM approved_applications WHERE application_key = ?",
            (application_key(executable),),
        ).fetchone()
        return None if row is None else _record(row)

    def list(self) -> tuple[ApprovedApplication, ...]:
        """Every recorded application, ordered for display."""
        rows = self._connection.execute(
            "SELECT * FROM approved_applications ORDER BY display_name, executable"
        ).fetchall()
        return tuple(_record(row) for row in rows)

    # -------------------------------------------------------------- review

    def propose(
        self,
        executable: Path,
        display_name: str,
        *,
        close_supported: bool = True,
    ) -> ApprovedApplication:
        """Record an application as pending approval, hashed as it is now.

        Calling this again for the same path refreshes the hash and returns the
        record to pending, which is what a changed file needs.
        """
        executable = Path(executable)
        name = display_name.strip()
        if not name:
            name = executable.stem
        now = self._clock().isoformat()
        self._connection.execute(
            """
            INSERT INTO approved_applications (
                application_key, executable, sha256, display_name,
                approved, close_supported, created_at, approved_at
            ) VALUES (?, ?, ?, ?, 0, ?, ?, NULL)
            ON CONFLICT(application_key) DO UPDATE SET
                sha256 = excluded.sha256,
                display_name = excluded.display_name,
                close_supported = excluded.close_supported,
                approved = 0,
                approved_at = NULL
            """,
            (
                application_key(executable),
                str(executable),
                executable_sha256(executable),
                name,
                int(close_supported),
                now,
            ),
        )
        self._connection.commit()
        return self._require(executable)

    def approve(
        self,
        executable: Path,
        *,
        display_name: str | None = None,
        close_supported: bool | None = None,
    ) -> ApprovedApplication:
        """Approve the version on disk right now, re-hashing it as the user confirms."""
        existing = self.find(executable)
        if existing is None:
            self.propose(
                executable,
                display_name or Path(executable).stem,
                close_supported=True if close_supported is None else close_supported,
            )
            existing = self._require(executable)
        self._connection.execute(
            """
            UPDATE approved_applications
               SET sha256 = ?, approved = 1, approved_at = ?,
                   display_name = ?, close_supported = ?
             WHERE application_key = ?
            """,
            (
                executable_sha256(executable),
                self._clock().isoformat(),
                (display_name or existing.display_name).strip() or existing.display_name,
                int(existing.close_supported if close_supported is None else close_supported),
                application_key(executable),
            ),
        )
        self._connection.commit()
        return self._require(executable)

    def set_close_supported(self, executable: Path, close_supported: bool) -> ApprovedApplication:
        """Record whether Once may close this application, as measured for it."""
        self._connection.execute(
            "UPDATE approved_applications SET close_supported = ? WHERE application_key = ?",
            (int(close_supported), application_key(executable)),
        )
        self._connection.commit()
        return self._require(executable)

    def forget(self, executable: Path) -> None:
        """Remove the approval entirely, so the application must be approved again."""
        self._connection.execute(
            "DELETE FROM approved_applications WHERE application_key = ?",
            (application_key(executable),),
        )
        self._connection.commit()

    def _require(self, executable: Path) -> ApprovedApplication:
        record = self.find(executable)
        if record is None:  # pragma: no cover - the caller just wrote this row
            raise KeyError(f"No approved-application record for {executable}.")
        return record


def _record(row: sqlite3.Row) -> ApprovedApplication:
    return ApprovedApplication(
        executable=Path(row["executable"]),
        sha256=row["sha256"],
        display_name=row["display_name"],
        approved=bool(row["approved"]),
        close_supported=bool(row["close_supported"]),
    )

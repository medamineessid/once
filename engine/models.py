"""Domain models for Once."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class OperationType(StrEnum):
    """Kinds of file-system operation Once can plan."""

    CREATE_FOLDER = "CREATE_FOLDER"
    RENAME = "RENAME"
    MOVE = "MOVE"
    COPY = "COPY"


class Severity(StrEnum):
    """How an issue affects a plan."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class OpStatus(StrEnum):
    """Lifecycle state for a single operation."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    UNDONE = "UNDONE"
    UNDO_REFUSED = "UNDO_REFUSED"
    UNDO_FAILED = "UNDO_FAILED"
    UNKNOWN = "UNKNOWN"


class RunStatus(StrEnum):
    """Lifecycle state for an execution run."""

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"
    UNDONE = "UNDONE"
    PARTIALLY_UNDONE = "PARTIALLY_UNDONE"


class IssueCode(StrEnum):
    """Stable machine-readable issue codes."""

    NAME_EMPTY = "NAME_EMPTY"
    NAME_INVALID_CHARS = "NAME_INVALID_CHARS"
    NAME_RESERVED = "NAME_RESERVED"
    NAME_TRAILING_DOT_OR_SPACE = "NAME_TRAILING_DOT_OR_SPACE"
    NAME_TOO_LONG = "NAME_TOO_LONG"
    PATH_TOO_LONG = "PATH_TOO_LONG"
    DEST_EXISTS = "DEST_EXISTS"
    DEST_DUPLICATE_IN_PLAN = "DEST_DUPLICATE_IN_PLAN"
    SOURCE_MISSING = "SOURCE_MISSING"
    SOURCE_CHANGED = "SOURCE_CHANGED"
    SOURCE_NOT_REGULAR_FILE = "SOURCE_NOT_REGULAR_FILE"
    SOURCE_IS_LINK = "SOURCE_IS_LINK"
    DEST_PARENT_MISSING = "DEST_PARENT_MISSING"
    CROSS_VOLUME_MOVE_UNSUPPORTED = "CROSS_VOLUME_MOVE_UNSUPPORTED"
    CYCLE_DETECTED = "CYCLE_DETECTED"
    NO_CHANGE = "NO_CHANGE"
    CASE_ONLY_RENAME = "CASE_ONLY_RENAME"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    FILE_IN_USE = "FILE_IN_USE"
    DEPENDENCY_FAILED = "DEPENDENCY_FAILED"
    CANCELLED_BY_USER = "CANCELLED_BY_USER"
    UNEXPECTED_OS_ERROR = "UNEXPECTED_OS_ERROR"


@dataclass(frozen=True)
class Fingerprint:
    """Immutable file fingerprint used for revalidation."""

    size: int
    mtime_ns: int

    @classmethod
    def from_stat(cls, stat_result: object) -> Fingerprint:
        """Build a fingerprint from an ``os.stat_result`` object."""
        return cls(size=stat_result.st_size, mtime_ns=stat_result.st_mtime_ns)


@dataclass(frozen=True)
class FileEntry:
    """Metadata for a file found during scanning."""

    path: Path
    name: str
    stem: str
    suffix: str
    size: int
    mtime_ns: int
    birthtime_ns: int | None
    is_hidden: bool


@dataclass(frozen=True)
class Issue:
    """Structured issue record with a plain-language explanation."""

    code: IssueCode
    severity: Severity
    message: str


@dataclass(frozen=True)
class Operation:
    """Single planned filesystem action."""

    op_id: str
    op_type: OperationType
    source: Path | None
    destination: Path
    expected_source: Fingerprint | None
    issues: tuple[Issue, ...]
    depends_on: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class Plan:
    """A sequence of operations produced by the planner."""

    plan_id: str
    source_folder: Path
    workflow_name: str | None
    created_at: datetime
    operations: tuple[Operation, ...]
    excluded: tuple[object, ...]


@dataclass(frozen=True)
class ApprovedPlan:
    """Validated plan approved for execution."""

    plan: Plan
    approved_at: datetime


@dataclass(frozen=True)
class OperationResult:
    """Outcome of a single operation in a run report."""

    op_id: str
    op_type: OperationType
    source: Path | None
    destination: Path
    status: str
    issue: Issue | None
    undo_eligible_hint: bool


@dataclass(frozen=True)
class RunReport:
    """Summary of a completed execution run."""

    run_id: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime
    results: tuple[OperationResult, ...]

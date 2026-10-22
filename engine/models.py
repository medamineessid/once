"""Domain enums for Once.

These definitions mirror the domain model in ``AGENTS.md``. Dataclasses
(operations, plans, reports) arrive with the steps that first need them.
"""

from __future__ import annotations

from enum import StrEnum


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
    """Lifecycle of one operation during and after execution."""

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
    """Lifecycle of a whole run."""

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"
    UNDONE = "UNDONE"
    PARTIALLY_UNDONE = "PARTIALLY_UNDONE"


class IssueCode(StrEnum):
    """Stable machine-readable reason codes for planner and execution issues."""

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

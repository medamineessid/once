"""Exception hierarchy for Once.

Every error raised deliberately by application code derives from OnceError.
Callers can distinguish expected failures from programming errors, and the UI
can present the message without exposing stack traces.
"""

from __future__ import annotations


class OnceError(Exception):
    """Base class for errors that Once reports to the user."""


class WorkflowValidationError(OnceError):
    """A workflow definition is invalid or cannot be loaded safely."""


class PlanError(OnceError):
    """A plan cannot be built or approved."""


class ExecutionError(OnceError):
    """An approved plan could not be executed as specified."""


class RecoveryError(OnceError):
    """An undo or recovery action could not be performed safely."""

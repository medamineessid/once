"""Git-backed coding-agent proposal integration.

The agent command is an exactly configured argv template (no shell), always
runs on a freshly created separate branch, and its output diff is captured for
human review. This module never merges, pushes, or force-updates anything; the
approval-gated local fast-forward merge lives in the controller.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from engine.agent_change import MAX_DIFF_CHARS, ChangeReview
from engine.errors import AgentIntegrationError

MAX_TIMEOUT_SECONDS = 600.0
MAX_AGENT_OUTPUT_CHARS = 2_000
EVIDENCE_PLACEHOLDER = "{evidence}"
BRANCH_PREFIX = "once/agent"


@dataclass(frozen=True)
class AgentCommand:
    """An exact argv template with one {evidence} placeholder; shell disabled."""

    argv: tuple[str, ...]
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.argv or sum(argument == EVIDENCE_PLACEHOLDER for argument in self.argv) != 1:
            raise AgentIntegrationError(
                "The agent command must contain exactly one {evidence} argument."
            )
        if not 0 < self.timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise AgentIntegrationError(
                "The agent command timeout must be between 0 and 600 seconds."
            )
        if any(not isinstance(argument, str) or not argument for argument in self.argv):
            raise AgentIntegrationError("Agent command arguments must be non-empty text.")

    def for_evidence(self, evidence_path: Path) -> tuple[str, ...]:
        return tuple(
            str(evidence_path) if argument == EVIDENCE_PLACEHOLDER else argument
            for argument in self.argv
        )


class GitRepository:
    """Read-side and branch-side git operations for agent proposals."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    def run_git(self, *args: str) -> str:
        """Run one exact git argv with the shell disabled and fail closed."""
        completed = subprocess.run(  # noqa: S603 - exact git argv, shell disabled
            ("git", *args),  # noqa: S607 - git is on the managed tool path
            cwd=self._path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            shell=False,
        )
        if completed.returncode != 0:
            raise AgentIntegrationError(
                f"Git command failed: {_tail(completed.stderr) or 'no error details.'}"
            )
        return completed.stdout.strip()

    def current_branch(self) -> str:
        return self.run_git("rev-parse", "--abbrev-ref", "HEAD")

    def head(self) -> str:
        return self.run_git("rev-parse", "HEAD")

    def ensure_clean(self) -> None:
        status = self.run_git("status", "--porcelain")
        if status:
            raise AgentIntegrationError(
                "The repository has uncommitted changes. Commit or stash them "
                "before requesting an agent proposal."
            )

    def create_agent_branch(self) -> tuple[str, str, str]:
        """Create a unique agent branch and return (branch, original, base_commit)."""
        original = self.current_branch()
        self.ensure_clean()
        base_commit = self.head()
        while True:
            branch = f"{BRANCH_PREFIX}/{uuid4().hex[:8]}"
            completed = subprocess.run(  # noqa: S603 - exact git argv, shell disabled
                ("git", "checkout", "-b", branch),  # noqa: S607 - managed tool path
                cwd=self._path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                shell=False,
            )
            if completed.returncode == 0:
                return branch, original, base_commit
            text = completed.stdout + completed.stderr
            if "already exists" in text:
                continue
            raise AgentIntegrationError(
                f"Could not create the agent branch: {_tail(text) or 'no error details.'}"
            )

    def restore(self, branch: str) -> None:
        self.run_git("checkout", branch)
        self.ensure_clean()

    def capture(self, base_commit: str) -> tuple[str, tuple[str, ...], tuple[str, ...], bool]:
        """Return (diff, changed tracked files, untracked files, truncated)."""
        diff = self.run_git("diff", "--no-ext-diff", base_commit, "--")
        truncated = len(diff) > MAX_DIFF_CHARS
        changed = tuple(
            line
            for line in self.run_git("diff", "--name-only", base_commit, "--").splitlines()
            if line
        )
        untracked = tuple(
            line.split(" ", 1)[-1].strip()
            for line in self.run_git("status", "--porcelain").splitlines()
            if line.startswith("??")
        )
        return (diff[:MAX_DIFF_CHARS] if truncated else diff, changed, untracked, truncated)

    def fast_forward(self, branch: str) -> str:
        """Fast-forward the current branch only; never creates commits or pushes."""
        self.run_git("merge", "--ff-only", branch)
        return self.head()


def _tail(value: str | None) -> str:
    if not value:
        return ""
    text = value.strip()
    return text[-MAX_AGENT_OUTPUT_CHARS:]


@dataclass(frozen=True)
class AgentProposalResult:
    """What a successful agent run produced, ready for review persistence."""

    review: ChangeReview
    agent_stdout_tail: str
    agent_stderr_tail: str


def run_agent_for_proposal(
    repo_path: Path,
    argv: tuple[str, ...],
    timeout_seconds: float,
    evidence_path: Path,
    proposal_id: str | None = None,
) -> AgentProposalResult:
    """Run one allowlisted agent command on a separate branch and capture its diff.

    Raises AgentIntegrationError (after restoring the original branch) when the
    repository is dirty, the command fails, or it proposes no changes.
    """
    command = AgentCommand(argv, timeout_seconds)
    repository = GitRepository(repo_path)
    branch, original, base_commit = repository.create_agent_branch()
    try:
        completed = subprocess.run(  # noqa: S603 - exact configured argv, shell disabled
            command.for_evidence(evidence_path),
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=command.timeout_seconds,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as error:
        repository.restore(original)
        raise AgentIntegrationError(
            "The coding agent did not finish in time, so no proposal was recorded."
        ) from error
    if completed.returncode != 0:
        repository.restore(original)
        raise AgentIntegrationError(
            "The coding agent exited with an error, so no proposal was recorded."
        )
    status = repository.run_git("status", "--porcelain")
    if not status:
        repository.restore(original)
        raise AgentIntegrationError(
            "The coding agent did not propose any changes, so no proposal was recorded."
        )
    # The reviewed diff and the approved branch tip must be the same content:
    # snapshot the agent's result once on its own branch, then capture.
    repository.run_git("add", "-A")
    repository.run_git(
        "commit",
        "-m",
        "Once agent proposal snapshot - review before approval",
    )
    diff, changed, untracked, truncated = repository.capture(base_commit)
    agent_tip = repository.head()
    repository.restore(original)
    return AgentProposalResult(
        ChangeReview(
            proposal_id or uuid4().hex,
            str(repo_path),
            original,
            branch,
            base_commit,
            agent_tip,
            diff,
            changed[:500],
            untracked[:500],
            truncated,
        ),
        _tail(completed.stdout),
        _tail(completed.stderr),
    )

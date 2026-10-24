"""Git-backed coding-agent proposal integration.

The agent command is an exactly configured argv template (no shell), always
runs on a freshly created separate branch, and its output diff is captured for
human review. This module never merges, pushes, or force-updates anything; the
approval-gated local fast-forward merge lives in the controller.
"""

from __future__ import annotations

import shutil
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
PARK_MESSAGE = "Once agent failure output - kept for inspection, not a proposal"


def git_executable() -> str:
    """Return the absolute Git path resolved from PATH, failing when Git is missing."""
    resolved = shutil.which("git")
    if resolved is None:
        raise AgentIntegrationError(
            "Git was not found on the PATH, so proposal and verification "
            "operations that need Git cannot run. Install Git and make sure "
            "the 'git' command is available on the PATH."
        )
    return resolved


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
        self._git = git_executable()

    def run_git(self, *args: str) -> str:
        """Run one exact git argv with the shell disabled and fail closed."""
        completed = subprocess.run(  # noqa: S603 - exact git argv, shell disabled
            (self._git, *args),
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
                (self._git, "checkout", "-b", branch),
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


class WorktreeCheckout:
    """A disposable, detached git worktree bound to one exact proposal commit.

    The worktree only ever contains committed proposal state; cleanup uses a
    plain `git worktree remove` and never deletes data. If the worktree is
    dirty, cleanup reports failure and leaves it in place for inspection.
    """

    def __init__(self, repo_path: Path, path: Path) -> None:
        self._repo_path = Path(repo_path).resolve()
        self._path = Path(path).resolve()
        self._git = git_executable()

    @property
    def path(self) -> Path:
        """Return the checked-out directory used as the {checkout} substitute."""
        return self._path

    def create(self, commit: str) -> None:
        """Add a detached worktree at the exact commit, or fail closed."""
        if self._repo_path in self._path.parents or self._path == self._repo_path:
            raise AgentIntegrationError("The worktree path must be outside the repository.")
        if self._path.exists():
            raise AgentIntegrationError(
                f"A leftover worktree directory exists at {self._path}. Restore or "
                "remove it safely before verification can run again."
            )
        if not self._path.parent.exists():
            # The root is a dedicated Once-owned worktree directory; create it
            # deterministically instead of failing on a fresh machine.
            self._path.parent.mkdir(parents=True, exist_ok=True)
        identity = subprocess.run(  # noqa: S603 - exact git argv, shell disabled
            (self._git, "-C", str(self._repo_path), "cat-file", "-e", f"{commit}^{{commit}}"),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            shell=False,
        )
        if identity.returncode != 0:
            raise AgentIntegrationError(
                "The proposal commit no longer exists in this repository, so it "
                "must be re-proposed before verification."
            )
        created = subprocess.run(  # noqa: S603 - exact git argv, shell disabled
            (
                self._git,
                "-C",
                str(self._repo_path),
                "worktree",
                "add",
                "--detach",
                str(self._path),
                commit,
            ),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            shell=False,
        )
        if created.returncode != 0:
            raise AgentIntegrationError(
                "Could not create the verification worktree: "
                f"{_tail(created.stdout + created.stderr) or 'no error details.'}"
            )
        confirmed = subprocess.run(  # noqa: S603 - exact git argv, shell disabled
            (self._git, "-C", str(self._path), "rev-parse", "HEAD"),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            shell=False,
        )
        if confirmed.returncode != 0 or confirmed.stdout.strip() != commit:
            self.close()
            raise AgentIntegrationError(
                "The created worktree does not match the proposal commit, so "
                "verification was refused rather than run in a wrong tree."
            )

    def close(self) -> bool:
        """Remove the worktree if it is clean; never force-delete anything."""
        completed = subprocess.run(  # noqa: S603 - exact git argv, shell disabled
            (self._git, "-C", str(self._repo_path), "worktree", "remove", str(self._path)),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            shell=False,
        )
        return completed.returncode == 0


def _commit_parked(repository: GitRepository) -> None:
    """Stage and commit all parked output, bypassing project hooks when needed."""
    repository.run_git("add", "-A")
    try:
        repository.run_git("commit", "-m", PARK_MESSAGE)
    except AgentIntegrationError:
        repository.run_git("commit", "--no-verify", "-m", PARK_MESSAGE)


def _park_and_restore(repository: GitRepository, original: str, agent_branch: str) -> str:
    """Park any agent output and restore the original branch; explain otherwise.

    Returns a short plain-language note naming where incomplete output went
    ("" when there was nothing to park). A crashed or timed-out agent's
    half-written files are never deleted: they are parked in one clearly
    labelled commit with hook checks bypassed, because parking must not depend
    on project hooks. Parking never commits onto a branch Once did not create:
    if an agent moved the tree onto an existing branch, a fresh Once-prefix
    parked branch is created so user branch history stays untouched. If even
    parking fails, the function leaves the repository untouched and returns a
    plain-language description of the state left behind, so the caller can
    hand the user exact recovery instructions.
    """
    try:
        if repository.run_git("status", "--porcelain"):
            current = repository.current_branch()
            if current != agent_branch:
                parked = f"{BRANCH_PREFIX}/parked-{uuid4().hex[:8]}"
                repository.run_git("checkout", "-b", parked)
                _commit_parked(repository)
                repository.restore(original)
                return (
                    f" The agent's incomplete output was parked on branch {parked} for inspection."
                )
            _commit_parked(repository)
            repository.restore(original)
            return (
                " The agent's incomplete output was parked on branch "
                f"{agent_branch} for inspection."
            )
        repository.restore(original)
        return ""
    except AgentIntegrationError as error:
        try:
            left_on = repository.current_branch()
        except AgentIntegrationError:
            left_on = agent_branch
        return (
            f" Once could not restore the repository automatically: it is "
            f"still on branch {left_on}, with the changes kept in place. The "
            f"original branch {original} holds the pre-run content and was "
            f"not modified by Once. Recover in Git (for example, inspect and "
            f"commit or move the changes, then check out {original}) before "
            f"using Once on this repository again. Git said: {error}"
        )


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
        leftover = _park_and_restore(repository, original, branch)
        raise AgentIntegrationError(
            "The coding agent did not finish in time, so no proposal was recorded." + leftover
        ) from error
    if completed.returncode != 0:
        leftover = _park_and_restore(repository, original, branch)
        raise AgentIntegrationError(
            "The coding agent exited with an error, so no proposal was recorded." + leftover
        )
    status = repository.run_git("status", "--porcelain")
    if not status:
        repository.restore(original)
        raise AgentIntegrationError(
            "The coding agent did not propose any changes, so no proposal was recorded."
        )
    if repository.current_branch() != branch:
        leftover = _park_and_restore(repository, original, branch)
        raise AgentIntegrationError(
            "The coding agent switched Git branches during its run, so its output "
            "could not be captured as a proposal. Nothing was recorded." + leftover
        )
    # The reviewed diff and the approved branch tip must be the same content:
    # snapshot the agent's result once on its own branch, then capture.
    try:
        repository.run_git("add", "-A")
        repository.run_git(
            "commit",
            "-m",
            "Once agent proposal snapshot - review before approval",
        )
        diff, changed, untracked, truncated = repository.capture(base_commit)
        agent_tip = repository.head()
    except AgentIntegrationError as error:
        leftover = _park_and_restore(repository, original, branch)
        raise AgentIntegrationError(
            "The agent's changes could not be captured as a proposal, so no "
            "proposal was recorded." + leftover
        ) from error
    try:
        repository.restore(original)
    except AgentIntegrationError as error:
        raise AgentIntegrationError(
            "The agent's proposal was captured on branch "
            f"{branch} (tip {agent_tip[:12]}), but Once could not switch the "
            f"repository back to branch {original}; it is still on the agent "
            "branch. Nothing was merged. Check out the original branch in Git "
            f"to continue working, then re-propose. Git said: {error}"
        ) from error
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

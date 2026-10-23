"""Qt-free services that connect the UI to the workflow engine."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from ai.approval import ApprovedProposal
from engine.acceptance import load_acceptance_cases
from engine.agent_change import ApprovedChange, ChangeReview, approve_change
from engine.errors import AgentIntegrationError, WorkflowValidationError
from engine.loop import FixProposer, LoopController, LoopPolicy, LoopRun
from engine.replay import ReplayExecutor, ReplayPreview
from engine.verifier import (
    AcceptanceVerifier,
    AllowlistedCommand,
    EvidenceBundle,
)
from engine.workflow import (
    StepKind,
    StepResult,
    UIElementInspector,
    WindowInspector,
    Workflow,
    WorkflowRun,
    WorkflowRunner,
    WorkflowStep,
)
from integrations.coding_agent import GitRepository, WorktreeCheckout, run_agent_for_proposal
from storage.database import connect
from storage.history import (
    AgentProposalRecord,
    ExecutionHistory,
    ProposalVerificationRecord,
    WorktreeRecord,
)
from storage.workflows import load_workflow, save_workflow


class WorkflowService:
    """Create and execute the currently supported local workflow definitions."""

    def __init__(
        self,
        runner: WorkflowRunner | None = None,
        history: ExecutionHistory | None = None,
        workflow_directory: Path | None = None,
        window_inspector: WindowInspector | None = None,
        ui_element_inspector: UIElementInspector | None = None,
    ) -> None:
        self._runner = runner or WorkflowRunner()
        self._replay = ReplayExecutor()
        if window_inspector is None:
            from integrations.windows_automation import PywinautoWindowInspector

            self._window_inspector = PywinautoWindowInspector().inspect
        else:
            self._window_inspector = window_inspector
        if ui_element_inspector is None:
            from integrations.windows_automation import PywinautoWindowInspector

            self._ui_element_inspector = PywinautoWindowInspector().inspect_element
        else:
            self._ui_element_inspector = ui_element_inspector
        self._history = history
        self._workflow_directory = workflow_directory
        if workflow_directory is not None:
            workflow_directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def for_app_data(cls, app_data_dir: Path) -> WorkflowService:
        """Create a service backed by the application's local data directory."""
        workflow_directory = app_data_dir / "workflows"
        workflow_directory.mkdir(parents=True, exist_ok=True)
        history = ExecutionHistory(connect(app_data_dir / "once.db"))
        return cls(history=history, workflow_directory=workflow_directory)

    @staticmethod
    def demo_workflow() -> Workflow:
        """Return a visible, deterministic workflow used by the first UI milestone."""
        return Workflow(
            workflow_id="demo-local-workflow",
            name="Local workflow foundation demo",
            steps=(
                WorkflowStep(
                    step_id="inspect",
                    name="Inspect workflow",
                    kind=StepKind.REPORT,
                    message="Workflow definition accepted.",
                ),
                WorkflowStep(
                    step_id="record",
                    name="Record controlled result",
                    kind=StepKind.REPORT,
                    message="Controlled result recorded locally.",
                ),
            ),
        )

    def run_demo(self) -> WorkflowRun:
        """Execute the demo through the same service path used by future workflows."""
        return self.run_workflow(self.demo_workflow())

    def run_workflow(
        self,
        workflow: Workflow,
        allowed_root: Path | None = None,
        cancel_check: Callable[[], bool] | None = None,
        progress_callback: Callable[[StepResult], None] | None = None,
    ) -> WorkflowRun:
        """Execute a workflow and persist its real outcome when history is configured."""
        run = self._runner.run(
            workflow,
            allowed_root=allowed_root,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
        )
        if self._history is not None:
            self._history.record(run)
        return run

    def save(self, workflow: Workflow, path: Path | None = None) -> Path:
        """Validate and save a workflow through the storage boundary."""
        if self._workflow_directory is None and path is None:
            raise WorkflowValidationError("Workflow storage is not configured.")
        destination = path or self._workflow_directory / f"{workflow.workflow_id}.json"
        save_workflow(workflow, destination)
        return destination

    def save_approved(self, proposal: ApprovedProposal) -> Path:
        """Save only a proposal that passed the explicit approval gate."""
        if not isinstance(proposal, ApprovedProposal):
            raise WorkflowValidationError("Only an explicitly approved proposal can be saved.")
        return self.save(proposal.workflow)

    def run_approved(
        self,
        proposal: ApprovedProposal,
        allowed_root: Path | None = None,
        cancel_check: Callable[[], bool] | None = None,
        progress_callback: Callable[[StepResult], None] | None = None,
    ) -> WorkflowRun:
        """Execute only a proposal that passed the explicit approval gate."""
        if not isinstance(proposal, ApprovedProposal):
            raise WorkflowValidationError("Only an explicitly approved proposal can run.")
        return self.run_replay(
            proposal.workflow,
            allowed_root=allowed_root,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
        )

    def preview_replay(self, workflow: Workflow) -> ReplayPreview:
        """Return a policy check and readable preview without executing."""
        return self._replay.preview(workflow)

    def run_replay(
        self,
        workflow: Workflow,
        allowed_root: Path | None,
        cancel_check: Callable[[], bool] | None = None,
        progress_callback: Callable[[StepResult], None] | None = None,
        window_inspector: WindowInspector | None = None,
        ui_element_inspector: UIElementInspector | None = None,
    ) -> WorkflowRun:
        """Execute and persist only actions allowed by the replay policy."""
        run = self._replay.execute(
            workflow,
            allowed_root=allowed_root,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
            window_inspector=window_inspector or self._window_inspector,
            ui_element_inspector=ui_element_inspector or self._ui_element_inspector,
        )
        if self._history is not None:
            self._history.record(run)
        return run

    def verify_acceptance(
        self,
        cases_path: Path,
        argv: tuple[str, ...],
        timeout_seconds: float = 30.0,
        checkout: Path | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> EvidenceBundle:
        """Run allowlisted acceptance verification and persist the outcome."""
        verifier = AcceptanceVerifier(AllowlistedCommand(argv, timeout_seconds))
        bundle = verifier.verify(
            load_acceptance_cases(cases_path), cancel_check=cancel_check, checkout=checkout
        )
        if self._history is not None:
            self._history.record_verification(bundle)
        return bundle

    def acceptance_history(self) -> tuple[EvidenceBundle, ...]:
        """Return persisted verification runs, newest first."""
        if self._history is None:
            return ()
        return self._history.list_verification_runs()

    def verification_run(self, run_id: str) -> EvidenceBundle | None:
        """Return one persisted verification run by id, or None."""
        if self._history is None:
            return None
        for bundle in self._history.list_verification_runs():
            if bundle.run_id == run_id:
                return bundle
        return None

    def verify_proposal_pre_merge(
        self,
        review: object,
        cases_path: Path,
        verifier_argv: tuple[str, ...],
        timeout_seconds: float,
        worktree_root: Path,
        cancel_check: Callable[[], bool] | None = None,
    ) -> EvidenceBundle:
        """Verify a proposal's exact commit inside a disposable worktree.

        Verification refuses a proposal whose commit no longer matches its
        branch tip or that was already decided, runs the allowlisted checkers
        with {checkout} bound to the worktree, and always restores the main
        checkout unchanged.
        """
        if not isinstance(review, ChangeReview):
            raise WorkflowValidationError("Only a recorded review can be verified.")
        record = self._proposal_record(review.proposal_id)
        if record is not None and record.review != review:
            raise AgentIntegrationError(
                "The proposal you are verifying does not match the recorded "
                "proposal with the same id, so it must be re-proposed and "
                "reviewed again."
            )
        repository = GitRepository(Path(review.repo_path))
        if repository.run_git("rev-parse", f"refs/heads/{review.agent_branch}") != review.agent_tip:
            raise AgentIntegrationError(
                "The proposal commit is no longer the tip of its branch, so it "
                "must be proposed and reviewed again before verification."
            )
        status = self._proposal_status(review.proposal_id)
        if status not in (None, "PENDING"):
            raise AgentIntegrationError(
                "This proposal has already been approved or rejected, so it "
                "cannot be verified again."
            )
        worktree = WorktreeCheckout(
            Path(review.repo_path),
            Path(worktree_root) / f"proposal-{review.proposal_id[:8]}",
        )
        worktree_path = str(worktree.path)
        try:
            worktree.create(review.agent_tip)
        except AgentIntegrationError:
            self._record_worktree(review, worktree_path, "REFUSED")
            raise
        self._record_worktree(review, worktree_path, "ACTIVE")
        try:
            verifier = AcceptanceVerifier(AllowlistedCommand(tuple(verifier_argv), timeout_seconds))
            bundle = verifier.verify(
                load_acceptance_cases(cases_path),
                cancel_check=cancel_check,
                checkout=worktree.path,
            )
        finally:
            closed = worktree.close()
            self._record_worktree(review, worktree_path, "CLOSED" if closed else "LEFTOVER")
        if self._history is not None:
            self._history.record_verification(bundle)
            self._history.record_proposal_verification(
                ProposalVerificationRecord(
                    proposal_id=review.proposal_id,
                    agent_tip=review.agent_tip,
                    phase="PRE_MERGE",
                    verification_run_id=bundle.run_id,
                    passed=bundle.passed and not bundle.cancelled,
                    cancelled=bundle.cancelled,
                    checked_at=datetime.now(UTC).isoformat(),
                )
            )
        return bundle

    def verify_post_merge(
        self,
        repo_path: Path,
        cases_path: Path,
        verifier_argv: tuple[str, ...],
        timeout_seconds: float,
        review: object,
    ) -> EvidenceBundle:
        """Rerun the required verification against the merged main checkout."""
        if not isinstance(review, ChangeReview):
            raise WorkflowValidationError("Only a recorded review can be verified.")
        verifier = AcceptanceVerifier(AllowlistedCommand(tuple(verifier_argv), timeout_seconds))
        bundle = verifier.verify(
            load_acceptance_cases(cases_path), checkout=Path(repo_path).resolve()
        )
        if self._history is not None:
            self._history.record_verification(bundle)
            self._history.record_proposal_verification(
                ProposalVerificationRecord(
                    proposal_id=review.proposal_id,
                    agent_tip=review.agent_tip,
                    phase="POST_MERGE",
                    verification_run_id=bundle.run_id,
                    passed=bundle.passed,
                    cancelled=bundle.cancelled,
                    checked_at=datetime.now(UTC).isoformat(),
                )
            )
        return bundle

    def proposal_verifications(self, proposal_id: str) -> tuple[ProposalVerificationRecord, ...]:
        """Return persisted verifications for one proposal, newest first."""
        if self._history is None:
            return ()
        return self._history.list_proposal_verifications(proposal_id)

    def _record_worktree(self, review: object, path: str, status: str) -> None:
        """Persist one worktree lifecycle event when history is configured."""
        if not isinstance(review, ChangeReview) or self._history is None:
            return
        self._history.record_worktree(
            WorktreeRecord(
                proposal_id=review.proposal_id,
                agent_tip=review.agent_tip,
                path=path,
                status=status,
                created_at=datetime.now(UTC).isoformat(),
                closed_at=datetime.now(UTC).isoformat() if status != "ACTIVE" else None,
            )
        )

    def stale_worktrees(self) -> tuple[WorktreeRecord, ...]:
        """Return un-closed or refused worktree records, for safe recovery."""
        if self._history is None:
            return ()
        return self._history.stale_worktrees()

    def _identity_blocker(self, review: ChangeReview) -> str | None:
        """Return a plain-language message when review differs from the record.

        The reviewed diff, branch names, and commits must be exactly the ones
        recorded when the agent proposed the change; a stale or re-created
        review object must never be approved, applied, or verified.
        """
        record = self._proposal_record(review.proposal_id)
        if record is not None and record.review != review:
            return (
                "The proposal you are viewing does not match the recorded "
                "proposal with the same id. Close and reopen the Agent "
                "proposals tab to show the recorded diff, or reject it and "
                "request the fix again."
            )
        return None

    def _proposal_record(self, proposal_id: str) -> AgentProposalRecord | None:
        if self._history is None:
            return None
        return self._history.proposal_record(proposal_id)

    def approval_blockers(self, review: object) -> tuple[str, ...]:
        """Return plain-language reasons why this proposal cannot be approved."""
        if not isinstance(review, ChangeReview):
            raise WorkflowValidationError("Only a recorded review can be approved.")
        blockers: list[str] = []
        status = self._proposal_status(review.proposal_id)
        if status == "APPROVED":
            blockers.append("This proposal was already approved.")
        elif status == "REJECTED":
            blockers.append("This proposal was rejected.")
        elif status is None:
            blockers.append("This proposal is not recorded in the history database.")
        else:
            identity = self._identity_blocker(review)
            if identity is not None:
                blockers.append(identity)
        pre_merge = [
            record
            for record in self.proposal_verifications(review.proposal_id)
            if record.phase == "PRE_MERGE" and record.agent_tip == review.agent_tip
        ]
        if not pre_merge:
            blockers.append(
                "This proposal has no passed pre-merge verification record. Run "
                "the acceptance checks in the isolated worktree first."
            )
        elif pre_merge[0].cancelled:
            blockers.append(
                "The last pre-merge verification was cancelled, so it must run "
                "again before approval."
            )
        elif not pre_merge[0].passed:
            blockers.append(
                "The last pre-merge verification did not pass, so this proposal cannot be approved."
            )
        repository = GitRepository(Path(review.repo_path))
        try:
            tip_matches = (
                repository.run_git("rev-parse", f"refs/heads/{review.agent_branch}")
                == review.agent_tip
            )
            base_matches = repository.run_git("rev-parse", review.base_branch) == review.base_commit
        except AgentIntegrationError:
            blockers.append(
                "The proposal's branches no longer exist, so it must be "
                "re-proposed and reviewed again."
            )
        else:
            if not tip_matches:
                blockers.append(
                    "The proposal commit is no longer its branch tip, so it must be "
                    "re-proposed and reviewed again."
                )
            if not base_matches:
                blockers.append("The target repository has moved since the proposal was reviewed.")
        return tuple(blockers)

    def run_supervised_loop(
        self,
        cases_path: Path,
        argv: tuple[str, ...],
        timeout_seconds: float,
        policy: LoopPolicy,
        proposer: FixProposer | None = None,
    ) -> LoopRun:
        """Run the bounded verify-fix-rerun loop with allowlisted verification."""
        verifier = AcceptanceVerifier(AllowlistedCommand(argv, timeout_seconds))
        cases = load_acceptance_cases(cases_path)

        def verify_and_record() -> EvidenceBundle:
            bundle = verifier.verify(cases)
            if self._history is not None:
                self._history.record_verification(bundle)
            return bundle

        run = LoopController(verify_and_record, proposer=proposer).run(policy)
        if self._history is not None:
            self._history.record_loop(run)
        return run

    def loop_history(self) -> tuple[LoopRun, ...]:
        """Return persisted loop runs, newest first."""
        if self._history is None:
            return ()
        return self._history.list_loops()

    def request_agent_fix(
        self,
        repo_path: Path,
        argv: tuple[str, ...],
        timeout_seconds: float,
        evidence_path: Path,
    ) -> ChangeReview:
        """Run the allowlisted agent on a separate branch and record the proposal."""
        result = run_agent_for_proposal(repo_path, argv, timeout_seconds, evidence_path)
        if self._history is not None:
            self._history.record_agent_proposal(result.review, datetime.now(UTC).isoformat())
        return result.review

    def agent_proposals(self) -> tuple[AgentProposalRecord, ...]:
        """Return persisted agent proposals, newest first."""
        if self._history is None:
            return ()
        return self._history.list_agent_proposals()

    def approve_agent_change(self, review: object) -> ApprovedChange:
        """Record the human approval only when no blocker remains."""
        if not isinstance(review, ChangeReview):
            raise WorkflowValidationError("Only a real review can be approved.")
        status = self._proposal_status(review.proposal_id)
        if status == "PENDING":
            blockers = self.approval_blockers(review)
            if blockers:
                raise AgentIntegrationError(" ".join(blockers))
        elif status is None:
            raise AgentIntegrationError("This proposal is not recorded in the history.")
        else:
            raise AgentIntegrationError("This proposal has already been approved or rejected.")
        decided_at = datetime.now(UTC).isoformat()
        if self._history is not None:
            self._history.record_agent_decision(review.proposal_id, "APPROVED", decided_at)
        return approve_change(review)

    def reject_agent_proposal(self, review: object) -> str:
        """Record the human rejection of one pending proposal."""
        if not isinstance(review, ChangeReview):
            raise WorkflowValidationError("Only a real review can be rejected.")
        status = self._proposal_status(review.proposal_id)
        if status != "PENDING":
            raise AgentIntegrationError("This proposal has already been approved or rejected.")
        decided_at = datetime.now(UTC).isoformat()
        if self._history is not None:
            self._history.record_agent_decision(review.proposal_id, "REJECTED", decided_at)
        return decided_at

    def _proposal_status(self, proposal_id: str) -> str | None:
        if self._history is None:
            return None
        return self._history.proposal_status(proposal_id)

    def apply_agent_change(self, approved: object) -> str:
        """Fast-forward only a gate-approved agent change; never push or rebase."""
        if not isinstance(approved, ApprovedChange):
            raise WorkflowValidationError(
                "Only an explicitly approved change can be applied. "
                "Review the diff and approve it first."
            )
        review = approved.review
        status = self._proposal_status(review.proposal_id)
        if status != "APPROVED":
            raise AgentIntegrationError("Only a proposal with a recorded approval can be applied.")
        identity = self._identity_blocker(review)
        if identity is not None:
            raise AgentIntegrationError(identity)
        repository = GitRepository(Path(review.repo_path))
        repository.ensure_clean()
        if repository.current_branch() != review.base_branch:
            raise AgentIntegrationError(
                "The repository is not on the proposal's original branch, so the "
                "change cannot be applied right now."
            )
        if repository.head() != review.base_commit:
            raise AgentIntegrationError(
                "The repository has moved since the proposal was reviewed, so this "
                "proposal must be reviewed again before it can be applied."
            )
        if (
            repository.head() != review.agent_tip
            and repository.run_git("rev-parse", review.agent_branch) != review.agent_tip
        ):
            raise AgentIntegrationError(
                "The agent branch changed after the review, so this proposal must "
                "be reviewed again before it can be applied."
            )
        return repository.fast_forward(review.agent_branch)

    def list_saved(self) -> tuple[Path, ...]:
        """Return saved workflow files in deterministic order."""
        if self._workflow_directory is None:
            return ()
        return tuple(
            sorted(self._workflow_directory.glob("*.json"), key=lambda item: item.name.casefold())
        )

    @staticmethod
    def load(path: Path) -> Workflow:
        """Load one validated workflow through the storage boundary."""
        return load_workflow(path)

    def history(self) -> tuple[WorkflowRun, ...]:
        """Return persisted executions, newest first."""
        if self._history is None:
            return ()
        return tuple(record.run for record in self._history.list_runs())

    def close(self) -> None:
        """Release controller-owned persistence resources."""
        if self._history is not None:
            self._history.close()
            self._history = None


class AgentFixProposer:
    """A bounded-loop proposer that requests an allowlisted coding-agent fix.

    The proposer writes the redacted verification evidence to an explicit
    directory and records the agent's diff as a pending human review. It never
    executes agent output and never merges anything.
    """

    def __init__(
        self,
        service: WorkflowService,
        repo_path: Path,
        argv: tuple[str, ...],
        timeout_seconds: float,
        evidence_directory: Path,
    ) -> None:
        self._service = service
        self._repo_path = repo_path
        self._argv = argv
        self._timeout_seconds = timeout_seconds
        self._evidence_directory = evidence_directory

    def propose(self, evidence: EvidenceBundle) -> None:
        """Send redacted evidence to the agent and file its diff for review."""
        evidence_directory = Path(self._evidence_directory)
        evidence_directory.mkdir(parents=True, exist_ok=True)
        json_path, _ = evidence.write(evidence_directory)
        self._service.request_agent_fix(
            self._repo_path, self._argv, self._timeout_seconds, json_path
        )

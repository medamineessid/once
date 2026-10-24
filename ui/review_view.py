"""Review panel for coding-agent proposals.

Read-only display of persisted proposals, their diffs, and pre-merge
verification results, with explicit approve/reject actions that go through
the controller service. Approval and apply are enabled only for the exact
pending proposal that has a passing pre-merge verification of its current
commit, and whose base branch and agent branch are unchanged. After an
approved change is applied, the required verification runs again off the GUI
thread and is persisted as a POST_MERGE record.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controller.service import WorkflowService
from controller.verifier_config import VerifierConfig, load_verifier_config
from engine.agent_change import ChangeReview
from engine.errors import WorkflowValidationError
from engine.verifier import EvidenceBundle
from storage.history import AgentProposalRecord
from ui.verifier_dialog import VerifierConfigDialog
from ui.workers import (
    ApplyProposalWorker,
    ApplyRecordedApprovalWorker,
    PostMergeVerifyWorker,
    VerifyProposalWorker,
)

if TYPE_CHECKING:
    from collections.abc import Callable


class ProposalReviewPanel(QWidget):
    """One proposal at a time: diff, evidence, decision — always explicit."""

    _verify_worker_done = Signal(object)
    _apply_worker_done = Signal(object)

    def __init__(
        self,
        service: WorkflowService,
        verifier_config: VerifierConfig | None = None,
        verifier_note: str | None = None,
        app_data_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self._service = service
        self._verifier_config = verifier_config
        self._verifier_note = verifier_note
        self._app_data_dir = app_data_dir
        self._records: tuple[AgentProposalRecord, ...] = ()
        self._thread: QThread | None = None
        self._pending_action: Callable[[], None] | None = None
        self._worker: (
            VerifyProposalWorker
            | ApplyProposalWorker
            | ApplyRecordedApprovalWorker
            | PostMergeVerifyWorker
            | None
        ) = None

        self._proposal_list = QListWidget(self)
        self._status_label = QLabel("No proposal selected.", self)
        self._message_label = QLabel("", self)
        self._message_label.setWordWrap(True)
        self._base_label = QLabel("Base: -", self)
        self._tip_label = QLabel("Proposed commit: -", self)
        self._changed_files_label = QLabel("Changed files: -", self)
        self._diff_view = QPlainTextEdit(self)
        self._diff_view.setReadOnly(True)
        self._diff_view.setPlaceholderText("The exact unified diff under review appears here.")
        self._verification_list = QListWidget(self)
        self._verification_list.setAlternatingRowColors(True)
        self._evidence_view = QPlainTextEdit(self)
        self._evidence_view.setReadOnly(True)
        self._evidence_view.setPlaceholderText(
            "Redacted evidence of the latest pre-merge verification appears here."
        )
        self._blockers_label = QLabel("", self)
        self._blockers_label.setWordWrap(True)
        self._verify_button = QPushButton("Run pre-merge verification", self)
        self._verify_button.setObjectName("verifyProposalButton")
        self._approve_button = QPushButton("Approve and apply proposal", self)
        self._approve_button.setObjectName("approveProposalButton")
        self._apply_button = QPushButton("Apply previously approved proposal", self)
        self._apply_button.setObjectName("applyApprovedProposalButton")
        self._reject_button = QPushButton("Reject proposal", self)
        self._reject_button.setObjectName("rejectProposalButton")
        self._configure_button = QPushButton("Configure acceptance checks…", self)
        self._configure_button.setObjectName("configureVerifierButton")
        self._configure_button.setToolTip(
            "Save the checker configuration used for pre-merge verification."
        )

        self._proposal_list.currentRowChanged.connect(self._select_proposal)
        self._verify_button.clicked.connect(self._verify_selected)
        self._approve_button.clicked.connect(self._approve_and_apply)
        self._apply_button.clicked.connect(self._apply_recorded_approval)
        self._reject_button.clicked.connect(self._reject_selected)
        self._configure_button.clicked.connect(self._configure_checks)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Agent proposals (review the diff before any approval)", self))
        layout.addWidget(self._proposal_list)
        layout.addWidget(self._status_label)
        layout.addWidget(self._message_label)
        layout.addWidget(self._base_label)
        layout.addWidget(self._tip_label)
        layout.addWidget(self._changed_files_label)
        layout.addWidget(QLabel("Exact diff under review (read only):", self))
        layout.addWidget(self._diff_view)
        layout.addWidget(QLabel("Verification runs recorded for this proposal:", self))
        layout.addWidget(self._verification_list)
        layout.addWidget(QLabel("Redacted evidence (latest pre-merge run):", self))
        layout.addWidget(self._evidence_view)
        layout.addWidget(self._blockers_label)
        actions = QHBoxLayout()
        actions.addWidget(self._verify_button)
        actions.addWidget(self._approve_button)
        actions.addWidget(self._apply_button)
        actions.addWidget(self._reject_button)
        layout.addLayout(actions)
        layout.addWidget(self._configure_button)
        self.setLayout(layout)
        if verifier_note:
            self._message_label.setText(verifier_note)
        self.refresh_proposals()

    # ---------------------------------------------------------------- helpers

    def status_text(self) -> str:
        """Return the panel's transient message line; a stable hook for tests and users."""
        return self._message_label.text()

    def refresh_proposals(self) -> None:
        """Reload persisted proposals and keep the same selection when possible."""
        selected = self._selected_proposal_id()
        self._proposal_list.clear()
        self._records = self._service.agent_proposals()
        for index, record in enumerate(self._records):
            self._proposal_list.addItem(
                f"{record.review.proposal_id[:8]} — {record.status}"
                f" — {len(record.review.changed_files)} file(s)"
            )
            if record.review.proposal_id == selected:
                self._proposal_list.setCurrentRow(index)

    def _selected_proposal_id(self) -> str | None:
        row = self._proposal_list.currentRow()
        if 0 <= row < len(self._records):
            return self._records[row].review.proposal_id
        return None

    def _selected_record(self) -> AgentProposalRecord | None:
        row = self._proposal_list.currentRow()
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

    def _selected_review(self) -> ChangeReview | None:
        record = self._selected_record()
        return record.review if record is not None else None

    def _select_proposal(self, row: int) -> None:
        if not 0 <= row < len(self._records):
            self._show_record(None)
            return
        self._show_record(self._records[row])

    def _show_record(self, record: AgentProposalRecord | None) -> None:
        self._verification_list.clear()
        self._evidence_view.setPlainText("")
        if record is None:
            self._status_label.setText("No proposal selected.")
            self._base_label.setText("Base: -")
            self._tip_label.setText("Proposed commit: -")
            self._changed_files_label.setText("Changed files: -")
            self._diff_view.setPlainText("")
            self._blockers_label.setText("")
            self._message_label.setText("")
            self._update_action_buttons(None)
            return
        review = record.review
        self._status_label.setText(f"Proposal {review.proposal_id[:8]} — {record.status}")
        self._base_label.setText(f"Base: {review.base_branch} @ {review.base_commit[:12]}")
        self._tip_label.setText(f"Proposed commit: {review.agent_tip[:12]}")
        files = ", ".join((*review.changed_files, *review.untracked_files)) or "(none)"
        suffix = " (diff truncated)" if review.truncated else ""
        self._changed_files_label.setText(f"Changed files: {files}{suffix}")
        if review.truncated:
            self._diff_view.setPlainText(
                "The diff is too large to display in full.\n" + review.diff
            )
        else:
            self._diff_view.setPlainText(review.diff)
        self._load_verifications(review)
        self._update_action_buttons(record)

    def _load_verifications(self, review: ChangeReview) -> None:
        """List persisted verification runs bound to this proposal's commit."""
        latest_pre_merge: EvidenceBundle | None = None
        for record in self._service.proposal_verifications(review.proposal_id):
            if record.agent_tip != review.agent_tip:
                self._verification_list.addItem(
                    f"[{record.phase}] {record.verification_run_id[:8]} — "
                    "STALE COMMIT (not this proposed commit)"
                )
                continue
            bundle = self._service.verification_run(record.verification_run_id)
            state = self._record_state(record, bundle)
            self._verification_list.addItem(
                f"[{record.phase}] {record.verification_run_id[:8]} — {state}"
            )
            if bundle is None:
                self._verification_list.addItem("    Evidence for this run was not found.")
                continue
            if record.phase == "PRE_MERGE":
                latest_pre_merge = bundle
            self._list_bundle_cases(bundle)
        if self._verification_list.count() == 0:
            self._verification_list.addItem("Not run yet (no verification record).")
        self._show_evidence(latest_pre_merge)

    @staticmethod
    def _record_state(record: object, bundle: EvidenceBundle | None) -> str:
        passed = getattr(record, "passed", None)
        cancelled = getattr(record, "cancelled", False)
        if bundle is None:
            return "INCOMPLETE (evidence is missing)"
        if cancelled:
            return "CANCELLED"
        if passed:
            return "PASSED"
        return "FAILED"

    @staticmethod
    def _case_state(case: object) -> str:
        if case.timed_out:
            return "TIMED OUT"
        if case.exit_code is None and not case.fields:
            return "SKIPPED"
        return "PASSED" if case.passed else "FAILED"

    def _list_bundle_cases(self, bundle: EvidenceBundle) -> None:
        for case in bundle.cases:
            self._verification_list.addItem(
                f"    {case.case_id}: {self._case_state(case)}"
                f" (exit {case.exit_code}, redaction applied: {bundle.redaction_applied})"
            )
            for field in case.fields:
                self._verification_list.addItem(
                    f"      {field.field}: {field.status}"
                    f" (expected {field.expected}, observed {field.actual})"
                )

    def _show_evidence(self, bundle: EvidenceBundle | None) -> None:
        if bundle is None:
            self._evidence_view.setPlainText("")
            return
        self._evidence_view.setPlainText(
            "Output below was captured with a bounded redaction applied before display."
            "\n\n" + bundle.to_markdown()
        )

    def _update_action_buttons(self, record: AgentProposalRecord | None) -> None:
        decided = record is not None and record.status != "PENDING"
        self._verify_button.setEnabled(record is not None and not decided)
        self._reject_button.setEnabled(record is not None and not decided)
        self._approve_button.setEnabled(False)
        self._apply_button.setEnabled(False)
        if record is None:
            self._blockers_label.setText("")
            return
        if decided:
            if record.status == "REJECTED":
                self._blockers_label.setText(
                    "This proposal was rejected, so no further action is possible."
                )
                return
            # The approval is recorded; applying may still be possible after a
            # restart, under the same controller checks as a fresh apply.
            try:
                apply_blockers = self._service.apply_blockers(record.review)
            except WorkflowValidationError as error:
                self._blockers_label.setText(f"Apply check failed: {error}")
                return
            self._apply_button.setEnabled(not apply_blockers)
            self._blockers_label.setText(
                " ".join(apply_blockers) if apply_blockers else "Approved; you can apply it now."
            )
            return
        try:
            blockers = self._service.approval_blockers(record.review)
        except Exception as error:
            self._blockers_label.setText(f"Approval check failed: {error}")
            return
        if not blockers:
            self._approve_button.setEnabled(True)
        self._blockers_label.setText(" ".join(blockers))

    # ------------------------------------------------------------- actions

    def _configure_checks(self) -> None:
        """Open the checker editor and reload the configuration afterwards."""
        if self._app_data_dir is None:
            self._warn(
                "This session has no application data directory, so the "
                "checker configuration cannot be edited here."
            )
            return
        dialog = VerifierConfigDialog(self._app_data_dir, self._verifier_config, self)
        dialog.exec()
        self._reload_verifier_config()

    def _reload_verifier_config(self) -> None:
        """Re-read the checker configuration and refresh the tab's state."""
        try:
            self._verifier_config = load_verifier_config(self._app_data_dir)
        except WorkflowValidationError as error:
            self._verifier_note = str(error)
            self._message_label.setText(str(error))
            self._verifier_config = None
            return
        self._verifier_note = None
        if self._verifier_config is None:
            self._message_label.setText(
                "No acceptance checks are configured; pre-merge verification "
                "cannot run. Configure the checks to enable approval."
            )
        else:
            self._message_label.setText(
                "Acceptance checker configuration loaded. Select a proposal and "
                "run pre-merge verification."
            )

    def _verify_selected(self) -> None:
        review = self._selected_review()
        if review is None:
            self._warn("Select a proposal before verifying it.")
            return
        if self._verifier_config is None:
            if self._verifier_note:
                self._warn(self._verifier_note)
            else:
                self._warn("No acceptance checker is configured for this session.")
            return
        cases_path, argv, timeout_seconds, worktree_root = self._verifier_config
        self._start_worker(
            VerifyProposalWorker(
                self._service, review, cases_path, argv, timeout_seconds, worktree_root
            ),
            on_ok=self._verification_finished,
            running="Running acceptance checks in an isolated worktree…",
        )

    def _verification_finished(self, bundle: EvidenceBundle) -> None:
        self.refresh_proposals()
        outcome = "PASSED" if bundle.passed and not bundle.cancelled else "FAILED"
        self._message_label.setText(
            f"Verification finished: {outcome}."
            " Review the results, then approve or reject explicitly."
        )
        self._select_proposal(self._proposal_list.currentRow())
        self._verify_worker_done.emit(bundle)

    def _approve_and_apply(self) -> None:
        review = self._selected_review()
        if review is None:
            self._warn("Select a proposal before approving it.")
            return
        try:
            approved = self._service.approve_agent_change(review)
        except Exception as error:
            self._check_blockers(review)
            self._warn(str(error))
            return
        self._start_worker(
            ApplyProposalWorker(self._service, approved),
            on_ok=self._apply_finished,
            running="Applying the approved change with a local fast-forward merge…",
        )

    def _apply_recorded_approval(self) -> None:
        review = self._selected_review()
        if review is None:
            self._warn("Select a proposal before applying its approval.")
            return
        try:
            blockers = self._service.apply_blockers(review)
        except Exception as error:  # show the real failure, keep the repo state
            self._warn(str(error))
            return
        if blockers:
            self._warn(" ".join(blockers))
            return
        self._start_worker(
            ApplyRecordedApprovalWorker(self._service, review),
            on_ok=self._apply_finished,
            running="Applying the previously approved change with a local fast-forward merge…",
        )

    def _apply_finished(self, commit: str) -> None:
        self.refresh_proposals()
        self._select_proposal(self._proposal_list.currentRow())
        if self._verifier_config is None:
            self._message_label.setText(f"Applied the approved proposal: {commit[:12]}.")
            self._apply_worker_done.emit(commit)
            return
        cases_path, argv, timeout_seconds, _worktree_root = self._verifier_config
        review = self._selected_review()
        if review is None:
            self._message_label.setText(f"Applied the approved proposal: {commit[:12]}.")
            self._apply_worker_done.emit(commit)
            return
        self._start_worker(
            PostMergeVerifyWorker(self._service, review, cases_path, argv, timeout_seconds),
            on_ok=self._post_merge_finished,
            running="Post-merge checks are running in the main repository…",
        )

    def _post_merge_finished(self, bundle: EvidenceBundle) -> None:
        self.refresh_proposals()
        outcome = "PASSED" if bundle.passed and not bundle.cancelled else "FAILED"
        self._message_label.setText(f"Applied. Post-merge checks {outcome}.")
        self._select_proposal(self._proposal_list.currentRow())
        self._apply_worker_done.emit(bundle)

    def _reject_selected(self) -> None:
        review = self._selected_review()
        if review is None:
            self._warn("Select a proposal before rejecting it.")
            return
        try:
            self._service.reject_agent_proposal(review)
        except Exception as error:
            self._warn(str(error))
            return
        self.refresh_proposals()
        self._message_label.setText("Proposal rejected. Nothing was merged.")
        self._select_proposal(self._proposal_list.currentRow())

    def _check_blockers(self, review: ChangeReview) -> None:
        try:
            blockers = self._service.approval_blockers(review)
        except Exception:
            blockers = ("The blocker check failed; see the log for details.",)
        self._message_label.setText(" ".join(blockers))

    # ----------------------------------------------------------- threading

    def _start_worker(
        self,
        worker: (
            VerifyProposalWorker
            | ApplyProposalWorker
            | ApplyRecordedApprovalWorker
            | PostMergeVerifyWorker
        ),
        *,
        on_ok: Callable[[object], None],
        running: str,
    ) -> None:
        if self._thread is not None:
            # A previous worker is still winding down; queue this step so the
            # chain continues when its thread has fully finished instead of
            # raising a modal dialog inside the running worker's callback.
            self._pending_action = lambda: self._start_worker(worker, on_ok=on_ok, running=running)
            return
        self._pending_action = None
        self._set_busy(True, running)
        self._worker = worker
        self._thread = QThread(self)
        worker.moveToThread(self._thread)
        self._thread.started.connect(worker.run)
        worker.ok.connect(on_ok)
        worker.failed.connect(self._show_error)
        worker.ok.connect(self._finish_worker)
        worker.failed.connect(self._finish_worker)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread_finished)
        self._thread.start()

    def _finish_worker(self, _value: object) -> None:
        if self._thread is not None:
            self._thread.quit()

    def _thread_finished(self) -> None:
        self._worker = None
        self._thread = None
        self._set_busy(False, "")
        action = self._pending_action
        self._pending_action = None
        if action is not None:
            action()

    def _set_busy(self, busy: bool, message: str) -> None:
        if busy:
            self._verify_button.setEnabled(False)
            self._approve_button.setEnabled(False)
            self._apply_button.setEnabled(False)
            self._reject_button.setEnabled(False)
        else:
            self._update_action_buttons(self._selected_record())
        if message:
            self._message_label.setText(message)

    def _show_error(self, message: str) -> None:
        self._message_label.setText(f"Error: {message}")
        QMessageBox.warning(self, "Operation failed", message)

    def _warn(self, message: str) -> None:
        QMessageBox.warning(self, "Not possible yet", message)

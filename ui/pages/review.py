"""Review screen — present a proposed automation for approval."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ai.approval import approve_proposal
from ai.models import ProviderDraft
from controller.service import WorkflowService
from engine.errors import WorkflowValidationError


class ReviewPage(QWidget):
    """Clean review of a proposed workflow before approval."""

    approved = Signal()
    cancelled = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._proposal: ProviderDraft | None = None
        self._steps_list: QListWidget | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 28, 24, 24)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._title_label = QLabel("Review automation", self)
        self._title_label.setObjectName("pageTitle")
        self._title_label.setStyleSheet("font-size: 26px; font-weight: 600; color: #1d1d1d;")
        layout.addWidget(self._title_label, alignment=Qt.AlignHCenter)
        self._goal_label = QLabel("No proposal loaded.", self)
        self._goal_label.setObjectName("goalLabel")
        self._goal_label.setStyleSheet("font-size: 15px; color: #525252; margin-top: 4px;")
        layout.addWidget(self._goal_label, alignment=Qt.AlignHCenter)
        self._steps_list = QListWidget(self)
        self._steps_list.setObjectName("stepsList")
        self._steps_list.setAlternatingRowColors(True)
        self._steps_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._steps_list.addItems(self._empty_steps())
        layout.addWidget(self._steps_list, alignment=Qt.AlignHCenter)
        layout.addSpacing(12)
        self._actions_container = QFrame(self)
        actions_layout = QVBoxLayout(self._actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)
        self._edit_button = QPushButton("Edit", self)
        self._edit_button.setObjectName("secondaryActionButton")
        self._edit_button.setMinimumHeight(38)
        self._edit_button.clicked.connect(self._edit)
        self._cancel_button = QPushButton("Cancel", self)
        self._cancel_button.setObjectName("secondaryActionButton")
        self._cancel_button.setMinimumHeight(38)
        self._cancel_button.clicked.connect(self._cancel_review)
        self._approve_button = QPushButton("Approve and run", self)
        self._approve_button.setObjectName("primaryActionButton")
        self._approve_button.setMinimumHeight(38)
        self._approve_button.clicked.connect(self._approve)
        buttons_row.addWidget(self._edit_button)
        buttons_row.addWidget(self._cancel_button)
        buttons_row.addWidget(self._approve_button)
        actions_layout.addLayout(buttons_row)
        layout.addWidget(self._actions_container, alignment=Qt.AlignHCenter)

    def _empty_steps(self) -> list[str]:
        return ["No step details to review."]

    def _edit(self) -> None:
        pass

    def _cancel_review(self) -> None:
        self.cancelled.emit()

    def _approve(self) -> None:
        if self._service is None or self._proposal is None:
            return
        try:
            approved = approve_proposal(self._proposal)
            self._service.save_approved(approved)
            self.approved.emit()
        except WorkflowValidationError as error:
            QMessageBox.warning(self, "Approval error", str(error))

    def load_proposal(self, proposal: ProviderDraft | None) -> None:
        self._proposal = proposal
        self._goal_label.setText(f"Goal: {proposal.goal}" if proposal else "No proposal loaded.")
        self._steps_list.clear()
        if proposal:
            for idx, step_text in enumerate(proposal.steps, start=1):
                self._steps_list.addItem(f"{idx}. {step_text}")
        else:
            self._steps_list.addItems(self._empty_steps())

    def set_service(self, service: WorkflowService | None) -> None:
        self._service = service

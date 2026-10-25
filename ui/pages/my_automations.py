"""My Automations page — manage saved workflows."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controller.service import WorkflowService


class MyAutomationsPage(QWidget):
    """List saved workflows with name, last status, and actions."""

    opened_workflow = Signal(Path)
    workflow_selected = Signal()
    preview_requested = Signal()
    run_requested = Signal(Path)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._workflow_list: QListWidget | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 28, 24, 24)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._title_label = QLabel("My automations", self)
        self._title_label.setObjectName("pageTitle")
        self._title_label.setStyleSheet("font-size: 26px; font-weight: 600; color: #1d1d1d;")
        layout.addWidget(self._title_label)
        self._subtitle_label = QLabel(
            "Open and manage your saved workflows.",
            self,
        )
        self._subtitle_label.setObjectName("pageSubtitle")
        self._subtitle_label.setStyleSheet("font-size: 15px; color: #525252; margin-top: 2px;")
        layout.addWidget(self._subtitle_label)
        layout.addSpacing(16)
        self._workflow_list = QListWidget(self)
        self._workflow_list.setObjectName("workflowList")
        self._workflow_list.setAlternatingRowColors(True)
        self._workflow_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._workflow_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._workflow_list, alignment=Qt.AlignHCenter)
        layout.addSpacing(12)
        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)
        self._open_button = QPushButton("Open", self)
        self._open_button.setObjectName("secondaryActionButton")
        self._open_button.setMinimumHeight(38)
        self._open_button.clicked.connect(self._open_selected)
        self._preview_button = QPushButton("Preview", self)
        self._preview_button.setObjectName("secondaryActionButton")
        self._preview_button.setMinimumHeight(38)
        self._preview_button.clicked.connect(self._preview_selected)
        self._run_button = QPushButton("Run", self)
        self._run_button.setObjectName("primaryActionButton")
        self._run_button.setMinimumHeight(38)
        self._run_button.clicked.connect(self._run_selected)
        actions_row.addWidget(self._open_button)
        actions_row.addWidget(self._preview_button)
        actions_row.addWidget(self._run_button)
        actions_row.setStretchFactor(self._open_button, 1)
        actions_row.setStretchFactor(self._preview_button, 1)
        actions_row.setStretchFactor(self._run_button, 2)
        actions_container = QFrame(self)
        actions_container.setObjectName("actionsContainer")
        actions_container_layout = QVBoxLayout(actions_container)
        actions_container_layout.setContentsMargins(0, 0, 0, 0)
        actions_container_layout.setSpacing(8)
        actions_container_layout.addLayout(actions_row)
        layout.addWidget(actions_container, alignment=Qt.AlignHCenter)
        self._empty_state = self._workflow_list
        self._refresh()

    def _on_selection_changed(self) -> None:
        self.workflow_selected.emit()

    def _open_selected(self) -> None:
        item = self._workflow_list.currentItem()
        if item is None or self._service is None:
            return
        self._service.load(item.data(Qt.UserRole))
        self.opened_workflow.emit(Path(item.text()))

    def _preview_selected(self) -> None:
        item = self._workflow_list.currentItem()
        if item is None or self._service is None:
            return
        workflow = self._service.load(item.data(Qt.UserRole))
        self.preview_requested.emit()
        return self._service.preview_replay(workflow)

    def _run_selected(self) -> None:
        item = self._workflow_list.currentItem()
        if item is None or self._service is None:
            return
        workflow = self._service.load(item.data(Qt.UserRole))
        self.run_requested.emit(Path(item.text()))
        self._service.run_workflow(workflow)

    def _refresh(self) -> None:
        self._workflow_list.clear()
        if self._service is None:
            return
        for path in self._service.list_saved():
            item = QListWidgetItem(path.name)
            item.setData(Qt.UserRole, path)
            self._workflow_list.addItem(item)
        if self._workflow_list.count() == 0:
            self._empty_state.show()

    def set_service(self, service: WorkflowService | None) -> None:
        self._service = service
        self._refresh()

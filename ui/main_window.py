"""Main window for the workflow foundation milestone."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget

from controller.service import WorkflowService

WINDOW_TITLE = "Once"
STARTUP_MESSAGE = "Once is starting up…"


class MainWindow(QMainWindow):
    """Top-level window for inspecting and running a bounded local workflow."""

    def __init__(self, service: WorkflowService | None = None) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self._service = service or WorkflowService()
        self._status_label = QLabel(STARTUP_MESSAGE, self)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._run_button = QPushButton("Run demo workflow", self)
        self._run_button.clicked.connect(self._run_demo)
        layout = QVBoxLayout()
        layout.addWidget(self._status_label)
        layout.addWidget(self._run_button)
        central = QWidget(self)
        central.setLayout(layout)
        self.setCentralWidget(central)
        self.resize(640, 400)

    def _run_demo(self) -> None:
        run = self._service.run_demo()
        self._status_label.setText(f"{run.status.value}: {len(run.results)} steps recorded")

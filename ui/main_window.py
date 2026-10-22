"""Main window for Once (Step 1 placeholder)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow

WINDOW_TITLE = "Once"
STARTUP_MESSAGE = "Once is starting up…"


class MainWindow(QMainWindow):
    """Top-level window; later steps replace the placeholder with real screens."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self._startup_label = QLabel(STARTUP_MESSAGE, self)
        self._startup_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(self._startup_label)
        self.resize(640, 400)

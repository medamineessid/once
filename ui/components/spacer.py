"""FlowForge-inspired sidebar spacer.

This component provides consistent vertical spacing in the sidebar.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class Spacer(QLabel):
    """A transparent vertical spacer for sidebar layouts."""

    def __init__(self):
        super().__init__()
        self.setText("")
        self.setWordWrap(False)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(4)
        self.setMargin(0)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

"""A page body that scrolls when the window is too short for its content.

Pages used to stack everything in one fixed column, so at 960x600 Qt squeezed
the widgets into each other instead of letting the user scroll. `ScrollPage`
wraps an existing body widget: the body keeps its own layout, the scroll area
resizes it to the viewport width, and the vertical scrollbar appears only when
the content is taller than the window. Horizontal scrolling stays off so a page
never drifts sideways.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QScrollArea, QWidget


class ScrollPage(QScrollArea):
    """A frameless scroll area around one page body."""

    def __init__(self, body: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pageScrollArea")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setWidget(body)

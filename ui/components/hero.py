"""Shared hero panel and micro-label used across the Once pages.

The hero carries the product statement in the Anton display face; the
micro-label carries a real count so the panel is never decorative filler.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ui.styles import SPACING_LG, SPACING_SM, SPACING_XL


class MicroLabel(QLabel):
    """A small uppercase-style label carrying a real count."""

    def __init__(
        self,
        text: str,
        parent: QWidget | None = None,
        *,
        on_hero: bool = False,
    ) -> None:
        super().__init__(text.upper(), parent)
        self.setObjectName("heroMicro" if on_hero else "pageMicro")


class Hero(QFrame):
    """Sky-blue statement panel: micro-label plus display lines."""

    def __init__(
        self,
        micro_text: str,
        lines: tuple[tuple[str, bool], ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("heroPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_LG, SPACING_XL, SPACING_LG, SPACING_XL)
        layout.setSpacing(SPACING_SM)

        self.micro_label = MicroLabel(micro_text, self, on_hero=True)
        layout.addWidget(self.micro_label)

        self.line_labels: list[QLabel] = []
        first = True
        for text, accent in lines:
            label = QLabel(text, self)
            label.setObjectName("heroLineAccent" if accent else "heroLine")
            label.setWordWrap(False)
            if first:
                layout.addSpacing(SPACING_LG)
                first = False
            layout.addWidget(label)
            self.line_labels.append(label)

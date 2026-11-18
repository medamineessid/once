"""Non-modal banner: what happened, and what the user should do next.

A banner replaces blocking message boxes inside the shell. It shows an icon and
a short body; dismiss button. Colors are set by objectName in ui/styles.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.components.phosphor_icons import render_icon_pixmap
from ui.styles import STATUS_ERROR, STATUS_OK, STATUS_RUNNING, STATUS_WARNING

SEVERITY_INFO = "info"
SEVERITY_SUCCESS = "success"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"

#: One icon per severity: the banner never prints "Warning" as text.
_SEVERITY_ICONS = {
    SEVERITY_INFO: ("pulse", STATUS_RUNNING),
    SEVERITY_SUCCESS: ("check", STATUS_OK),
    SEVERITY_WARNING: ("warning", STATUS_WARNING),
    SEVERITY_ERROR: ("warning", STATUS_ERROR),
}


class Banner(QFrame):
    """A one-line title/body bar with a dismiss button; never modal."""

    dismissed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("banner")
        self.setProperty("severity", SEVERITY_INFO)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(12, 10, 12, 10)
        self._layout.setSpacing(12)
        self._badge = QLabel(self)
        self._badge.setObjectName("bannerIcon")
        self._title = QLabel(self)
        self._title.setObjectName("bannerTitle")
        self._body = QLabel(self)
        self._body.setObjectName("bannerBody")
        self._body.setWordWrap(True)
        self._dismiss = QPushButton("Dismiss", self)
        self._dismiss.setObjectName("bannerDismiss")
        self._dismiss.clicked.connect(self._dismiss_clicked)
        self._left = QVBoxLayout()
        self._left.setSpacing(2)
        self._left.addWidget(self._title)
        self._left.addWidget(self._body)
        self._layout.addWidget(self._badge)
        self._layout.addLayout(self._left, stretch=1)
        self._layout.addWidget(self._dismiss)
        self.hide()

    def _dismiss_clicked(self) -> None:
        self.hide()
        self.dismissed.emit()

    def show_message(
        self,
        severity: str,
        title: str,
        body: str = "",
        *,
        dismiss_button: bool = True,
    ) -> None:
        """Show a message. Severity is one of the module constants."""
        if severity not in _SEVERITY_ICONS:
            severity = SEVERITY_INFO
        self.setProperty("severity", severity)
        icon_name, colour = _SEVERITY_ICONS[severity]
        self._badge.setPixmap(
            render_icon_pixmap(icon_name, weight="Fill", logical_size=24, color=colour)
        )
        self._badge.setFixedSize(24, 24)
        self._title.setText(title)
        self._body.setText(body)
        self._body.setVisible(bool(body))
        self._dismiss.setVisible(dismiss_button)
        self.show()

    def clear(self) -> None:
        self.hide()

    @property
    def body_text(self) -> str:
        """Body text, for tests."""
        return self._body.text()

    @property
    def title_text(self) -> str:
        """Title text, for tests."""
        return self._title.text()

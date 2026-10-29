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

from ui.strings import BANNER_ERROR, BANNER_INFO, BANNER_SUCCESS, BANNER_WARNING

SEVERITY_INFO = "info"
SEVERITY_SUCCESS = "success"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"

_SEVERITY_NAMES = {
    SEVERITY_INFO: BANNER_INFO,
    SEVERITY_SUCCESS: BANNER_SUCCESS,
    SEVERITY_WARNING: BANNER_WARNING,
    SEVERITY_ERROR: BANNER_ERROR,
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
        self._badge.setObjectName("bannerBadge")
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
        if severity not in _SEVERITY_NAMES:
            severity = SEVERITY_INFO
        self.setProperty("severity", severity)
        self._badge.setText(_SEVERITY_NAMES[severity])
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

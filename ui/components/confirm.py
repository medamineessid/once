"""Inline two-step confirmation (no blocking modals inside the shell).

First click arms the button ("Run" → "Confirm run?"); a second click within
the timeout performs the action and emits ``confirmed``. Arming expires and
resets the label when the timeout lapses or when the action becomes unusable.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QPushButton

DEFAULT_CONFIRM_MS = 5000


class InlineConfirm(QPushButton):
    """A destructive-action button that arms on the first click."""

    confirmed = Signal()

    def __init__(
        self,
        label: str,
        confirm_label: str,
        *,
        confirm_timeout_ms: int = DEFAULT_CONFIRM_MS,
        parent=None,
    ) -> None:
        super().__init__(label, parent)
        self.setObjectName("confirmButton")
        self._plain_label = label
        self._confirm_label = confirm_label
        self._armed = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(max(1, confirm_timeout_ms))
        self._timer.timeout.connect(self._expire)
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self) -> None:
        if not self._armed:
            self._armed = True
            self.setText(self._confirm_label)
            self.setProperty("armed", True)
            self._repolish()
            self._timer.start()
            return
        self._timer.stop()
        self.reset()
        self.confirmed.emit()

    def _expire(self) -> None:
        self._armed = False
        self.setProperty("armed", False)
        self._repolish()
        self.setText(self._plain_label)

    def _repolish(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)

    def arm_for_test(self) -> None:
        """Arm once without a click, for tests only.

        Behaves exactly like the real arming click, including starting the
        expiry timer, so tests can observe the timeout path deterministically.
        """
        self._armed = True
        self.setText(self._confirm_label)
        self.setProperty("armed", True)
        self._repolish()
        self._timer.start()

    def is_armed(self) -> bool:
        """True while the button waits for the confirming click."""
        return self._armed

    def reset(self, label: str | None = None) -> None:
        """Drop the armed state and restore the plain label."""
        self._timer.stop()
        self._armed = False
        self.setProperty("armed", False)
        self._repolish()
        if label is not None:
            self._plain_label = label
            self.setText(label)
        elif self.text() != self._plain_label:
            self.setText(self._plain_label)

    def set_running(self, running: bool, running_label: str = "Running…") -> None:
        """Show the busy state and disable further clicks."""
        self.reset()
        if running:
            self.setText(running_label)
            self.setEnabled(False)
        else:
            self.setEnabled(True)

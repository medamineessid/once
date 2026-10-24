"""Guided editor for the acceptance checker configuration.

The dialog writes only after `save_verifier_config` validated the document
with the exact same rules a restart applies; a rejected save leaves the
existing configuration untouched and shows a plain-language reason.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from controller.verifier_config import (
    VerifierConfig,
    save_verifier_config,
)

ARGUMENTS_PLACEHOLDER = "One argument per line, exactly one {input}."


class VerifierConfigDialog(QDialog):
    """Collect and persist the acceptance checker configuration."""

    def __init__(
        self,
        app_data_dir: Path,
        current: VerifierConfig | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._app_data_dir = app_data_dir
        self.saved: VerifierConfig | None = None

        self._cases_path = QLineEdit(self)
        self._arguments = QPlainTextEdit(self)
        self._arguments.setPlaceholderText(ARGUMENTS_PLACEHOLDER)
        self._arguments.setMaximumHeight(100)
        self._timeout = QDoubleSpinBox(self)
        self._timeout.setRange(1.0, 300.0)
        self._timeout.setDecimals(1)
        self._timeout.setSingleStep(5.0)
        self._worktree_root = QLineEdit(self)

        cases_row = QHBoxLayout()
        cases_row.addWidget(self._cases_path)
        browse_cases = QPushButton("Browse…", self)
        browse_cases.clicked.connect(self._browse_cases)
        cases_row.addWidget(browse_cases)
        root_row = QHBoxLayout()
        root_row.addWidget(self._worktree_root)
        browse_root = QPushButton("Browse…", self)
        browse_root.clicked.connect(self._browse_worktree_root)
        root_row.addWidget(browse_root)

        form = QFormLayout()
        form.addRow("Acceptance cases file", cases_row)
        form.addRow("Checker command line", self._arguments)
        form.addRow("Timeout per case (seconds)", self._timeout)
        form.addRow("Worktree directory for reruns", root_row)

        save_button = QPushButton("Save configuration", self)
        save_button.setObjectName("saveVerifierConfigButton")
        save_button.clicked.connect(self.apply_config)
        cancel_button = QPushButton("Cancel", self)
        cancel_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addWidget(save_button)
        buttons.addWidget(cancel_button)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons)
        self.setLayout(layout)
        self.setWindowTitle("Acceptance checker configuration")
        if current is not None:
            self._cases_path.setText(str(current.cases_path))
            self._arguments.setPlainText("\n".join(current.argv))
            self._timeout.setValue(current.timeout_seconds)
            self._worktree_root.setText(str(current.worktree_root))

    def arguments(self) -> tuple[str, ...]:
        """Return the checker argv text, one non-empty argument per line."""
        return tuple(
            line.strip() for line in self._arguments.toPlainText().splitlines() if line.strip()
        )

    def _browse_cases(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Acceptance cases file")
        if path:
            self._cases_path.setText(path)

    def _browse_worktree_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Worktree directory for reruns")
        if path:
            self._worktree_root.setText(path)

    def apply_config(self) -> VerifierConfig | None:
        """Validate the fields and write the configuration; None on refusal."""
        try:
            self.saved = save_verifier_config(
                self._app_data_dir,
                self._cases_path.text().strip(),
                list(self.arguments()),
                self._timeout.value(),
                self._worktree_root.text().strip(),
            )
        except Exception as error:  # show the exact validation problem
            QMessageBox.warning(self, "Configuration not saved", str(error))
            return None
        self.accept()
        return self.saved

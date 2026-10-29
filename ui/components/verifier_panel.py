"""Inline acceptance-checker editor shown inside the Settings page.

Same validation and persistence as the old dialog (`ui/verifier_dialog.py`,
kept for the legacy window): writes happen only through
``controller.verifier_config.save_verifier_config`` after the exact restart
validation passes, and a rejected edit never touches the stored file.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controller.verifier_config import VerifierConfig, save_verifier_config
from engine.errors import OnceError, WorkflowValidationError

ARGUMENTS_PLACEHOLDER = "One argument per line, exactly one {input}."


class VerifierEditorPanel(QFrame):
    """Collect, validate, and persist the checker configuration inline."""

    saved = Signal(object)

    def __init__(
        self,
        app_data_dir: Path | None,
        current: VerifierConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("verifierEditorPanel")
        self._app_data_dir = app_data_dir

        self._error_label = QLabel("", self)
        self._error_label.setObjectName("panelErrorLabel")
        self._error_label.setWordWrap(True)
        self._error_label.hide()

        self._cases_path = QLineEdit(self)
        self._arguments = QPlainTextEdit(self)
        self._arguments.setPlaceholderText(ARGUMENTS_PLACEHOLDER)
        self._arguments.setObjectName("inputBase")
        self._arguments.setMaximumHeight(100)
        self._timeout = QDoubleSpinBox(self)
        self._timeout.setRange(1.0, 300.0)
        self._timeout.setDecimals(1)
        self._timeout.setSingleStep(5.0)
        self._worktree_root = QLineEdit(self)

        cases_row = QHBoxLayout()
        cases_row.addWidget(self._cases_path, stretch=1)
        browse_cases = QPushButton("Browse…", self)
        browse_cases.setObjectName("secondaryActionButton")
        browse_cases.clicked.connect(self._browse_cases)
        cases_row.addWidget(browse_cases)
        root_row = QHBoxLayout()
        root_row.addWidget(self._worktree_root, stretch=1)
        browse_root = QPushButton("Browse…", self)
        browse_root.setObjectName("secondaryActionButton")
        browse_root.clicked.connect(self._browse_worktree_root)
        root_row.addWidget(browse_root)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.addRow("Acceptance cases file", cases_row)
        form.addRow("Checker command line", self._arguments)
        form.addRow("Timeout per case (seconds)", self._timeout)
        form.addRow("Worktree directory for reruns", root_row)

        self._save_button = QPushButton("Save configuration", self)
        self._save_button.setObjectName("saveVerifierConfigButton")
        self._save_button.clicked.connect(self._on_save_clicked)
        close_button = QPushButton("Close", self)
        close_button.setObjectName("ghostButton")
        close_button.clicked.connect(self.hide)

        buttons = QHBoxLayout()
        buttons.addWidget(self._save_button)
        buttons.addWidget(close_button)
        buttons.addStretch(1)
        buttons.setContentsMargins(0, 0, 0, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(self._error_label)
        layout.addLayout(form)
        layout.addLayout(buttons)
        self.hide()
        if current is not None:
            self.reconfigure(app_data_dir, current)

    # ------------------------------------------------------------- configure

    def reconfigure(self, app_data_dir: Path | None, current: VerifierConfig | None = None) -> None:
        """Point the editor at a data folder and fill the current values."""
        self.hide_error()
        self._app_data_dir = app_data_dir
        if current is not None:
            self._cases_path.setText(str(current.cases_path))
            self._arguments.setPlainText("\n".join(current.argv))
            self._timeout.setValue(current.timeout_seconds)
            self._worktree_root.setText(str(current.worktree_root))

    def focus_first_field(self) -> None:
        """Move keyboard focus to the first editable field."""
        self._cases_path.setFocus()

    # ------------------------------------------------------------ save logic

    def arguments(self) -> tuple[str, ...]:
        """Return the checker argv text, one non-empty argument per line."""
        return tuple(
            line.strip() for line in self._arguments.toPlainText().splitlines() if line.strip()
        )

    def hide_error(self) -> None:
        self._error_label.clear()
        self._error_label.hide()

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()

    def _on_save_clicked(self) -> None:
        config = self.apply_config()
        if config is not None:
            self.saved.emit(config)

    def apply_config(self) -> VerifierConfig | None:
        """Validate the fields and write the configuration; None on refusal."""
        self.hide_error()
        if self._app_data_dir is None:
            self._show_error("No data folder is configured, so this cannot be saved yet.")
            return None
        try:
            config = save_verifier_config(
                self._app_data_dir,
                self._cases_path.text().strip(),
                list(self.arguments()),
                self._timeout.value(),
                self._worktree_root.text().strip(),
            )
        except (WorkflowValidationError, OnceError, OSError) as error:
            # Show the exact validation problem; never save a partial file.
            self._show_error(str(error))
            return None
        return config

    # -------------------------------------------------------------- browsing

    def _browse_cases(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Acceptance cases file")
        if path:
            self._cases_path.setText(path)

    def _browse_worktree_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Worktree directory for reruns")
        if path:
            self._worktree_root.setText(path)

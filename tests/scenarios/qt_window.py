"""A real (offscreen) Qt window whose layout changes between variants.

Every scenario builds a genuine widget tree: tabs whose "+" moves as tabs are
added, a list that reorders, a dialog that sometimes exists, a control that
appears after a delay, a translated label, and a destructive Delete next to a
harmless one. The adapter reads the widgets the way a UI Automation adapter
would (role, name, object name, containing group, position) and clicks them
with ``QTest``.

Each widget carries a ``lab_key`` property. It is the lab's internal handle for
truth and click routing and is never exposed as a clue.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from engine.resolve import Candidate, Clue, ClueKind

LAST_ACTION_PROPERTY = "lab_last_action"
LAB_KEY_PROPERTY = "lab_key"
TYPE_PROPERTY = "lab_type"


FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"


def ensure_application() -> QApplication:
    """Return the single QApplication, using the app's own font.

    This environment can expose zero system font families, in which case every
    label renders as an empty box and a screenshot proves nothing. Registering
    the bundled Inter face keeps the captures readable.
    """
    from PySide6.QtGui import QFont, QFontDatabase

    instance = QApplication.instance()
    if isinstance(instance, QApplication):
        return instance
    app = QApplication([])
    font_path = FONT_DIR / "Inter-Regular.ttf"
    if font_path.is_file():
        family = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(family)
        if families:
            app.setFont(QFont(families[0], 10))
    return app


def _mark(widget: QWidget, key: str, kind: str) -> QWidget:
    widget.setProperty(LAB_KEY_PROPERTY, key)
    widget.setProperty(TYPE_PROPERTY, kind)
    return widget


def _record_click(window: QWidget, key: str) -> None:
    window.setProperty(LAST_ACTION_PROPERTY, key)


def build_tabs_window(
    *, tabs: int, plus_in_strip: bool, plus_outside: bool, twins: bool
) -> QWidget:
    """A tab strip whose "+" position depends on how many tabs exist."""
    window = QWidget()
    window.setAccessibleName("Invoices")
    layout = QVBoxLayout(window)

    strip = QWidget()
    strip.setAccessibleName("Tabs")
    strip_layout = QHBoxLayout(strip)
    for index in range(1, tabs + 1):
        tab = QToolButton()
        tab.setText(f"Tab {index}")
        _mark(tab, f"tab-{index}", "tab")
        tab.clicked.connect(lambda _checked=False, key=f"tab-{index}": _record_click(window, key))
        strip_layout.addWidget(tab)
    if plus_in_strip:
        plus = QPushButton("+")
        plus.setObjectName("new-tab")
        _mark(plus, "new-tab", "plus")
        plus.clicked.connect(lambda: _record_click(window, "new-tab"))
        strip_layout.addWidget(plus)
    if twins:
        twin = QPushButton("+")
        twin.setObjectName("new-tab")
        _mark(twin, "new-tab-twin", "plus")
        twin.clicked.connect(lambda: _record_click(window, "new-tab-twin"))
        strip_layout.addWidget(twin)
    # Keep the buttons at their natural width so the strip reads like a tab bar.
    strip_layout.addStretch(1)
    layout.addWidget(strip)

    if plus_outside:
        toolbar = QWidget()
        toolbar.setAccessibleName("Toolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        outside = QPushButton("+")
        outside.setObjectName("new-tab")
        _mark(outside, "new-tab-toolbar", "plus")
        outside.clicked.connect(lambda: _record_click(window, "new-tab-toolbar"))
        toolbar_layout.addWidget(outside)
        toolbar_layout.addStretch(1)
        layout.addWidget(toolbar)

    layout.addWidget(QLabel("Invoices"))
    layout.addStretch(1)
    window.resize(640, 420)
    return window


def build_list_window(*, items: tuple[tuple[str, str], ...]) -> QWidget:
    """A list whose rows reorder and whose text can repeat."""
    window = QWidget()
    window.setAccessibleName("Results")
    layout = QVBoxLayout(window)
    listing = QListWidget()
    listing.setAccessibleName("Results")
    for key, text in items:
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, key)
        listing.addItem(item)
    listing.itemClicked.connect(
        lambda item: _record_click(window, str(item.data(Qt.ItemDataRole.UserRole)))
    )
    layout.addWidget(listing)
    layout.addStretch(1)
    window.resize(520, 380)
    return window


def build_dialog_window(*, dialog: bool, confirm_key: str = "confirm-save") -> QWidget:
    """A window where a confirmation dialog sometimes appears."""
    window = QWidget()
    window.setAccessibleName("Invoice editor")
    layout = QVBoxLayout(window)
    layout.addWidget(QLabel("Invoice 1042"))

    if dialog:
        panel = QDialog(window)
        panel.setAccessibleName("Confirm changes")
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(QLabel("Save your changes?"))
        confirm = QPushButton("Confirm")
        _mark(confirm, confirm_key, "confirm")
        confirm.clicked.connect(lambda: _record_click(window, confirm_key))
        panel_layout.addWidget(confirm)
        panel.setVisible(True)
        layout.addWidget(panel)

    layout.addStretch(1)
    window.resize(560, 400)
    return window


def build_delete_window(*, row_delete: bool, filter_delete: bool, twins: bool) -> QWidget:
    """A destructive Delete button next to a harmless one."""
    window = QWidget()
    window.setAccessibleName("Invoices")
    layout = QVBoxLayout(window)

    row = QWidget()
    row.setAccessibleName("Invoice 1042")
    row_layout = QHBoxLayout(row)
    row_layout.addWidget(QLabel("Invoice 1042"))
    if row_delete:
        delete_row = QPushButton("Delete")
        _mark(delete_row, "delete-row", "delete")
        delete_row.clicked.connect(lambda: _record_click(window, "delete-row"))
        row_layout.addWidget(delete_row)
    if twins:
        delete_twin = QPushButton("Delete")
        _mark(delete_twin, "delete-row-twin", "delete")
        delete_twin.clicked.connect(lambda: _record_click(window, "delete-row-twin"))
        row_layout.addWidget(delete_twin)
    row_layout.addStretch(1)
    layout.addWidget(row)

    if filter_delete:
        filters = QWidget()
        filters.setAccessibleName("Filters")
        filters_layout = QHBoxLayout(filters)
        filters_layout.addWidget(QLabel("Shift filter"))
        delete_filter = QPushButton("Delete")
        _mark(delete_filter, "delete-filter", "delete")
        delete_filter.clicked.connect(lambda: _record_click(window, "delete-filter"))
        filters_layout.addWidget(delete_filter)
        filters_layout.addStretch(1)
        layout.addWidget(filters)

    layout.addStretch(1)
    window.resize(600, 360)
    return window


def build_edit_window(
    *,
    text: str,
    object_name: str,
    rows: int,
    delayed_ms: int,
    row_label: str = "Invoice 1042",
) -> QWidget:
    """An edit button, optionally translated, duplicated or shown late."""
    window = QWidget()
    window.setAccessibleName("Invoice 1042")
    layout = QVBoxLayout(window)
    holder = QWidget()
    holder_layout = QVBoxLayout(holder)
    layout.addWidget(holder)
    layout.addStretch(1)
    window.resize(600, 400)

    def add_rows() -> None:
        for index in range(rows):
            row = QWidget()
            row.setAccessibleName(row_label)
            row_layout = QHBoxLayout(row)
            row_layout.addWidget(QLabel(row_label))
            button = QPushButton(text)
            button.setObjectName(object_name)
            key = f"edit-{index + 1}"
            _mark(button, key, "edit")
            button.clicked.connect(lambda _checked=False, k=key: _record_click(window, k))
            row_layout.addWidget(button)
            row_layout.addStretch(1)
            holder_layout.addWidget(row)

    if delayed_ms > 0:
        from PySide6.QtCore import QTimer

        QTimer.singleShot(delayed_ms, add_rows)
    else:
        add_rows()
    return window


class QtAdapter:
    """Adapter that turns a widget tree into candidates and clicks them."""

    surface_kind = "DESKTOP"

    def __init__(
        self,
        builder: Callable[[str], QWidget],
        truth: dict[str, str | None],
        *,
        settle_ms: int = 0,
    ) -> None:
        self._builder = builder
        self._truth = truth
        self._settle_ms = settle_ms
        self._window: QWidget | None = None
        self._variant = "A"

    @property
    def window(self) -> QWidget:
        assert self._window is not None, "prepare() must be called first"
        return self._window

    def prepare(self, variant: str) -> None:
        """Build and show the variant window, then let bounded timers settle."""
        ensure_application()
        self.close()
        self._variant = variant
        self._window = self._builder(variant)
        self._window.show()
        if self._settle_ms:
            # A bounded wait for the delayed control, not a fixed sleep in the
            # resolver: the adapter owns waiting, the resolver never sleeps.
            QTest.qWait(self._settle_ms)

    def snapshot(self, variant: str, row_rule: str | None = None) -> tuple[Candidate, ...]:
        del variant, row_rule
        window = self.window
        candidates: list[Candidate] = []
        role_counts: dict[str, int] = {}

        for widget in window.findChildren(QWidget):
            if isinstance(widget, QListWidget):
                container = widget.accessibleName() or None
                for index in range(widget.count()):
                    item = widget.item(index)
                    rect = widget.visualItemRect(item)
                    point = widget.viewport().mapToGlobal(rect.center())
                    candidates.append(
                        Candidate(
                            candidate_id=str(item.data(Qt.ItemDataRole.UserRole)),
                            clues=_clues(
                                role="list item",
                                name=item.text(),
                                object_name="",
                                container=container,
                                ordinal=index,
                            ),
                            ordinal=index,
                            enabled=True,
                            position=(point.x(), point.y()),
                        )
                    )
                continue
            key = widget.property(LAB_KEY_PROPERTY)
            if not isinstance(key, str) or not isinstance(widget, QPushButton | QToolButton):
                continue
            ordinal = role_counts.get("button", 0)
            role_counts["button"] = ordinal + 1
            point = widget.mapToGlobal(widget.rect().center())
            candidates.append(
                Candidate(
                    candidate_id=key,
                    clues=_clues(
                        role="button",
                        name=widget.text(),
                        object_name=widget.objectName(),
                        container=_container_label(widget),
                        ordinal=ordinal,
                    ),
                    ordinal=ordinal,
                    enabled=widget.isEnabled(),
                    position=(point.x(), point.y()),
                )
            )
        return tuple(candidates)

    def truth_id(self, variant: str) -> str | None:
        return self._truth.get(variant)

    def perform(self, candidate: Candidate) -> None:
        """Click the resolved widget (or select the resolved list row)."""
        for widget in self.window.findChildren(QWidget):
            if isinstance(widget, QPushButton | QToolButton) and (
                widget.property(LAB_KEY_PROPERTY) == candidate.candidate_id
            ):
                QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
                QApplication.processEvents()
                return
            if isinstance(widget, QListWidget):
                for index in range(widget.count()):
                    item = widget.item(index)
                    if str(item.data(Qt.ItemDataRole.UserRole)) == candidate.candidate_id:
                        widget.setCurrentRow(index)
                        _record_click(self.window, candidate.candidate_id)
                        QApplication.processEvents()
                        return
        raise AssertionError(f"candidate {candidate.candidate_id} is not in the window")

    def observe(self) -> str:
        value = self.window.property(LAST_ACTION_PROPERTY)
        return f"action={value or 'none'}"

    def save_screenshot(self, path: Path) -> None:
        """Save this window only (never the desktop) for human inspection."""
        ensure_application()
        QApplication.processEvents()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.window.grab().save(str(path))

    def close(self) -> None:
        window, self._window = self._window, None
        if window is not None:
            window.close()
            window.deleteLater()
            QApplication.processEvents()


def _container_label(widget: QWidget) -> str | None:
    """The nearest ancestor group's accessible name, as an adapter would read it."""
    parent = widget.parentWidget()
    while parent is not None:
        name = parent.accessibleName()
        if name:
            return name
        parent = parent.parentWidget()
    return None


def _clues(
    *,
    role: str,
    name: str,
    object_name: str,
    container: str | None,
    ordinal: int,
) -> tuple[Clue, ...]:
    clues: list[Clue] = []
    if object_name:
        clues.append(Clue(ClueKind.AUTOMATION_ID, object_name, "automation_id"))
    clues.append(Clue(ClueKind.ROLE, role, "role"))
    if name:
        clues.append(Clue(ClueKind.NAME, name, "name"))
    if container:
        clues.append(Clue(ClueKind.CONTAINER_TEXT, container, "container"))
    clues.append(Clue(ClueKind.ORDINAL, str(ordinal), "ordinal"))
    return tuple(clues)

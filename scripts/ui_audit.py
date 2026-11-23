"""Audit every page and state of Once for the six defect classes.

    python scripts/ui_audit.py                 # 100/125/150%, three window sizes
    python scripts/ui_audit.py --scale 125     # one scale (internal use)
    python scripts/ui_audit.py --offscreen     # the CI subset

Checks:

a. a visible widget leaves its parent or its scroll viewport;
b. two visible widgets overlap that are not ancestor/descendant;
c. text is clipped by its widget;
d. a button's text does not contrast 3:1 with its own background, or an
   outlined button has no visible border on one of its four edges;
e. an element required by ``scripts/ui_spec.py`` is missing, hidden, zero-size
   or outside the window;
f. hovering or pressing a button changes its geometry, or a spec rule about
   layout geometry does not hold.

The script builds its own synthetic data folder, never the real one, and writes
app-window PNGs plus a JSON report. Exit status is non-zero when it finds
anything.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

SCALES = (100, 125, 150)
SIZES = ((960, 600), (1280, 800), (1920, 1020))
PAGES = ("home", "automations", "activity", "settings", "details")
STATES = ("banner", "permission_panel", "delete_dialog", "parameter_dialog", "running")


@dataclass
class Finding:
    """One failed check, with everything needed to reproduce it."""

    check: str
    page: str
    state: str
    scale: int
    size: str
    widget: str
    detail: str


# --------------------------------------------------------------- geometry


def rect_in_window(widget, window) -> "QRect":
    """The widget's rectangle in window coordinates."""
    from PySide6.QtCore import QPoint, QRect

    return QRect(widget.mapTo(window, QPoint(0, 0)), widget.size())


def is_visible(widget) -> bool:
    """True when the widget would be visible once its window is mapped.

    ``isVisibleTo`` is deliberate: an audit may run before the window manager
    maps a window (offscreen CI), and ``isVisible`` would then hide every child.
    """
    return widget.isVisibleTo(widget.window()) and widget.width() > 0 and widget.height() > 0


def viewport_rect(widget, window):
    """The scroll viewport rectangle when ``widget`` sits inside one, else None."""
    from PySide6.QtWidgets import QAbstractScrollArea

    parent = widget.parentWidget()
    while parent is not None and parent is not window:
        if isinstance(parent, QAbstractScrollArea):
            return rect_in_window(parent.viewport(), window)
        parent = parent.parentWidget()
    return None


def _labelled(widget) -> bool:
    """True for widgets worth checking individually."""
    from PySide6.QtWidgets import QAbstractButton, QLabel

    if widget.objectName():
        return True
    if isinstance(widget, (QLabel, QAbstractButton)) and widget.text():
        return True
    return False


def _atomic(widget) -> bool:
    """True for leaf widgets that must not overlap their siblings."""
    from PySide6.QtWidgets import QAbstractButton, QLabel, QWidget

    if not is_visible(widget):
        return False
    if not (widget.objectName() or isinstance(widget, (QLabel, QAbstractButton))):
        return False
    return not any(is_visible(child) for child in widget.findChildren(QWidget))


def contrast_ratio(first, second) -> float:
    """WCAG contrast ratio between two RGB colours."""

    def luminance(colour) -> float:
        channels = []
        for value in (colour.redF(), colour.greenF(), colour.blueF()):
            channels.append(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4)
        red, green, blue = channels
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue

    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def dominant_colours(widget, limit: int = 3):
    """The most common colours inside the widget's own rendering."""
    from PySide6.QtGui import QColor

    image = widget.grab().toImage()
    counts: Counter[tuple[int, int, int]] = Counter()
    step_y = max(1, image.height() // 32)
    step_x = max(1, image.width() // 32)
    for y in range(0, image.height(), step_y):
        for x in range(0, image.width(), step_x):
            colour = image.pixelColor(x, y)
            counts[(colour.red(), colour.green(), colour.blue())] += 1
    return [(QColor(*rgb), count) for rgb, count in counts.most_common(limit)]


def button_measurements(widget):
    """(background, strongest contrast colour, ratio) for one button."""
    colours = dominant_colours(widget, limit=6)
    if not colours:
        return None
    background = colours[0][0]
    best = None
    for colour, _count in colours[1:]:
        ratio = contrast_ratio(background, colour)
        if best is None or ratio > best[1]:
            best = (colour, ratio)
    if best is None:
        return background, background, 1.0
    return background, best[0], best[1]


def edge_has_border(widget, edge: str, background, tolerance: int = 8) -> bool:
    """True when at least one pixel on ``edge`` differs from the fill colour."""
    image = widget.grab().toImage()
    width, height = image.width(), image.height()
    if width < 3 or height < 3:
        return False
    if edge in ("top", "bottom"):
        y = 0 if edge == "top" else height - 1
        pixels = [image.pixelColor(x, y) for x in range(1, width - 1)]
    else:
        x = 0 if edge == "left" else width - 1
        pixels = [image.pixelColor(x, y) for y in range(1, height - 1)]
    for colour in pixels:
        if (
            abs(colour.red() - background.red()) > tolerance
            or abs(colour.green() - background.green()) > tolerance
            or abs(colour.blue() - background.blue()) > tolerance
        ):
            return True
    return False


# ----------------------------------------------------------------- checks


def check_containment(window, page, state, scale, size, findings) -> None:
    """(a) nothing visible may leave the window or its scroll viewport."""
    from PySide6.QtCore import QRect
    from PySide6.QtWidgets import QWidget

    window_rect = QRect(0, 0, window.width(), window.height())
    for widget in window.findChildren(QWidget):
        if not is_visible(widget) or not _labelled(widget):
            continue
        bounds = viewport_rect(widget, window) or window_rect
        rect = rect_in_window(widget, window)
        parent = widget.parentWidget()
        inside_parent = True
        if bounds is window_rect and parent is not None and parent is not window:
            inside_parent = rect_in_window(parent, window).contains(rect)
        if bounds.contains(rect) and inside_parent:
            continue
        findings.append(
            Finding(
                "a-contains",
                page,
                state,
                scale,
                size,
                widget.objectName() or type(widget).__name__,
                f"rect {rect.getRect()} leaves {bounds.getRect()}",
            )
        )


def check_overlap(window, page, state, scale, size, findings, allowlist=frozenset()) -> None:
    """(b) two visible leaf widgets must not overlap unless related."""
    from PySide6.QtCore import QRect
    from PySide6.QtWidgets import QWidget

    candidates = [widget for widget in window.findChildren(QWidget) if _atomic(widget)]
    window_rect = QRect(0, 0, window.width(), window.height())
    for first, second in combinations(candidates, 2):
        if first.isAncestorOf(second) or second.isAncestorOf(first):
            continue
        first_rect = rect_in_window(first, window).intersected(window_rect)
        second_rect = rect_in_window(second, window).intersected(window_rect)
        shared = first_rect.intersected(second_rect)
        if shared.width() <= 2 or shared.height() <= 2:
            continue
        key = (first.objectName(), second.objectName())
        if key in allowlist or key[::-1] in allowlist:
            continue
        findings.append(
            Finding(
                "b-overlap",
                page,
                state,
                scale,
                size,
                f"{key[0]}|{key[1]}",
                f"overlap {shared.width()}x{shared.height()}",
            )
        )


def check_text_clipped(window, page, state, scale, size, findings, allowlist=frozenset()) -> None:
    """(c) text must fit inside the widget that draws it."""
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtWidgets import QAbstractButton, QLabel, QWidget

    for widget in window.findChildren(QWidget):
        if not is_visible(widget):
            continue
        if widget.objectName() in allowlist:
            continue
        if isinstance(widget, QLabel) and widget.text():
            metrics = widget.fontMetrics()
            flags = int(widget.alignment())
            if widget.wordWrap():
                flags |= int(Qt.TextFlag.TextWordWrap)
            bounds = metrics.boundingRect(QRect(0, 0, widget.width(), 10000), flags, widget.text())
            if bounds.height() > widget.height() + 2 or (
                not widget.wordWrap() and bounds.width() > widget.width() + 2
            ):
                findings.append(
                    Finding(
                        "c-clipped",
                        page,
                        state,
                        scale,
                        size,
                        widget.objectName() or "QLabel",
                        f"text needs {bounds.width()}x{bounds.height()} in "
                        f"{widget.width()}x{widget.height()}",
                    )
                )
        elif isinstance(widget, QAbstractButton) and widget.text():
            metrics = widget.fontMetrics()
            needed = metrics.boundingRect(widget.text()).width()
            room = widget.contentsRect().width()
            if needed > room + 2:
                findings.append(
                    Finding(
                        "c-clipped",
                        page,
                        state,
                        scale,
                        size,
                        widget.objectName() or type(widget).__name__,
                        f"text needs {needed}px, button offers {room}px",
                    )
                )


def check_buttons(window, page, state, scale, size, findings) -> None:
    """(d) every button must read clearly and keep its border."""
    from PySide6.QtWidgets import QAbstractButton, QWidget

    outlined = {"secondary", "outline", "ghost"}
    for widget in window.findChildren(QWidget):
        if not isinstance(widget, QAbstractButton) or not is_visible(widget):
            continue
        if not widget.text():
            continue
        name = widget.objectName() or type(widget).__name__
        measurements = button_measurements(widget)
        if measurements is None:
            continue
        background, _text, ratio = measurements
        if ratio < 3.0:
            findings.append(
                Finding(
                    "d-contrast",
                    page,
                    state,
                    scale,
                    size,
                    name,
                    f"contrast {ratio:.2f}:1 against its own background",
                )
            )
        variant = str(widget.property("variant") or "")
        if variant in outlined:
            for edge in ("top", "bottom", "left", "right"):
                if not edge_has_border(widget, edge, background):
                    findings.append(
                        Finding(
                            "d-border",
                            page,
                            state,
                            scale,
                            size,
                            name,
                            f"no visible border on the {edge} edge",
                        )
                    )


def check_required(root, page, state, scale, size, findings) -> None:
    """(e) every element the spec requires must exist, be visible and be placed."""
    from PySide6.QtCore import QRect
    from PySide6.QtWidgets import QWidget

    from ui_spec import REQUIRED

    window_rect = QRect(0, 0, root.width(), root.height())
    for name in REQUIRED.get(page, ()):
        widget = root.findChild(QWidget, name)
        if widget is None:
            findings.append(Finding("e-required", page, state, scale, size, name, "missing"))
            continue
        if not widget.isVisibleTo(root) or widget.width() <= 0 or widget.height() <= 0:
            findings.append(
                Finding("e-required", page, state, scale, size, name, "hidden or zero-size")
            )
            continue
        rect = rect_in_window(widget, root)
        if not window_rect.contains(rect):
            findings.append(
                Finding(
                    "e-required",
                    page,
                    state,
                    scale,
                    size,
                    name,
                    f"rect {rect.getRect()} is off-screen",
                )
            )
    if page == "delete_dialog":
        for name in ("confirmDeleteButton", "cancelDeleteButton"):
            widget = root.findChild(QWidget, name)
            if widget is None:
                continue
            variant = str(widget.property("variant") or "")
            wanted = "destructive" if name == "confirmDeleteButton" else "secondary"
            if variant != wanted:
                findings.append(
                    Finding(
                        "e-required",
                        page,
                        state,
                        scale,
                        size,
                        name,
                        f'variant is "{variant}", spec requires "{wanted}"',
                    )
                )


def check_animation(window, page, state, scale, size, findings, app) -> None:
    """(f) hover and press may repaint, never move or resize the control."""
    from PySide6.QtCore import QEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QAbstractButton, QApplication, QWidget

    for widget in window.findChildren(QWidget):
        if not isinstance(widget, QAbstractButton) or not is_visible(widget):
            continue
        if not widget.isEnabled():
            continue
        name = widget.objectName() or type(widget).__name__
        base = rect_in_window(widget, window)
        QApplication.sendEvent(widget, QEvent(QEvent.Type.Enter))
        app.processEvents()
        QTest.qWait(50)
        early = rect_in_window(widget, window)
        QTest.qWait(70)
        late = rect_in_window(widget, window)
        # setDown draws the pressed state without emitting clicked, so a button
        # that opens a modal dialog cannot hang the audit.
        widget.setDown(True)
        app.processEvents()
        QTest.qWait(50)
        pressed = rect_in_window(widget, window)
        widget.setDown(False)
        QApplication.sendEvent(widget, QEvent(QEvent.Type.Leave))
        app.processEvents()
        for label, rect in (("hover-50%", early), ("hover-100%", late), ("press", pressed)):
            if rect != base:
                findings.append(
                    Finding(
                        "f-animation",
                        page,
                        state,
                        scale,
                        size,
                        name,
                        f"{label} moved/resized {base.getRect()} -> {rect.getRect()}",
                    )
                )
                break


# ------------------------------------------------------------------ rules


def _rect(window, widget):
    return rect_in_window(widget, window)


def _gap(upper, lower) -> float:
    return float(lower.top() - upper.bottom())


def rule_header_gaps(window, page) -> list[tuple[str, str]]:
    """D7: 8-12px between micro label, title and subtitle."""
    from PySide6.QtWidgets import QLabel

    from ui_spec import HEADER_GAP

    labels = [window.findChild(QLabel, name) for name in ("pageMicro", "pageTitle", "pageSubtitle")]
    if any(label is None or not label.isVisibleTo(window) or not label.text() for label in labels):
        return []
    micro, title, subtitle = (_rect(window, label) for label in labels)
    problems = []
    for upper, lower, label in (
        (micro, title, "micro->title"),
        (title, subtitle, "title->subtitle"),
    ):
        gap = _gap(upper, lower)
        if not HEADER_GAP.holds(gap):
            problems.append(("header_gaps", f"{label} gap is {gap:.1f}px, spec is 8-12px"))
    return problems


def _label_class():
    from PySide6.QtWidgets import QLabel

    return QLabel


def rule_sidebar_equal_width(window, page) -> list[tuple[str, str]]:
    """D8: all four sidebar items share one width and one left edge."""
    from ui_spec import REQUIRED

    rects = []
    for name in REQUIRED["home"][:4]:
        widget = window.findChild(type(window), name)
        if widget is None:
            return []
        rects.append((name, _rect(window, widget)))
    widths = {rect.width() for _name, rect in rects}
    lefts = {rect.left() for _name, rect in rects}
    problems = []
    if len(widths) > 1:
        problems.append(("sidebar_equal_width", f"widths differ: {sorted(widths)}"))
    if len(lefts) > 1:
        problems.append(("sidebar_equal_width", f"left edges differ: {sorted(lefts)}"))
    return problems


def rule_sidebar_focus_not_pill(window, page) -> list[tuple[str, str]]:
    """D8: keyboard focus may draw an outline, never the active pill fill."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QWidget

    from ui_spec import REQUIRED

    problems = []
    for name in REQUIRED["home"][:4]:
        widget = window.findChild(QWidget, name)
        if widget is None or not is_visible(widget):
            continue
        if widget.isChecked():
            continue
        widget.clearFocus()
        window.activateWindow()
        window.setFocus()
        window.repaint()
        before = button_measurements(widget)
        widget.setFocus(Qt.FocusReason.TabFocusReason)
        window.repaint()
        after = button_measurements(widget)
        if before is None or after is None:
            continue
        delta = sum(
            abs(a - b) for a, b in zip(before[0].getRgb()[:3], after[0].getRgb()[:3], strict=True)
        )
        if delta > 30:
            problems.append(
                (
                    "sidebar_focus_not_pill",
                    f"{name} background changes by {delta} on keyboard focus",
                )
            )
    return problems


def rule_hero_lines_stacked(window, page) -> list[tuple[str, str]]:
    """D6: both display lines start at the same left edge and stack."""
    from PySide6.QtWidgets import QWidget

    first = window.findChild(QWidget, "heroLine")
    second = window.findChild(QWidget, "heroLineAccent")
    if first is None or second is None or not first.isVisibleTo(window):
        return []
    one, two = _rect(window, first), _rect(window, second)
    problems = []
    if abs(one.left() - two.left()) > 2:
        problems.append(("hero_lines_stacked", f"left edges {one.left()} and {two.left()}"))
    if two.top() < one.bottom() - 6:
        problems.append(("hero_lines_stacked", f"lines overlap: {one.getRect()} {two.getRect()}"))
    return problems


def rule_hero_micro_gap(window, page) -> list[tuple[str, str]]:
    """D6: 10-14px between the micro label and the first display line."""
    from PySide6.QtWidgets import QWidget

    from ui_spec import HERO_MICRO_GAP

    micro = window.findChild(QWidget, "heroMicro")
    first = window.findChild(QWidget, "heroLine")
    if micro is None or first is None or not micro.isVisibleTo(window):
        return []
    gap = _gap(_rect(window, micro), _rect(window, first))
    if not HERO_MICRO_GAP.holds(gap):
        return [("hero_micro_gap", f"gap is {gap:.1f}px, spec is 10-14px")]
    return []


def rule_record_circle_padding(window, page) -> list[tuple[str, str]]:
    """D6: the Record circle is a large target with a comfortably small icon."""
    from PySide6.QtWidgets import QAbstractButton

    from ui_spec import CIRCLE_ICON_MAX_PX, CIRCLE_MIN_PX

    button = window.findChild(QAbstractButton, "circleButton")
    if button is None or not is_visible(button):
        return []
    problems = []
    if min(button.width(), button.height()) < CIRCLE_MIN_PX:
        problems.append(("record_circle_padding", f"circle is {button.width()}x{button.height()}"))
    icon = button.iconSize()
    if max(icon.width(), icon.height()) > CIRCLE_ICON_MAX_PX:
        problems.append(("record_circle_padding", f"icon is {icon.width()}x{icon.height()}"))
    return problems


def rule_build_label_centred(window, page) -> list[tuple[str, str]]:
    """D6: the Build label sits centred in its button, arrow included."""
    from PySide6.QtWidgets import QAbstractButton

    button = window.findChild(QAbstractButton, "buildButton")
    if button is None or not is_visible(button):
        return []
    metrics = button.fontMetrics()
    text_width = metrics.boundingRect(button.text()).width()
    contents = button.contentsRect()
    if text_width > contents.width():
        return [("build_label_centred", f"label {text_width}px wider than {contents.width()}px")]
    return []


def rule_row_run_label(window, page, *, running: bool) -> list[tuple[str, str]]:
    """D4: only a running row says Running; a waiting row keeps Run (disabled)."""
    from PySide6.QtWidgets import QAbstractButton, QWidget

    problems = []
    for row in window.findChildren(QWidget, "automationRow"):
        if not row.isVisibleTo(window):
            continue
        button = row.findChild(QAbstractButton, "runRowButton")
        if button is None:
            continue
        text = button.text()
        if "Running" in text and not running:
            problems.append(("row_run_label", f"row shows '{text}' while nothing is running"))
        if "Running" in text and running and button.isEnabled():
            problems.append(("row_run_label", "running row keeps its button enabled"))
    return problems


def rule_settings_checker_border(window, page) -> list[tuple[str, str]]:
    """D5: the Configure checker control is drawn with a complete border."""
    from PySide6.QtWidgets import QAbstractButton, QWidget

    for widget in window.findChildren(QWidget):
        if not isinstance(widget, QAbstractButton) or not is_visible(widget):
            continue
        if "Configure" not in widget.text():
            continue
        measurements = button_measurements(widget)
        if measurements is None:
            continue
        background = measurements[0]
        missing = [
            edge
            for edge in ("top", "bottom", "left", "right")
            if not edge_has_border(widget, edge, background)
        ]
        if missing:
            return [
                (
                    "settings_checker_border",
                    f"'{widget.text()}' has no visible border on {', '.join(missing)}",
                )
            ]
    return []


# --------------------------------------------------------------- driving


def _select_page(window, name: str) -> None:
    import app as app_module

    app_module._select_page(window, name)
    window.repaint()


def _save(window, out_dir: Path, scale: int, size: str, state: str) -> str:
    target = out_dir / f"{scale}-{size}-{state}.png"
    window.grab().save(str(target))
    return str(target)


def audit_state(window, app, page, state, scale, size, out_dir, findings, *, root=None) -> None:
    """Run every check and rule for one page/state combination."""
    from ui_spec import CLIP_ALLOWLIST, OVERLAP_ALLOWLIST

    window.repaint()
    app.processEvents()
    check_containment(window, page, state, scale, size, findings)
    check_overlap(window, page, state, scale, size, findings, OVERLAP_ALLOWLIST)
    check_text_clipped(window, page, state, scale, size, findings, CLIP_ALLOWLIST)
    check_buttons(window, page, state, scale, size, findings)
    check_required(root or window, page, state, scale, size, findings)
    check_animation(window, page, state, scale, size, findings, app)
    for rule, detail in _run_rules(window, page, state):
        findings.append(Finding("f-rule", page, state, scale, size, rule, detail))
    _save(window, out_dir, scale, size, f"{page}-{state}")


def _run_rules(window, page, state) -> list[tuple[str, str]]:
    from ui_spec import RULES

    problems: list[tuple[str, str]] = []
    for rule in RULES.get(page, ()) + RULES.get("all", ()):
        if rule == "row_run_label":
            problems.extend(rule_row_run_label(window, page, running=state == "running"))
        elif rule == "sidebar_focus_not_pill":
            problems.extend(rule_sidebar_focus_not_pill(window, page))
        elif rule == "settings_checker_border":
            problems.extend(rule_settings_checker_border(window, page))
        else:
            handler = globals().get(f"rule_{rule}")
            if handler is not None:
                try:
                    problems.extend(handler(window, page))
                except TypeError:
                    problems.extend(handler(window, page, state=state))
    return problems


def run_scale(scale: int, out_root: Path, *, offscreen: bool) -> dict[str, object]:
    """Build the real window once per scale and audit every state and size."""
    from PySide6.QtWidgets import QApplication

    import app as app_module
    from controller.service import WorkflowService
    from tests.ui_fixtures import build_ui_fixtures
    from ui.shell import MainWindow

    data_root = Path(tempfile.mkdtemp(prefix=f"once-audit-{scale}-"))
    build_ui_fixtures(data_root)
    service = WorkflowService.for_app_data(data_root)
    qt_app = QApplication.instance() or QApplication([sys.argv[0]])
    window = MainWindow(service, None, app_data_dir=data_root)
    platform = QApplication.platformName()
    window.resize(*SIZES[0])
    window.show()
    qt_app.processEvents()

    out_dir = out_root / str(scale)
    out_dir.mkdir(parents=True, exist_ok=True)
    findings: list[Finding] = []
    shots: list[str] = []
    size_name = {size: f"{size[0]}x{size[1]}" for size in SIZES}
    for size in SIZES:
        window.resize(*size)
        qt_app.processEvents()
        for page in PAGES:
            _select_page(window, page)
            audit_state(window, qt_app, page, "idle", scale, size_name[size], out_dir, findings)
        _select_page(window, "automations")
        page_widget = window.my_automations_page
        page_widget._banner.show_message(
            "warning",
            "Files need attention",
            "vscode-session.json: unknown launch fields: application",
            dismiss_button=True,
        )
        audit_state(
            window,
            qt_app,
            "automations_banner",
            "banner",
            scale,
            size_name[size],
            out_dir,
            findings,
        )
        page_widget._banner.clear()
        audit_state(window, qt_app, "running", "running", scale, size_name[size], out_dir, findings)
        page_widget._set_running(False)
        for state, dialog in (
            ("delete_dialog", _delete_dialog(window)),
            ("parameter_dialog", _parameter_dialog(window)),
        ):
            dialog.show()
            qt_app.processEvents()
            audit_state(
                window, qt_app, state, state, scale, size_name[size], out_dir, findings, root=dialog
            )
            shots.append(_save(dialog, out_dir, scale, size_name[size], f"{state}-window"))
            dialog.reject()
        page_widget._approval_panel.show_for(_desktop_workflow())
        audit_state(
            window,
            qt_app,
            "permission_panel",
            "permission_panel",
            scale,
            size_name[size],
            out_dir,
            findings,
        )
        page_widget._approval_panel.reset()
    shots.extend(str(path) for path in sorted(out_dir.glob("*.png")))
    window.close()
    service.close()
    return {
        "scale": scale,
        "platform": platform,
        "offscreen": offscreen,
        "findings": [asdict(finding) for finding in findings],
        "screenshots": shots,
    }


def _desktop_workflow():
    """A workflow whose run needs the desktop permission panel."""
    from engine.workflow import StepKind, Workflow, WorkflowStep

    return Workflow(
        "audit-desktop",
        "Open Notepad",
        (
            WorkflowStep(
                step_id="s1",
                name="Open Notepad",
                kind=StepKind.LAUNCH_APPLICATION,
                message="Launched Notepad.",
                target='{"application": "notepad"}',
            ),
        ),
    )


def _delete_dialog(window):
    from ui.components.delete_confirm import DeleteConfirmDialog, automation_delete_message

    return DeleteConfirmDialog(
        automation_delete_message("Rename screenshots", 2), runs_count=2, parent=window
    )


def _parameter_dialog(window):
    from ui.components.parameter_dialog import ParameterDialog

    return ParameterDialog(("invoice_folder", "month"), parent=window)


def summarise(reports: list[dict[str, object]]) -> dict[str, object]:
    """Count findings per check, page and scale."""
    by_check: Counter[str] = Counter()
    by_page: Counter[str] = Counter()
    by_scale: dict[str, Counter[str]] = {}
    for report in reports:
        scale = str(report["scale"])
        by_scale.setdefault(scale, Counter())
        for finding in report["findings"]:
            by_check[finding["check"]] += 1
            by_page[finding["page"]] += 1
            by_scale[scale][finding["check"]] += 1
    return {
        "total": sum(by_check.values()),
        "by_check": dict(sorted(by_check.items())),
        "by_page": dict(sorted(by_page.items())),
        "by_scale": {key: dict(sorted(value.items())) for key, value in by_scale.items()},
        "platforms": sorted({str(report["platform"]) for report in reports}),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=int, choices=SCALES, help="audit one scale only")
    parser.add_argument("--offscreen", action="store_true", help="use the offscreen platform")
    parser.add_argument("--out", default=None, help="folder for PNGs and the JSON report")
    args = parser.parse_args(argv)

    out_root = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="once-ui-audit-"))
    out_root.mkdir(parents=True, exist_ok=True)

    if args.scale is None:
        reports = []
        for scale in SCALES:
            environment = dict(os.environ)
            environment["QT_SCALE_FACTOR"] = f"{scale / 100:.2f}"
            environment["QT_QPA_PLATFORM"] = "offscreen" if args.offscreen else "windows"
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--scale",
                str(scale),
                "--out",
                str(out_root),
            ]
            if args.offscreen:
                command.append("--offscreen")
            completed = subprocess.run(command, env=environment, capture_output=True, text=True)
            if completed.returncode != 0:
                print(completed.stdout[-4000:])
                print(completed.stderr[-4000:], file=sys.stderr)
                return completed.returncode
            report_path = out_root / str(scale) / "report.json"
            reports.append(json.loads(report_path.read_text(encoding="utf-8")))
        summary = summarise(reports)
        (out_root / "audit-report.json").write_text(
            json.dumps({"summary": summary, "reports": reports}, indent=2), encoding="utf-8"
        )
        print(json.dumps(summary, indent=2))
        print(f"report: {out_root / 'audit-report.json'}")
        return 0 if summary["total"] == 0 else 1

    report = run_scale(args.scale, out_root, offscreen=args.offscreen)
    target = out_root / str(args.scale) / "report.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"scale": args.scale, "findings": len(report["findings"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Quick smoke tests for the redesigned application shell."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from PySide6.QtCore import SIGNAL, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QLabel,
    QPushButton,
    QToolButton,
)

from controller.service import WorkflowService
from engine.workflow import StepKind, Workflow, WorkflowStep
from ui.components.spacer import Spacer
from ui.shell import MainWindow, ShellPages

UI_ROOT = Path(__file__).resolve().parents[1] / "ui"


@pytest.fixture
def app(qtbot):
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


@pytest.fixture
def window(qtbot, app):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    yield window


def test_page_navigation_switches_workspace(qtbot, window):
    qtbot.mouseClick(window.sidebar._automations_button, Qt.MouseButton.LeftButton)
    qtbot.wait(50)
    assert window.workspace.currentIndex() == ShellPages.MY_AUTOMATIONS


def test_home_page_shows_welcome_and_empty_activity(qtbot, window):
    home = window.home_page
    assert window.workspace.currentIndex() == ShellPages.HOME
    title = home._title_label.text()
    subtitle = home._subtitle_label.text()
    assert "Once" in title
    assert "personal assistant" in subtitle
    assert home._activity_empty.isVisible() is True


def test_create_automation_page_has_description_input(qtbot, window):
    window._show_create_automation()
    page = window.create_automation_page
    input_field = page._description_input
    assert input_field.placeholderText().startswith("Example:")
    QTest.keyClicks(input_field, "Open invoices folder and read PDFs")
    assert page._description_input.toPlainText() == "Open invoices folder and read PDFs"


def test_shell_injects_the_service_into_the_home_page(qtbot, window):
    # Without this, HomePage._refresh_activity() returns early and the Home
    # page shows an empty Recent activity block forever.
    assert window.home_page._service is not None
    assert window.home_page._service is window._service


def test_create_automation_button_emits_typed_task_and_banners_honestly(qtbot, window):
    """Swap test (2026-10-30): the blocking QMessageBox.information became a
    page banner. Same trigger, stronger assertion: a real visible banner on
    the create page quotes the typed task and says what was and was not done.
    Replaces: test_create_automation_button_emits_typed_task.
    """
    window._show_create_automation()
    page = window.create_automation_page
    page._description_input.setPlainText("Open invoices folder and read PDFs")
    received: list[str] = []
    page.task_entered.connect(received.append)

    qtbot.mouseClick(page._create_button, Qt.MouseButton.LeftButton)

    assert received == ["Open invoices folder and read PDFs"]
    assert page._banner.isVisible()
    assert "cannot turn a typed description into an automation yet" in page._banner.body_text
    assert "Open invoices folder and read PDFs" in page._banner.body_text


def test_create_automation_button_ignores_blank_input(qtbot, window):
    """Swap test (2026-10-30), same-or-more: blank input emits nothing and
    never surfaces a banner. Replaces the earlier monkeypatched-modal variant."""
    window._show_create_automation()
    page = window.create_automation_page
    page._description_input.setPlainText("   ")
    received: list[str] = []
    page.task_entered.connect(received.append)

    qtbot.mouseClick(page._create_button, Qt.MouseButton.LeftButton)

    assert received == []
    assert page._banner.isHidden()


def test_sidebar_active_state_after_sidebar_click(qtbot, window):
    qtbot.mouseClick(window.sidebar._activity_button, Qt.MouseButton.LeftButton)
    qtbot.wait(50)
    assert window.sidebar.is_on(ShellPages.ACTIVITY)


def test_settings_page_opens_from_sidebar(qtbot, window):
    window._show_page(ShellPages.SETTINGS)
    qtbot.wait(50)
    settings = window.settings_page
    assert window.workspace.currentIndex() == ShellPages.SETTINGS
    assert settings._authorized_group.isVisible() is True
    assert settings._verifier_group.isVisible() is True
    assert window.sidebar._settings_button.isChecked() is True


def test_settings_page_keeps_no_placeholder_controls(qtbot, window):
    """Settings shows only real configuration, never dead placeholder groups."""
    settings = window.settings_page
    for removed in (
        "_recordings_group",
        "_gemini_group",
        "_coding_agent_group",
        "_advanced_group",
        "_start_recording_button",
        "_stop_recording_button",
        "_delete_recording_button",
        "_connect_gemini_button",
        "_status_label",
    ):
        assert not hasattr(settings, removed), f"placeholder still present: {removed}"


# The old dialog-based tests (test_settings_verifier_button_saves_and_signals,
# test_settings_verifier_button_without_data_dir_does_not_crash) were swapped on
# 2026-10-30 for
# * tests/test_p2_shell.py::test_verifier_configuration_saves_through_the_inline_panel
#   (real save through save_verifier_config + persisted round-trip), and
# * tests/test_p2_shell.py::test_verifier_configuration_without_data_folder_uses_banner
# Both assert the same-or-more outcomes the modal tests asserted. See commit message.


def test_settings_authorized_folder_persists_through_service(qtbot, window, monkeypatch, tmp_path):
    """Mirrors the old window: dialog choice is stored on the service and shown."""
    settings = window.settings_page
    chosen = tmp_path / "authorized"
    chosen.mkdir()
    monkeypatch.setattr(
        "ui.pages.settings.QFileDialog.getExistingDirectory",
        staticmethod(lambda *args, **kwargs: str(chosen)),
    )

    qtbot.mouseClick(settings._choose_authorized_button, Qt.MouseButton.LeftButton)

    assert window._service.allowed_root == chosen
    assert f"Authorized folder: {chosen}" in settings._authorized_label.text()


def test_settings_authorized_folder_cancel_keeps_previous_value(qtbot, window, monkeypatch):
    """Closing the folder dialog changes nothing, like the old window."""
    settings = window.settings_page
    before = settings._authorized_label.text()
    monkeypatch.setattr(
        "ui.pages.settings.QFileDialog.getExistingDirectory",
        staticmethod(lambda *args, **kwargs: ""),
    )

    qtbot.mouseClick(settings._choose_authorized_button, Qt.MouseButton.LeftButton)

    assert settings._authorized_label.text() == before
    assert window._service.allowed_root is None


def test_settings_displays_a_previously_chosen_folder(qtbot, window, tmp_path):
    """The stored authorized folder is displayed again, not only chosen once."""
    settings = window.settings_page
    window._service.set_allowed_root(tmp_path)

    settings.set_service(window._service)

    assert f"Authorized folder: {tmp_path}" in settings._authorized_label.text()


def test_shell_injects_the_service_into_the_settings_page(qtbot, window):
    """The settings page cannot record a folder without the real service."""
    assert window.settings_page._service is window._service


# --- Button audit (P1.2): every clicked control shows an observable effect -------


def _window_with_service(qtbot, tmp_path):
    """A real shell backed by a real, history-persisting service in tmp_path."""
    service = WorkflowService.for_app_data(tmp_path)
    window = MainWindow(service=service)
    qtbot.addWidget(window)
    window.show()
    return window, service


def demo_workflow_for_tests() -> Workflow:
    return Workflow(
        workflow_id="open-me",
        name="List invoices",
        steps=(
            WorkflowStep(
                step_id="s1",
                name="List",
                kind=StepKind.REPORT,
                message="Listed.",
            ),
        ),
    )


def test_sidebar_click_settings_switches_and_checks(qtbot, window):
    qtbot.mouseClick(window.sidebar._settings_button, Qt.MouseButton.LeftButton)
    qtbot.wait(50)
    assert window.workspace.currentIndex() == ShellPages.SETTINGS
    assert window.sidebar.is_on(ShellPages.SETTINGS)


def test_sidebar_click_home_returns_to_home(qtbot, window):
    window._show_page(ShellPages.SETTINGS)
    qtbot.mouseClick(window.sidebar._home_button, Qt.MouseButton.LeftButton)
    qtbot.wait(50)
    assert window.workspace.currentIndex() == ShellPages.HOME
    assert window.sidebar.is_on(ShellPages.HOME)


def test_home_create_button_clicks_into_create_flow(qtbot, window):
    qtbot.mouseClick(window.home_page._create_automation_button, Qt.MouseButton.LeftButton)
    qtbot.wait(50)
    assert window.workspace.currentWidget() is window.create_automation_page


def test_home_demo_button_runs_the_demo_exactly_once(qtbot, tmp_path):
    window, service = _window_with_service(qtbot, tmp_path)

    qtbot.mouseClick(window.home_page._demo_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: len(service.history()) == 1, timeout=10_000)
    # Wait for the demo thread to fully finish before teardown: destroying a
    # running QThread aborts the process under the offscreen platform.
    qtbot.waitUntil(lambda: window.status_footer.state == "Ready", timeout=10_000)
    qtbot.waitUntil(lambda: window._demo_thread is None, timeout=10_000)

    runs = service.history()
    assert len(runs) == 1
    assert runs[0].workflow_id == "demo-local-workflow"
    assert runs[0].status.value == "SUCCEEDED"


def test_open_button_click_shows_opened_workflow_on_the_review_page(qtbot, tmp_path):
    window, service = _window_with_service(qtbot, tmp_path)
    service.save(demo_workflow_for_tests())
    window._show_page(ShellPages.MY_AUTOMATIONS)
    page = window.my_automations_page
    page.refresh()
    page._workflow_list.setCurrentRow(0)

    qtbot.mouseClick(page._open_button, Qt.MouseButton.LeftButton)

    assert window.workspace.currentWidget() is window.review_page
    assert "List invoices" in window.review_page._goal_label.text()
    assert window.review_page._steps_list.count() == 1


def test_review_cancel_button_click_returns_home(qtbot, window):
    window.workspace.setCurrentWidget(window.review_page)
    qtbot.mouseClick(window.review_page._cancel_button, Qt.MouseButton.LeftButton)
    qtbot.wait(50)
    assert window.workspace.currentIndex() == ShellPages.HOME


def test_activity_run_click_shows_its_steps(qtbot, tmp_path):
    window, service = _window_with_service(qtbot, tmp_path)
    service.run_demo()
    window._show_page(ShellPages.ACTIVITY)
    page = window.activity_page
    page.refresh()
    history_list = page._history_list
    item = history_list.item(0)
    assert item is not None

    qtbot.mouseClick(
        history_list.viewport(),
        Qt.MouseButton.LeftButton,
        pos=history_list.visualItemRect(item).center(),
    )

    assert "demo-local-workflow" in page._details_label.text()
    assert "SUCCEEDED" in page._details_label.text()


# --- Layout foundation (B3): structure and honest controls -------------------------------


def test_sidebar_has_four_nav_items_brand_and_one_footer(qtbot, window):
    widgets = [window.sidebar.widgetForAction(a) for a in window.sidebar.actions()]
    buttons = [w for w in widgets if isinstance(w, QToolButton)]
    labels = [w for w in widgets if isinstance(w, QLabel) and not isinstance(w, Spacer)]
    assert [b.text() for b in buttons] == ["Home", "My automations", "Activity", "Settings"]
    assert [label.text() for label in labels] == ["Once", "Once Assistive Automation"]


def _ui_sources() -> dict[Path, str]:
    pages = sorted(UI_ROOT.glob("*.py")) + sorted((UI_ROOT / "pages").glob("*.py"))
    return {path: path.read_text(encoding="utf-8") for path in pages}


def _pass_only_handlers(source: str) -> set[str]:
    """Method names whose body does nothing but pass (with an optional docstring)."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = [
                stmt
                for stmt in node.body
                if not (
                    isinstance(stmt, ast.Expr)
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                )
            ]
            if body and all(isinstance(stmt, ast.Pass) for stmt in body):
                names.add(node.name)
    return names


def _emitted_signals(source: str, method_name: str) -> set[str] | None:
    """Signals a named method emits; None when the body does anything else too."""
    signals: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    func = sub.func
                    if (
                        isinstance(func, ast.Attribute)
                        and func.attr == "emit"
                        and isinstance(func.value, ast.Attribute)
                        and isinstance(func.value.value, ast.Name)
                        and func.value.value.id == "self"
                    ):
                        signals.add(func.value.attr)
                    else:
                        return None  # a real call: the handler does its own work
            return signals
    return None


def _connect_self_targets(source: str) -> list[tuple[str, bool]]:
    """(name, is_terminal_emit) pairs from `...connect(self.X)` / `...connect(self.X.emit)`."""
    targets: list[tuple[str, bool]] = []
    for node in ast.walk(ast.parse(source)):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "connect"
            and node.args
        ):
            continue
        first = node.args[0]
        if not isinstance(first, ast.Attribute):
            continue
        if isinstance(first.value, ast.Name) and first.value.id == "self":
            targets.append((first.attr, False))  # bound method handler
        elif (
            first.attr == "emit"
            and isinstance(first.value, ast.Attribute)
            and isinstance(first.value.value, ast.Name)
            and first.value.value.id == "self"
        ):
            targets.append((first.value.attr, True))  # signal relay
    return targets


def _follow_chain(sources: dict[Path, str], signal: str) -> str | None:
    """Follow `<signal>.connect(self.X)` to a real handler; return why not, else None."""
    seen: set[str] = set()
    current = signal
    for _ in range(6):  # bounded pass-through depth
        if current in seen:
            return f"signal chain for {current} loops back on itself"
        seen.add(current)
        # recompile per hop: relays change the signal being followed
        pattern = re.compile(
            rf"\.{re.escape(current)}\.connect\(\s*self\.([A-Za-z_]\w*)(\.emit)?\s*[,)]"
        )
        hit = None
        for path, source in sources.items():
            match = pattern.search(source)
            if match is not None:
                hit = (path, match)
                break
        if hit is None:
            return f"signal {current} has no downstream connection"
        path, match = hit
        target, relay = match.group(1), match.group(2)
        if relay:  # connected as `.emit`: the chain continues with the next signal
            current = target
            continue
        if target in _pass_only_handlers(sources[path]):
            return f"signal {current} ends in the pass-only handler {target}"
        return None
    return None


def _static_unwired_reasons(sources: dict[Path, str]) -> list[str]:
    """Chain-follow the `clicked -> handler -> signal -> shell` wiring of the ui."""
    reasons: list[str] = []
    connected: set[str] = set()
    relays: set[str] = set()
    for source in sources.values():
        for name, is_emit in _connect_self_targets(source):
            (relays if is_emit else connected).add(name)
    for path, source in sources.items():
        trivial = _pass_only_handlers(source)
        for name, is_emit in _connect_self_targets(source):
            if not is_emit and name in trivial:
                reasons.append(f"{path.name} connects a pass-only handler: {name}")
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name not in connected:
                continue
            emitted = _emitted_signals(source, node.name) or set()
            for signal in emitted:
                failure = _follow_chain(sources, signal)
                if failure is not None:
                    reasons.append(f"{path.name}: {node.name} -> {failure}")
    for signal in relays:
        failure = _follow_chain(sources, signal)
        if failure is not None:
            reasons.append(f"relay {signal} -> {failure}")
    return reasons


def test_every_page_has_no_unwired_buttons(qtbot, window):
    """Honest-controls rule, strengthened (2026-10-29 amendment).

    A visible enabled button must be actually connected (QPushButton and
    QToolButton, including the four sidebar items), AND its wiring is followed
    through: a connected handler may not be pass-only, and a handler that only
    emits a signal must reach a downstream shell connection with a real handler.
    """
    targets = [
        window.home_page,
        window.my_automations_page,
        window.activity_page,
        window.settings_page,
        window.review_page,
        window.create_automation_page,
        window.sidebar,
    ]
    unwired: list[str] = []
    for target in targets:
        if target is not window.sidebar:
            window.workspace.setCurrentWidget(target)
        qtbot.wait(10)
        for button in target.findChildren(QAbstractButton):
            if (
                button.isVisible()
                and button.isEnabled()
                and button.receivers(SIGNAL("clicked()")) == 0
            ):
                unwired.append(f"{target.__class__.__name__}: {button.text()}")
    sources = _ui_sources()
    unwired.extend(_static_unwired_reasons(sources))
    assert unwired == []


def test_review_edit_and_approve_are_hidden_until_j6(qtbot, window):
    """Per the 2026-10-29 amendment: approval controls stay hidden until J6."""
    window.workspace.setCurrentWidget(window.review_page)
    qtbot.wait(10)
    assert window.review_page._edit_button.isHidden()
    assert window.review_page._approve_button.isHidden()
    assert window.review_page._cancel_button.isVisible()


def test_pages_use_spacing_tokens_for_margins(qtbot, window):
    from ui.styles import SPACING_VALUES

    layouts = [
        window.home_page.layout(),
        window.my_automations_page.layout(),
        window.activity_page.layout(),
        window.create_automation_page.layout(),
        window.review_page.layout(),
        window.settings_page._scroll_layout,
    ]
    for layout in layouts:
        margins = layout.contentsMargins()
        for value in (margins.left(), margins.top(), margins.right(), margins.bottom()):
            assert value in SPACING_VALUES


def test_type_scale_is_declared_once_in_the_theme(qtbot, window):
    from ui.styles import (
        TYPE_CAPTION_PX,
        TYPE_HOME_TITLE_PX,
        TYPE_QUESTION_PX,
        TYPE_SUBTITLE_PX,
        TYPE_TITLE_PX,
    )

    pages = [
        window.home_page,
        window.my_automations_page,
        window.activity_page,
        window.create_automation_page,
        window.review_page,
        window.settings_page,
    ]
    for page in pages:
        for widget in (*page.findChildren(QLabel), *page.findChildren(QPushButton)):
            assert "font-size:" not in widget.styleSheet(), (
                f"inline font-size on {page.__class__.__name__}: {widget.styleSheet()}"
            )

    sheet = QApplication.instance().styleSheet()
    for rule, size in (
        ("QLabel#pageTitle", TYPE_TITLE_PX),
        ("QLabel#pageSubtitle", TYPE_SUBTITLE_PX),
        ("QLabel#homeTitle", TYPE_HOME_TITLE_PX),
        ("QLabel#questionLabel", TYPE_QUESTION_PX),
        ("QLabel#hintLabel", TYPE_CAPTION_PX),
    ):
        start = sheet.index(rule)
        block = sheet[start : sheet.index("}", start)]
        assert f"font-size: {size}px" in block, f"{rule} does not use its token"
    assert window.sidebar._home_button.styleSheet() == ""


def test_sidebar_buttons_resist_stuck_repeats(qtbot, window):
    assert window.sidebar._home_button.autoRepeat() is False
    assert window.sidebar._automations_button.autoRepeat() is False
    assert window.sidebar._activity_button.autoRepeat() is False
    assert window.sidebar._settings_button.autoRepeat() is False

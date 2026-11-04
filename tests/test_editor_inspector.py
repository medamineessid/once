"""A2a: node selection on the canvas and the right-hand inspector.

The spec is docs/specs/visual_workflow_editor.md (section 4 "Node
selection", section 8 "Step details inspector"): clicking a node selects
it with a clear outline and highlights both adjacent edges; an empty
click or Esc deselects; the inspector shows the selected step's summary
and automation info when nothing is selected. Keyboard: Tab and the
arrow keys walk along the chain edges, Enter moves focus to the
inspector.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from controller.editor import WorkflowEditorSession
from engine.replay import MUTATING_DESKTOP_KINDS
from engine.workflow import StepKind, Workflow, WorkflowRunner, WorkflowStep
from ui.editor import inspector as inspector_module
from ui.editor.canvas import CanvasView
from ui.editor.inspector import PreviewCandidate
from ui.editor.layout import FINISH_ID, START_ID
from ui.pages.editor import EditorPage
from ui.styles import ACCENT


@pytest.fixture
def app() -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def new_session() -> WorkflowEditorSession:
    session = WorkflowEditorSession()
    session.open(
        Workflow(
            workflow_id="automation-a2a-test",
            name="A2 selection",
            steps=(
                WorkflowStep(
                    step_id="s1",
                    name="Look around",
                    kind=StepKind.REPORT,
                    message="first",
                ),
                WorkflowStep(
                    step_id="s2",
                    name="Open notepad",
                    kind=StepKind.LAUNCH_APPLICATION,
                    message="second",
                    target='{"application": "notepad"}',
                ),
            ),
        )
    )
    return session


def make_page(qtbot, session: WorkflowEditorSession) -> EditorPage:
    page = EditorPage()
    qtbot.addWidget(page)
    page.show()
    page._session = session
    page._refresh()
    return page


def click_node(view: CanvasView, node_id: str) -> None:
    """Click exactly on a node's plan rectangle, through the real view."""
    slot = view.nodes[node_id].slot
    center = QPointF(slot.x + slot.w / 2, slot.y + slot.h / 2)
    point = view.mapFromScene(center)
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)


# --- Canvas selection ---------------------------------------------------------


def test_clicking_a_node_selects_it_and_highlights_adjacent_edges(qtbot, app) -> None:
    page = make_page(qtbot, new_session())
    canvas = page._canvas

    changes: list[object] = []
    canvas.node_selected.connect(changes.append)
    click_node(canvas, "s1")

    assert canvas.selected_id == "s1"
    assert changes == ["s1"]
    # Incoming edge (Start -> s1) and outgoing edge (s1 -> s2) are both
    # highlighted with the accent selection pen...
    incoming = canvas.edge_lookup[(START_ID, "s1")][0]
    outgoing = canvas.edge_lookup[("s1", "s2")][0]
    assert incoming.pen().color().name().lower() == ACCENT.lower()
    assert incoming.pen().widthF() == 2.0
    assert outgoing.pen().color().name().lower() == ACCENT.lower()
    # ...and nothing else is.
    other = canvas.edge_lookup[("s2", FINISH_ID)][0]
    assert other.pen().color().name().lower() != ACCENT.lower()


def test_clicking_a_selected_node_again_deselects(qtbot, app) -> None:
    page = make_page(qtbot, new_session())
    canvas = page._canvas

    click_node(canvas, "s1")
    assert canvas.selected_id == "s1"
    click_node(canvas, "s1")  # second click on the same node deselects

    assert canvas.selected_id is None


def test_click_on_empty_canvas_deselects(qtbot, app) -> None:
    page = make_page(qtbot, new_session())
    canvas = page._canvas

    click_node(canvas, "s2")
    assert canvas.selected_id == "s2"
    empty_point = view_point(canvas, 360.0, 140.0)  # inside the scene, on no card
    QTest.mouseClick(canvas.viewport(), Qt.MouseButton.LeftButton, pos=empty_point)

    assert canvas.selected_id is None


def view_point(view: CanvasView, x: float, y: float):
    return view.mapFromScene(QPointF(x, y))


def test_escape_clears_the_selection(qtbot, app) -> None:
    page = make_page(qtbot, new_session())
    canvas = page._canvas
    canvas.setFocus()

    click_node(canvas, "s2")
    assert canvas.selected_id == "s2"
    QTest.keyPress(canvas, Qt.Key_Escape)

    assert canvas.selected_id is None


def test_tab_and_arrow_keys_walk_the_chain(qtbot, app) -> None:
    page = make_page(qtbot, new_session())
    canvas = page._canvas
    canvas.setFocus()

    QTest.keyPress(canvas, Qt.Key_Right)
    assert canvas.selected_id == START_ID
    QTest.keyPress(canvas, Qt.Key_Right)
    assert canvas.selected_id == "s1"
    QTest.keyPress(canvas, Qt.Key_Tab)
    assert canvas.selected_id == "s2"
    QTest.keyPress(canvas, Qt.Key_Left)
    assert canvas.selected_id == "s1"
    QTest.keyClick(canvas, Qt.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
    assert canvas.selected_id == START_ID


def test_selection_survives_a_rebuild_when_the_step_still_exists(qtbot, app) -> None:
    page = make_page(qtbot, new_session())
    canvas = page._canvas
    click_node(canvas, "s2")

    page._refresh()  # any edit rebuilds the scene

    assert canvas.selected_id == "s2"


# --- Inspector ----------------------------------------------------------------


def test_selecting_a_node_opens_a_summary_in_the_inspector(qtbot, app) -> None:
    page = make_page(qtbot, new_session())

    click_node(page._canvas, "s2")

    assert page._inspector.isVisible()
    summary = page._inspector.summary_text
    assert "Open notepad" in summary
    assert "LAUNCH_APPLICATION" in summary
    assert "Read-only" not in summary or "changes your computer" in summary.lower()


def test_terminals_explain_they_are_not_editable_steps(qtbot, app) -> None:
    page = make_page(qtbot, new_session())

    click_node(page._canvas, START_ID)

    assert "fixed marker" in page._inspector.summary_text
    assert not page._inspector.field_names


def test_inspector_reports_mutating_steps_need_approval(qtbot, app) -> None:
    page = make_page(qtbot, new_session())
    assert StepKind.LAUNCH_APPLICATION in MUTATING_DESKTOP_KINDS

    click_node(page._canvas, "s2")

    summary = page._inspector.summary_text
    assert "changes your computer" in summary.lower()
    assert "approval" in summary.lower()


def test_inspector_shows_read_only_marker_target_and_timeout(qtbot, app) -> None:
    session = new_session()
    session.update_step(
        "s1",
        kind=StepKind.INSPECT_PATH,
        target="C:/authorized/invoice.pdf",
        timeout_seconds=12.5,
    )
    page = make_page(qtbot, session)

    click_node(page._canvas, "s1")

    summary = page._inspector.summary_text
    assert "Read-only" in summary
    assert "C:/authorized/invoice.pdf" in summary
    assert "12.5 seconds" in summary


def test_inspector_shows_automation_info_when_nothing_selected(qtbot, app) -> None:
    page = make_page(qtbot, new_session())

    summary = page._inspector.summary_text
    assert "A2 selection" in summary
    assert "2 steps" in summary


def test_inspector_close_button_hides_and_selection_reopens(qtbot, app) -> None:
    page = make_page(qtbot, new_session())

    click_node(page._canvas, "s1")
    assert page._inspector.isVisible()
    QTest.mouseClick(page._inspector._close_button, Qt.MouseButton.LeftButton)
    assert not page._inspector.isVisible()

    click_node(page._canvas, "s1")  # selecting again brings it back
    assert page._inspector.isVisible()


def test_enter_on_a_selected_node_focuses_the_inspector(qtbot, app) -> None:
    page = make_page(qtbot, new_session())
    canvas = page._canvas
    canvas.setFocus()
    QTest.keyPress(canvas, Qt.Key_Right)
    QTest.keyPress(canvas, Qt.Key_Right)
    assert canvas.selected_id == "s1"

    QTest.keyPress(canvas, Qt.Key_Return)

    # A QScrollArea receives focus on its viewport child; the assertion is
    # that keyboard focus went into the inspector, not the canvas.
    def inspector_focused() -> bool:
        focused = QApplication.focusWidget()
        return page._inspector.hasFocus() or (
            focused is not None and page._inspector.isAncestorOf(focused)
        )

    qtbot.waitUntil(inspector_focused, timeout=1000)


def test_inspector_applies_editable_fields_through_the_session(qtbot, app) -> None:
    page = make_page(qtbot, new_session())
    click_node(page._canvas, "s1")

    page._inspector.field("name").setText("A clearer note")
    page._inspector.field("message").setText("updated message")
    page._inspector.field("max_attempts").setValue(3)
    QTest.mouseClick(page._inspector.apply_button, Qt.MouseButton.LeftButton)

    step = page._session.workflow().steps[0]
    assert step.name == "A clearer note"
    assert step.message == "updated message"
    assert step.max_attempts == 3
    assert page._session.is_dirty()


def test_inspector_exposes_only_fields_allowed_for_the_step_kind(qtbot, app) -> None:
    page = make_page(qtbot, new_session())

    click_node(page._canvas, "s1")
    assert set(page._inspector.field_names) == {"name", "message", "kind", "max_attempts"}

    page._session.update_step(
        "s1",
        kind=StepKind.WAIT_WINDOW,
        target='{"title": "Invoices"}',
        timeout_seconds=4.0,
    )
    page._refresh()
    assert set(page._inspector.field_names) == {
        "name",
        "message",
        "kind",
        "target",
        "max_attempts",
        "timeout_seconds",
    }


def test_invalid_inspector_edit_keeps_definition_and_shows_inline_error(qtbot, app) -> None:
    page = make_page(qtbot, new_session())
    page._session.update_step(
        "s1",
        kind=StepKind.INSPECT_PATH,
        target="C:/authorized/invoice.pdf",
    )
    page._refresh()
    click_node(page._canvas, "s1")
    original = page._session.workflow().steps[0]

    page._inspector.field("target").setText("relative\\invoice.pdf")
    QTest.mouseClick(page._inspector.apply_button, Qt.MouseButton.LeftButton)

    assert page._session.workflow().steps[0] == original
    assert "absolute" in page._banner.body_text.lower()


# --- A2: live preview (debounced, engine-validator only) --------------------------------


@pytest.fixture
def fast_preview(monkeypatch: pytest.MonkeyPatch) -> int:
    """Shrink the debounce window so previews settle within the test."""
    interval = 30
    monkeypatch.setattr(inspector_module, "PREVIEW_DEBOUNCE_MS", interval)
    return interval


def _record_previews(page: EditorPage) -> list[PreviewCandidate]:
    candidates: list[PreviewCandidate] = []
    page._inspector.preview_requested.connect(candidates.append)
    return candidates


def test_rapid_field_edits_send_a_single_preview(qtbot, app, fast_preview) -> None:
    page = make_page(qtbot, new_session())
    click_node(page._canvas, "s1")
    candidates = _record_previews(page)

    qtbot.keyClicks(page._inspector.field("name"), "X")
    qtbot.keyClicks(page._inspector.field("message"), "halfwayY")
    qtbot.waitUntil(lambda: len(candidates) == 1, timeout=2000)
    qtbot.wait(fast_preview * 3)
    assert len(candidates) == 1

    (candidate,) = candidates
    assert candidate.step_id == "s1"
    # Values are read when the timer fires, so the latest edits win.
    assert candidate.values["name"] == "Look aroundX"
    assert candidate.values["message"] == "firsthalfwayY"


def test_loading_a_step_sends_no_preview(qtbot, app, fast_preview) -> None:
    page = make_page(qtbot, new_session())
    click_node(page._canvas, "s1")
    candidates = _record_previews(page)

    page._refresh()  # programmatic load
    qtbot.wait(fast_preview * 4)
    assert candidates == []

    # Programmatic line-edit writes are silent too: line edits use textEdited,
    # so only real typing schedules a preview. (Number fields have no
    # user-only signal in Qt; they are silent only while populating.)
    page._inspector.field("name").setText("quiet")
    page._inspector.field("message").setText("still quiet")
    qtbot.wait(fast_preview * 4)
    assert candidates == []


def test_kind_switch_previews_once_with_current_values(qtbot, app, fast_preview) -> None:
    page = make_page(qtbot, new_session())
    click_node(page._canvas, "s1")
    candidates = _record_previews(page)

    qtbot.keyClicks(page._inspector.field("name"), "X")
    kind_field = page._inspector.field("kind")
    kind_field.setCurrentIndex(kind_field.findData(StepKind.WAIT_WINDOW))
    qtbot.waitUntil(lambda: len(candidates) == 1, timeout=2000)
    qtbot.wait(fast_preview * 3)
    assert len(candidates) == 1

    (candidate,) = candidates
    assert candidate.step_id == "s1"
    assert candidate.values["kind"] is StepKind.WAIT_WINDOW
    assert candidate.values["name"] == "Look aroundX"
    # Retargeted fields appear with their rebuilt values at fire time.
    assert candidate.values["target"] == ""
    assert candidate.values["timeout_seconds"] == 30.0
    assert "postcondition" not in candidate.values


def test_selection_change_drops_a_pending_preview(qtbot, app, fast_preview) -> None:
    page = make_page(qtbot, new_session())
    click_node(page._canvas, "s1")
    candidates = _record_previews(page)

    qtbot.keyClicks(page._inspector.field("name"), "lost")
    click_node(page._canvas, "s2")

    qtbot.wait(fast_preview * 4)
    assert candidates == []
    assert page._inspector.preview_verdict == ""


def test_a_stale_candidate_after_selection_change_is_dropped(qtbot, app, fast_preview) -> None:
    page = make_page(qtbot, new_session())
    click_node(page._canvas, "s2")  # a valid LAUNCH_APPLICATION step
    qtbot.keyClicks(page._inspector.field("message"), "!")
    qtbot.waitUntil(lambda: "valid" in page._inspector.preview_verdict.lower(), timeout=2000)
    verdict = page._inspector.preview_verdict

    # A late preview for the previously selected step must be discarded.
    page._inspector.preview_requested.emit(PreviewCandidate("s1", {"name": ""}))
    qtbot.wait(fast_preview * 2)
    assert page._inspector.preview_verdict == verdict

    # Only the selected step can be previewed.
    page._inspector.preview_requested.emit(PreviewCandidate("s1", {"name": "mine"}))
    qtbot.wait(fast_preview * 2)
    assert page._inspector.preview_verdict == verdict


def test_running_stops_a_pending_preview_and_ignores_candidates(qtbot, app, fast_preview) -> None:
    page = make_page(qtbot, new_session())
    click_node(page._canvas, "s1")
    candidates = _record_previews(page)
    qtbot.keyClicks(page._inspector.field("name"), "during")

    page.set_running(True)
    qtbot.wait(fast_preview * 4)
    assert candidates == []
    assert page._inspector.preview_verdict == ""

    # A late candidate is ignored while running...
    page._inspector.preview_requested.emit(PreviewCandidate("s1", {"name": ""}))
    qtbot.wait(10)
    assert page._inspector.preview_verdict == ""

    # ...but after the run ends a candidate is validated again.
    page.set_running(False)
    page._inspector.preview_requested.emit(PreviewCandidate("s1", {"name": "Back again"}))
    qtbot.wait(10)
    assert "valid" in page._inspector.preview_verdict.lower()
    # Only the two manual test emits were recorded; no burst from the run.
    assert len(candidates) == 2


def test_preview_uses_the_engine_validator_and_never_runs_or_mutates(
    qtbot, app, fast_preview, monkeypatch
) -> None:
    def refuse_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("The live preview must never execute a workflow.")

    validate_calls: list[Workflow] = []
    real_validate = WorkflowRunner.validate

    def counting_validate(workflow: Workflow) -> None:  # type: ignore[no-untyped-def]
        validate_calls.append(workflow)
        real_validate(workflow)

    monkeypatch.setattr(WorkflowRunner, "run", refuse_run)
    monkeypatch.setattr(WorkflowRunner, "validate", staticmethod(counting_validate))

    page = make_page(qtbot, new_session())
    steps_before = page._session.workflow().steps
    click_node(page._canvas, "s1")
    validate_calls.clear()

    qtbot.keyClicks(page._inspector.field("message"), " live")
    qtbot.waitUntil(lambda: "valid" in page._inspector.preview_verdict.lower(), timeout=2000)
    assert len(validate_calls) == 1  # exactly the engine validator was called
    assert page._session.workflow().steps == steps_before  # preview edits nothing
    assert page._session.is_dirty() is False
    assert page._session.can_undo is False

    # An invalid edit shows the validator's message, still without mutating.
    page._inspector.preview_requested.emit(PreviewCandidate("s1", {"name": "  "}))
    qtbot.wait(10)
    assert "needs a name" in page._inspector.preview_verdict.lower()
    assert page._session.workflow().steps == steps_before

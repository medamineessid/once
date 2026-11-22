"""The scenario matrix: one step recorded on variant A, replayed on B/C/D.

Every descriptor is recorded from what the adapter observed on A and every
expected outcome is recorded by actually performing the step on A, so the lab
cannot claim behaviour the surface never showed.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from engine.resolve import SafetyClass, Surface

from . import qt_window, web_app
from .lab import TargetAdapter, record_step
from .model import Expectation, LabSurface, Scenario, Variant

Case = tuple[Scenario, TargetAdapter]


@contextmanager
def web_cases() -> Iterator[list[Case]]:
    """Two web scenarios, each with its own local app instance."""
    rows_app = web_app.WebApp("rows").start()
    form_app = web_app.WebApp("form").start()
    try:
        rows_adapter = web_app.WebAdapter(rows_app, "rows")
        rows_intent = record_step(
            rows_adapter,
            variant="A",
            step_id="open-invoice-1042",
            words="Open invoice 1042",
            safety=SafetyClass.REVERSIBLE,
            surface=Surface.WEB,
            row_rule=web_app.ROW_TARGET,
        )
        rows = Scenario(
            scenario_id="web-row-in-list",
            surface=LabSurface.WEB,
            recording="A",
            intent=rows_intent,
            variants=(
                Variant("B", Expectation.SUCCESS),  # adverts inserted above the list
                Variant("C", Expectation.SUCCESS),  # cookie banner
                Variant("D", Expectation.SUCCESS),  # the row moved to page 2
            ),
        )

        form_adapter = web_app.WebAdapter(form_app, "form")
        form_intent = record_step(
            form_adapter,
            variant="A",
            step_id="edit-invoice-1042",
            words="Edit invoice 1042",
            safety=SafetyClass.REVERSIBLE,
            surface=Surface.WEB,
        )
        form = Scenario(
            scenario_id="web-form-button",
            surface=LabSurface.WEB,
            recording="A",
            intent=form_intent,
            variants=(
                Variant("B", Expectation.SUCCESS),  # id removed, label changed
                Variant("C", Expectation.ASKS_USER),  # two identical invoices
                Variant("D", Expectation.SAFE_FAILURE),  # that invoice is gone
            ),
        )
        yield [(rows, rows_adapter), (form, form_adapter)]
    finally:
        rows_app.close()
        form_app.close()


def _tabs_window(variant: str):  # type: ignore[no-untyped-def]
    return qt_window.build_tabs_window(
        tabs={"A": 3, "B": 6, "C": 3, "D": 3}[variant],
        plus_in_strip=True,
        plus_outside=variant == "C",
        twins=variant == "D",
    )


LIST_VARIANTS: dict[str, tuple[tuple[str, str], ...]] = {
    "A": (("item-alpha", "Alpha"), ("item-beta", "Beta"), ("item-gamma", "Gamma")),
    "B": (("item-gamma", "Gamma"), ("item-alpha", "Alpha"), ("item-beta", "Beta")),
    "C": (("item-beta", "Beta"), ("item-beta-duplicate", "Beta")),
    "D": (),
}

EDIT_VARIANTS: dict[str, dict[str, object]] = {
    "A": {"text": "Edit", "object_name": "edit-invoice", "rows": 1, "delayed_ms": 0},
    "B": {"text": "Bearbeiten", "object_name": "edit-invoice", "rows": 1, "delayed_ms": 250},
    "C": {"text": "Bearbeiten", "object_name": "", "rows": 2, "delayed_ms": 0},
}


@contextmanager
def qt_cases(*, settle_ms: int = 350) -> Iterator[list[Case]]:
    """Five offscreen Qt scenarios: tabs, list, dialog, delete, localisation."""
    adapters: list[qt_window.QtAdapter] = []
    try:

        def adapter(builder, truth):  # type: ignore[no-untyped-def]
            built = qt_window.QtAdapter(builder, truth, settle_ms=settle_ms)
            adapters.append(built)
            return built

        tabs = adapter(_tabs_window, {"A": "new-tab", "B": "new-tab", "C": "new-tab", "D": None})
        tabs_intent = record_step(
            tabs,
            variant="A",
            step_id="new-tab",
            words="Open a new tab",
            safety=SafetyClass.READ_ONLY,
            surface=Surface.DESKTOP,
        )
        tabs_scenario = Scenario(
            "qt-tab-plus-moves",
            LabSurface.DESKTOP,
            "A",
            tabs_intent,
            (
                Variant("B", Expectation.SUCCESS),  # five more tabs push "+" right
                Variant("C", Expectation.SUCCESS),  # an identical "+" in the toolbar
                Variant("D", Expectation.ASKS_USER),  # a twin "+" in the same strip
            ),
        )

        listing = adapter(
            lambda variant: qt_window.build_list_window(items=LIST_VARIANTS[variant]),
            {"A": "item-beta", "B": "item-beta", "C": None, "D": None},
        )
        list_intent = record_step(
            listing,
            variant="A",
            step_id="select-beta",
            words="Select Beta",
            safety=SafetyClass.READ_ONLY,
            surface=Surface.DESKTOP,
        )
        list_scenario = Scenario(
            "qt-list-reorders",
            LabSurface.DESKTOP,
            "A",
            list_intent,
            (
                Variant("B", Expectation.SUCCESS),
                Variant("C", Expectation.ASKS_USER),
                Variant("D", Expectation.SAFE_FAILURE),
            ),
        )

        dialog = adapter(
            lambda variant: qt_window.build_dialog_window(dialog=variant != "C"),
            {"A": "confirm-save", "B": "confirm-save", "C": None},
        )
        dialog_intent = record_step(
            dialog,
            variant="A",
            step_id="confirm-save",
            words="Confirm the save",
            safety=SafetyClass.REVERSIBLE,
            surface=Surface.DESKTOP,
        )
        dialog_scenario = Scenario(
            "qt-dialog-sometimes",
            LabSurface.DESKTOP,
            "A",
            dialog_intent,
            (
                Variant("B", Expectation.SUCCESS),
                Variant("C", Expectation.SAFE_FAILURE),  # the dialog never appeared
            ),
        )

        deletion = adapter(
            lambda variant: qt_window.build_delete_window(
                row_delete=True,
                filter_delete=variant == "B",
                twins=variant == "C",
            ),
            {"A": "delete-row", "B": "delete-row", "C": None, "D": "delete-row"},
        )
        delete_intent = record_step(
            deletion,
            variant="A",
            step_id="delete-invoice-1042",
            words="Delete invoice 1042",
            safety=SafetyClass.DESTRUCTIVE,
            surface=Surface.DESKTOP,
        )
        delete_scenario = Scenario(
            "qt-destructive-delete",
            LabSurface.DESKTOP,
            "A",
            delete_intent,
            (
                Variant("B", Expectation.ASKS_USER),  # harmless Delete nearby
                Variant("C", Expectation.ASKS_USER),  # twin Delete in the same row
                Variant("D", Expectation.SAFE_FAILURE, unattended=True),
            ),
        )

        edit = adapter(
            lambda variant: qt_window.build_edit_window(**EDIT_VARIANTS[variant]),  # type: ignore[arg-type]
            {"A": "edit-1", "B": "edit-1", "C": None},
        )
        edit_intent = record_step(
            edit,
            variant="A",
            step_id="edit-invoice-1042",
            words="Edit invoice 1042",
            safety=SafetyClass.REVERSIBLE,
            surface=Surface.DESKTOP,
        )
        edit_scenario = Scenario(
            "qt-localised-delayed",
            LabSurface.DESKTOP,
            "A",
            edit_intent,
            (
                Variant("B", Expectation.SUCCESS),  # translated label, appears late
                Variant("C", Expectation.ASKS_USER),  # translated, no id, duplicates
            ),
        )
        yield [
            (tabs_scenario, tabs),
            (list_scenario, listing),
            (dialog_scenario, dialog),
            (delete_scenario, deletion),
            (edit_scenario, edit),
        ]
    finally:
        for closed in adapters:
            closed.close()

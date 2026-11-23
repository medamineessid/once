"""Machine-readable UI spec: required elements and structural rules.

``docs/UI_SPEC.md`` is the human mirror of this module; a test asserts the two
never drift. The audit reads this module, so a requirement cannot be enforced
in one place and documented in another.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Required elements per page/state, by objectName. Each must exist, be visible,
#: have a non-zero size and lie inside the window (or the page's scroll viewport).
REQUIRED: dict[str, tuple[str, ...]] = {
    "home": (
        "sidebarHomeButton",
        "sidebarAutomationsButton",
        "sidebarActivityButton",
        "sidebarSettingsButton",
        "heroPanel",
        "heroMicro",
        "heroLine",
        "heroLineAccent",
        "heroSubtitle",
        "circleButton",
        "buildButton",
        "statNumber",
        "activityLabel",
    ),
    "automations": (
        "pageBand",
        "pageMicro",
        "pageTitle",
        "pageSubtitle",
        "workflowList",
        "previewSelectedButton",
        "clearDraftsButton",
    ),
    "automations_banner": (
        "banner",
        "bannerTitle",
        "bannerBody",
        "bannerRevealButton",
    ),
    "activity": (
        "activitiesList",
        "detailsContainer",
        "activityDetailsLabel",
    ),
    "settings": (
        "settingsScroll",
        "settingsWidget",
    ),
    "details": (
        "detailsScrollArea",
        "goalLabel",
        "stepsList",
        "approvalPanel",
        "approvalDetails",
    ),
    "permission_panel": (
        "approvalPanel",
        "approvalPanelTitle",
        "approvalStepList",
        "approvalPanelBindingNote",
        "primaryActionButton",
        "secondaryActionButton",
    ),
    "delete_dialog": (
        "deleteConfirmDialog",
        "deleteConfirmTitle",
        "deleteConfirmBody",
        "confirmDeleteButton",
        "cancelDeleteButton",
    ),
    "parameter_dialog": (
        "parameterDialog",
        "dialogBody",
        "fieldLabel",
        "parameterOkButton",
        "parameterCancelButton",
    ),
}

#: Structural rules, by page. Each name maps to a function in scripts.ui_audit.
RULES: dict[str, tuple[str, ...]] = {
    "home": (
        "hero_lines_stacked",
        "hero_micro_gap",
        "record_circle_padding",
        "build_label_centred",
    ),
    "automations": ("row_run_label",),
    "automations_banner": ("row_run_label",),
    "running": ("row_run_label",),
    "all": ("header_gaps", "sidebar_equal_width", "sidebar_focus_not_pill"),
}


@dataclass(frozen=True)
class Bounds:
    """An inclusive range for one measured gap, in logical pixels."""

    minimum: float
    maximum: float

    def holds(self, value: float) -> bool:
        return self.minimum <= value <= self.maximum


#: Page-header gaps (micro label -> title -> subtitle), from the design spec.
HEADER_GAP = Bounds(8.0, 12.0)
#: Gap between the hero micro label and the first display line.
HERO_MICRO_GAP = Bounds(10.0, 14.0)
#: The Record circle is a large target with comfortable padding around its icon.
CIRCLE_MIN_PX = 96
CIRCLE_ICON_MAX_PX = 48
#: Minimum contrast between a button's text and its own background.
MIN_BUTTON_CONTRAST = 3.0
#: Widgets allowed to overlap on purpose: (page, a, b) pairs by objectName.
OVERLAP_ALLOWLIST: frozenset[tuple[str, str, str]] = frozenset()
#: Labels whose crop is part of the design (the hero's second line).
CLIP_ALLOWLIST: frozenset[str] = frozenset({"heroLineAccent"})

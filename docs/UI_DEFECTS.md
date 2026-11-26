# Current UI defects — V1 to V10

Status: current
Last verified: 2026-11-26 · `main f2e6ca3`
Owner: lane B (app experience)


Checked against `603a326` on 2026-11-26. `docs/archive/UX_AUDIT.md` is historical; do
not use its D1–D10 numbers for new work. V1, V5 and V8 are fixed (PR #29 and
PR #27); V2, V3, V4, V6, V7, V9 and V10 are unchanged. Reference captures are in
`docs/ui-reference/defects/` (app window only, never a full desktop; generated
by `scripts/capture_ui_defects.py` from synthetic fixtures at 960x600 and
1920x1020, and not yet reviewed by a person — see that folder's README).

## Blocking the app

### V1 — Delete confirmation buttons are unreadable — **FIXED** (PR #29)
Was: a plain `QMessageBox` whose buttons the platform style painted, so Delete
rendered white on near-white and Cancel was faint. Now `DeleteConfirmDialog`
(`ui/components/delete_confirm.py:58`) subclasses `ConfirmDialog`
(`ui/components/dialog.py:112`): Delete is a filled danger button with white
text, Cancel is an outlined navy button, both have a focus state, and Cancel is
the default. Pinned by `tests/test_confirm_dialog.py`; evidence level **tests
only** — no person has reviewed the after capture yet. Before capture:
`docs/ui-reference/defects/delete-dialog-960x600.png`.

### V2 — Permission panel overlaps and cuts off actions
`ui/components/approval_panel.py:82-129` stacks paragraph, action list, footnote
and both buttons in one `QVBoxLayout` with no scroll area; the panel is added to
the page at `ui/pages/my_automations.py:257-260`. "Approve for this run" and "Do
not run" are cut off. Fix: vertical layout inside a scroll area or modal dialog
with both buttons always visible. See
`docs/ui-reference/defects/my-automations-960x600.png` and
`my-automations-1920x1020.png`.

### V4 — Rows say "Running..." while waiting for approval
`ui/pages/my_automations.py:182` calls `set_running`, and `:561-563` sets the
"Running '…'" text before the worker exists. Fix: keep "Run" (disabled while
approval is pending); show "Running..." only on the row whose worker started.
See `docs/ui-reference/defects/my-automations-960x600.png`.

## Layout

### V3 — Preview / Clear drafts floats over a row
`ui/pages/my_automations.py:238-255` adds the list first and the two controls
after it, with styling that lets the controls overlap a row. Fix: put them in an
explicit toolbar row above `workflowList`. See
`docs/ui-reference/defects/my-automations-960x600.png`.

### V5 — Hover/press animation escapes the button rectangle — **FIXED** (PR #27)
Was: the button painted itself scaled about its centre, so the border left the
widget rectangle, and `HOVER_SCALE`/`PRESS_SCALE` lived in the styles module.
Now `ui/components/buttons.py` has no `paintEvent` override and no scale
(grep, 2026-11-26): hover changes colour and border, the arrow shifts 4px, press
moves 1px inward, and everything stays inside the rectangle. Pinned by
`tests/test_layout_geometry.py` (edge midpoints stay opaque at rest, hover and
press) and `tests/test_design_v4.py`; evidence level **tests only**. Before
capture: `docs/ui-reference/defects/settings-960x600.png`.

### V8 — Sidebar widths and focus outline disagree — **FIXED** (PR #27)
Was: rows had inconsistent widths and focus painted a second pill. Now rows
expand to the rail (`QSizePolicy.Expanding`, `ui/components/sidebar_item.py:91`),
the pill spans the full row, and `_keyboard_focus` is set only for Tab, Backtab
and Shortcut focus reasons (`:123`), so keyboard focus is an outline and a click
is not. Verified by `tests/test_layout_geometry.py`; evidence level **tests
only**. Before capture: `docs/ui-reference/defects/home-960x600.png`.

## Polish

### V6 — Home hero spacing and alignment
`ui/components/hero.py:76-84` positions the two display lines with absolute
`move()`, so they are not a stacked, left-aligned pair; the micro label at
`:127-131` touches the text, and Record/Build spacing at `:146-159` is uneven.
See `docs/ui-reference/defects/home-960x600.png` and `home-1920x1020.png`.

### V7 — Page header band gaps are 8px
`ui/components/band.py:68-105` uses `SPACING_XS`/`SPACING_SM` between micro,
title and subtitle, giving 8–12px gaps. Fix: one 12px rhythm. See
`docs/ui-reference/defects/home-960x600.png` and
`docs/ui-reference/defects/my-automations-1920x1020.png`.

### V9 — "Files need attention" has no detail
`ui/pages/my_automations.py:679` shows the generic body from
`ui/strings.py:71-75`; it names no file, no reason and offers no "Reveal in
folder" action. Expected example: "vscode-session.json: unknown launch fields:
application". See `docs/ui-reference/defects/my-automations-960x600.png` and
`my-automations-1920x1020.png`.

### V10 — Step-card chip overlaps the title
`ui/pages/review.py:227-250` adds the kind chip and the editable title to the
same horizontal row with no reserved width, so the chip covers the title. See
`docs/ui-reference/defects/details-960x600.png` and `details-1920x1020.png`.

## Old D1–D10 status (code inspection, not a visual check)

| old item | status | evidence |
| --- | --- | --- |
| D1 failed runs hidden on Home | FIXED | `ui/pages/home.py:181-192` reads all history statuses |
| D2 raw ids on Home | FIXED | `ui/pages/home.py:186` uses `friendly_run_name` |
| D3 centred 260px actions column | FIXED | `ui/pages/home.py:66-73`, `ui/components/hero.py:123-159` |
| D4 modal Run confirmation | FIXED | `ui/pages/my_automations.py:136-146` uses `InlineConfirm` |
| D5 raw validation error text | PARTIAL | banner at `ui/pages/my_automations.py:613`; details still `Error: …` at `:612` |
| D6 Activity not refreshed after run | PARTIAL | editor path refreshes at `ui/shell.py:520`; My automations path only at `ui/pages/my_automations.py:606` |
| D7 raw ids on Activity | FIXED | `ui/pages/activity.py:184-187` |
| D8 no timestamps / empty state | FIXED | `ui/pages/activity.py:171-177,187` |
| D9 Create dead-end modal | FIXED | `ui/pages/create_automation.py:64-65`, `ui/shell.py:540-543` |
| D10 modal information/exec in Settings | FIXED | `ui/pages/settings.py:79,137,149` use `Banner`; no `QMessageBox`/`exec` in current Settings (grep) |

D5 and D6 remain as follow-ups; they are not V-items and are not in a brief in
this PR.

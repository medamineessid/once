# Current UI defects — V1 to V10

Checked against `8c91ea7` on 2026-11-23. `docs/UX_AUDIT.md` is historical; do
not use its D1–D10 numbers for new work. Reference captures are in
`docs/ui-reference/` (repo captures, app window only, not full desktop; captured
but not visually reviewed by this model): `home.png`, `my-automations.png`,
`details.png`, `settings.png`.

## Blocking the app

### V1 — Delete confirmation buttons are unreadable
`ui/components/delete_confirm.py:55-72` builds a plain `QMessageBox` with
default-painted buttons; the Delete button renders white on near-white and
Cancel is faint. Fix: use design tokens — Delete is a filled danger button with
readable text, Cancel is an outlined navy button. See `details.png`.

### V2 — Permission panel overlaps and cuts off actions
`ui/components/approval_panel.py:82-129` stacks paragraph, action list, footnote
and both buttons in one `QVBoxLayout` with no scroll area; the panel is added to
the page at `ui/pages/my_automations.py:257-260`. "Approve for this run" and "Do
not run" are cut off. Fix: vertical layout inside a scroll area or modal dialog
with both buttons always visible. See `my-automations.png`.

### V4 — Rows say "Running..." while waiting for approval
`ui/pages/my_automations.py:182` calls `set_running`, and `:561-563` sets the
"Running '…'" text before the worker exists. Fix: keep "Run" (disabled while
approval is pending); show "Running..." only on the row whose worker started.

## Layout

### V3 — Preview / Clear drafts floats over a row
`ui/pages/my_automations.py:238-255` adds the list first and the two controls
after it, with styling that lets the controls overlap a row. Fix: put them in an
explicit toolbar row above `workflowList`. See `my-automations.png`.

### V5 — Hover/press animation escapes the button rectangle
`ui/components/buttons.py:120-134,181-189` drives a painted scale and
`ui/styles/__init__.py:447-494` supplies hover/press borders; on Settings,
"Configure checker..." shows a half-drawn border. Fix: animate colours or paint
only inside the rectangle; never scale widgets. See `settings.png`.

### V8 — Sidebar widths and focus outline disagree
`ui/components/sidebar_item.py:129-140` paints the active/hover pill and
`:174-176` paints focus as an outline; items have inconsistent widths. Fix: one
item width and an outline only for keyboard focus, never a second pill.

## Polish

### V6 — Home hero spacing and alignment
`ui/components/hero.py:76-84` positions the two display lines with absolute
`move()`, so they are not a stacked, left-aligned pair; the micro label at
`:127-131` touches the text, and Record/Build spacing at `:146-159` is uneven.
See `home.png`.

### V7 — Page header band gaps are 8px
`ui/components/band.py:68-105` uses `SPACING_XS`/`SPACING_SM` between micro,
title and subtitle, giving 8–12px gaps. Fix: one explicit 16px rhythm.

### V9 — "Files need attention" has no detail
`ui/pages/my_automations.py:679` shows the generic body from
`ui/strings.py:71-75`; it names no file, no reason and offers no "Reveal in
folder" action. Expected example: "vscode-session.json: unknown launch fields:
application". See `my-automations.png`.

### V10 — Step-card chip overlaps the title
`ui/pages/review.py:227-250` adds the kind chip and the editable title to the
same horizontal row with no reserved width, so the chip covers the title. See
`details.png`.

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

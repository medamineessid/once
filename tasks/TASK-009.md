# TASK-009 — Fix layout defects V3, V5 and V8

Lane: `ui` · Difficulty: `normal` · Owner review required: `yes` · Label: `lane/ui` · Size: `M`

## Status

- **V5 — fixed** by PR #27 (merged): no painted scale remains in
  `ui/components/buttons.py`; hover and press change colour, border and a 4px
  arrow shift only. Pinned by `tests/test_layout_geometry.py` and
  `tests/test_design_v4.py`. Evidence level **tests only**.
- **V8 — fixed** by PR #27 (merged): sidebar rows expand to the rail width and
  the outline appears only for keyboard focus
  (`ui/components/sidebar_item.py:91,123`).
- **V3 — open:** the Preview / Clear drafts controls are still added after the
  list, not as a toolbar row above `workflowList`.
- Tracking issue: #17, still open for V3.

## Goal

The Preview / Clear drafts controls become a real toolbar row above the list,
button hover and press stay inside the widget rectangle, and sidebar items share
one width with a keyboard-only focus outline. See `docs/UI_DEFECTS.md` and the
app-window captures in `docs/ui-reference/`.

## Files allowed

- `ui/pages/my_automations.py`
- `ui/components/buttons.py`
- `ui/components/sidebar_item.py`
- `ui/components/verifier_panel.py`
- `ui/styles/__init__.py` (explicitly allowed for V3/V5/V8 tokens)
- `ui/strings.py`
- `tests/test_shell.py`
- `tests/test_styles.py`
- `tests/test_reduced_motion.py`
- `tests/test_p2_shell.py`
- `docs/ui-reference/` (before/after app-window captures only)

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`
- `ui/pages/home.py`, `ui/pages/activity.py`, `ui/pages/settings.py`,
  `ui/pages/review.py`, `ui/components/hero.py`, `ui/components/band.py`,
  `ui/components/delete_confirm.py`, `ui/components/approval_panel.py`
- `.github/`, `scripts/verify.ps1`, `scripts/check_log_append_only.py`
- `docs/ai_engineering_log.md`, `docs/STATE.md`
- step schema, workflow validators, approval code

## Acceptance commands (run yourself)

```
python -m pytest -q tests/test_shell.py tests/test_styles.py tests/test_reduced_motion.py tests/test_p2_shell.py
ruff check .
ruff format --check .
```

The owner ran these three commands on this base and they pass. Once TASK-007
has landed, also run `python scripts/ui_audit.py` and paste its report.

## Screenshots

Screenshots before and after, app window only, one sentence per image: the
before images are `docs/ui-reference/defects/my-automations-960x600.png`,
`settings-960x600.png` and `home-960x600.png` (the V8 sidebar rail is the same
on every page). Add the matching after captures at 960x600 and 1920x1020 and
say which overlap, half-drawn border or wrong outline was removed. A person
opens every image and writes its one sentence; an unreviewed capture is not
evidence.

## Out of scope

Changing the list contents, resolver policy, or any controller/service call.
Do not scale widgets to animate them.

## Notes

V5 explicitly includes "Configure checker..." on Settings. V8 focus must be
outline-only for keyboard focus and must never look like the active pill.

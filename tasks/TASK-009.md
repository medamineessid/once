# TASK-009 — Fix layout defects V3, V5 and V8

Lane: `ui` · Difficulty: `normal` · Owner review required: `yes` · Label: `lane/ui` · Size: `M`

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

Screenshots before and after, app window only, one sentence per image: use
`docs/ui-reference/my-automations.png` and `docs/ui-reference/settings.png` as
the before images, add the matching after captures, and say which overlap,
half-drawn border or wrong outline was removed.

## Out of scope

Changing the list contents, resolver policy, or any controller/service call.
Do not scale widgets to animate them.

## Notes

V5 explicitly includes "Configure checker..." on Settings. V8 focus must be
outline-only for keyboard focus and must never look like the active pill.

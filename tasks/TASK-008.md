# TASK-008 — Fix blocking defects V1, V2 and V4

Lane: `ui` · Difficulty: `normal` · Owner review required: `yes` · Label: `lane/ui` · Size: `M`

## Goal

Delete confirmation becomes readable, the permission panel shows both actions
and all its text, and a row stays "Run" (disabled) while waiting for approval.
These are the three V-defects that stop a user finishing a normal action. See
`docs/UI_DEFECTS.md` and the app-window captures in `docs/ui-reference/`.

## Files allowed

- `ui/components/delete_confirm.py`
- `ui/components/approval_panel.py`
- `ui/components/confirm.py`
- `ui/pages/my_automations.py`
- `ui/strings.py`
- `ui/styles/__init__.py` (explicitly allowed for V1/V2 tokens)
- `tests/test_delete_flows.py`
- `tests/test_b2_approval_panel.py`
- `tests/test_shell.py`
- `tests/test_contrast.py`
- `docs/ui-reference/` (before/after app-window captures only)

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`
- `ui/pages/home.py`, `ui/pages/activity.py`, `ui/pages/settings.py`,
  `ui/pages/review.py`, `ui/components/hero.py`, `ui/components/band.py`,
  `ui/components/sidebar_item.py`
- `.github/`, `scripts/verify.ps1`, `scripts/check_log_append_only.py`
- `docs/ai_engineering_log.md`, `docs/STATE.md`
- step schema, workflow validators, approval code

## Acceptance commands (run yourself)

```
python -m pytest -q tests/test_delete_flows.py tests/test_b2_approval_panel.py tests/test_shell.py tests/test_contrast.py
ruff check .
ruff format --check .
```

The owner ran these three commands on this base and they pass. Once TASK-007
has landed, also run `python scripts/ui_audit.py` and paste its report.

## Screenshots

Screenshots before and after, app window only, one sentence per image: the
before images are `docs/ui-reference/defects/delete-dialog-960x600.png`,
`delete-dialog-1920x1020.png`, `my-automations-960x600.png` and
`my-automations-1920x1020.png`. Add matching `-after` captures at both sizes
and say what was unreadable or cut off and what is now readable and visible. A
person opens every image and writes its one sentence; an unreviewed capture is
not evidence.

## Out of scope

Changing the delete policy, the approval gate, or the resolver. No new
dependency and no full-desktop capture.

## Notes

V1 needs a filled danger Delete and outlined navy Cancel using tokens, not
hard-coded colours. V2 needs a scroll area or modal with both buttons always
visible. V4 must not change when a run actually starts.

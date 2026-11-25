# TASK-011 — V5 animation follow-ups from the audit

Lane: `ui` · Difficulty: `good-first-task` · Owner review required: `yes` · Label: `lane/ui` · Size: `S`

## Goal

Close the remaining V5 cases once the audit is available: any hover, press or
focus animation that still paints outside a button's rectangle, starting with
"Configure checker..." on Settings. The audit helps verify this defect; it is
not required to start the work. See `docs/UI_DEFECTS.md`.

## Files allowed

- `ui/components/buttons.py`
- `ui/components/verifier_panel.py`
- `ui/pages/settings.py`
- `ui/styles/__init__.py` (explicitly allowed for V5 tokens)
- `tests/test_styles.py`
- `tests/test_reduced_motion.py`
- `tests/test_shell.py`
- `docs/ui-reference/` (before/after app-window captures only)

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`
- `ui/pages/home.py`, `ui/pages/my_automations.py`, `ui/pages/activity.py`,
  `ui/pages/review.py`, `ui/components/hero.py`, `ui/components/band.py`,
  `ui/components/sidebar_item.py`
- `.github/`, `scripts/verify.ps1`, `scripts/check_log_append_only.py`
- `docs/ai_engineering_log.md`, `docs/STATE.md`
- step schema, workflow validators, approval code

## Acceptance commands (run yourself)

```
python -m pytest -q tests/test_styles.py tests/test_reduced_motion.py tests/test_shell.py
ruff check .
ruff format --check .
```

The owner ran these three commands on this base and they pass. Once TASK-007
has landed, also run `python scripts/ui_audit.py` and paste its report.

## Screenshots

Screenshots before and after, app window only, one sentence per image: the
before image is `docs/ui-reference/defects/settings-960x600.png` and its
1920x1020 twin. Add the after captures and say which border or animation no
longer leaves the rectangle. A person opens every image and writes its one
sentence; an unreviewed capture is not evidence.

## Out of scope

Changing button semantics, adding a new animation library, or touching other
V-defects already assigned in TASK-008..010.

## Notes

TASK-009 fixes the first V5 cases. This brief takes the follow-ups the audit
reports. If the audit finds nothing new, say so and close the brief with the
pasted audit report rather than inventing a change.

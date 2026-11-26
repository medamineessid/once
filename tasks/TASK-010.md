# TASK-010 — Fix polish defects V6, V7, V9 and V10

Lane: `ui` · Difficulty: `normal` · Owner review required: `yes` · Label: `lane/ui` · Size: `M`

## Status

Not started (2026-11-26). V6, V7, V9 and V10 are unchanged in the code; the
tracking issue is #18.

## Goal

Stack and left-align the Home hero lines with clear spacing, give page bands a
16px text rhythm, show real file names and reasons in the attention banner with
a Reveal action, and stop the step-card chip covering its title. See
`docs/UI_DEFECTS.md` and `docs/ui-reference/`.

## Files allowed

- `ui/components/hero.py`
- `ui/components/band.py`
- `ui/pages/home.py`
- `ui/pages/my_automations.py`
- `ui/pages/review.py`
- `ui/strings.py`
- `ui/styles/__init__.py` (explicitly allowed for V6/V7/V9/V10 tokens)
- `tests/test_design_v4.py`
- `tests/test_shell.py`
- `tests/test_activity_page.py`
- `tests/test_contrast.py`
- `docs/ui-reference/` (before/after app-window captures only)

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`
- `ui/pages/settings.py`, `ui/pages/create_automation.py`,
  `ui/components/buttons.py`, `ui/components/sidebar_item.py`,
  `ui/components/delete_confirm.py`, `ui/components/approval_panel.py`
- `.github/`, `scripts/verify.ps1`, `scripts/check_log_append_only.py`
- `docs/ai_engineering_log.md`, `docs/STATE.md`
- step schema, workflow validators, approval code

## Acceptance commands (run yourself)

```
python -m pytest -q tests/test_design_v4.py tests/test_shell.py tests/test_activity_page.py tests/test_contrast.py
ruff check .
ruff format --check .
```

The owner ran these three commands on this base and they pass. Once TASK-007
has landed, also run `python scripts/ui_audit.py` and paste its report.

## Screenshots

Screenshots before and after, app window only, one sentence per image: the
before images are `docs/ui-reference/defects/home-960x600.png`,
`details-960x600.png` and `my-automations-960x600.png`, plus their 1920x1020
twins. Add the matching after captures and say what spacing or overlap was
fixed in each. A person opens every image and writes its one sentence; an
unreviewed capture is not evidence.

## Out of scope

Changing run history, file scanning, or the step schema. The Reveal action must
be read-only and must not open or modify a file.

## Notes

V9 example text: "vscode-session.json: unknown launch fields: application".
Keep machine paths out of the banner and the screenshots.

# TASK-013 — Settings switch screen

Lane: `ui` · Difficulty: `normal` · Owner review required: `yes` · Label: `lane/ui` · Size: `M`

## Goal

Settings uses one consistent switch component for real, already-supported
options, with plain-language help and no placeholder controls that look live.
The screen is fed by local sample data under `tests/fixtures/` (and
`tests/ui_fixtures/` once TASK-007 lands), so it can be built and reviewed
without waiting for another task. This finishes the Settings part of the app
experience without adding settings the controller does not implement.

## Files allowed

- `ui/components/switch.py` (new)
- `ui/pages/settings.py`
- `ui/strings.py`
- `ui/styles/__init__.py` (explicitly allowed for switch tokens)
- `tests/fixtures/`
- `tests/ui_fixtures/`
- `tests/test_shell.py`
- `tests/test_styles.py`
- `docs/ui-reference/` (before/after app-window captures only)

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`
- `ui/shell.py`, `ui/pages/home.py`, `ui/pages/my_automations.py`,
  `ui/pages/activity.py`, `ui/pages/create_automation.py`
- `.github/`, `scripts/verify.ps1`, `scripts/check_log_append_only.py`
- `docs/ai_engineering_log.md`, `docs/STATE.md`
- step schema, workflow validators, approval code

## Acceptance commands (run yourself)

```
python -m pytest -q tests/test_shell.py tests/test_styles.py
ruff check .
ruff format --check .
```

The owner ran these three commands on this base and they pass. Once TASK-007
has landed, also run `python scripts/ui_audit.py` and paste its report. The
audit helps verify the screen; it is not required to start.

## Screenshots

Screenshots before and after, app window only, one sentence per image: the
before image is `docs/ui-reference/defects/settings-960x600.png` and its
1920x1020 twin. Add the after captures at 960x600 and 1920x1020 and say which
fake or inconsistent control was replaced by an honest switch or unavailable
text. A person opens every image and writes its one sentence; an unreviewed
capture is not evidence.

## Out of scope

Adding a smart-replay toggle that the app does not honour, changing
configuration storage, or adding new dependencies.

## Notes

If an option is not wired to the controller, show it as unavailable text, not
as a switch. Do not imply that observation-only replay is executable. Sample
data must stay inside `tests/fixtures/` and must not touch the real
`%LOCALAPPDATA%/Once` folder.

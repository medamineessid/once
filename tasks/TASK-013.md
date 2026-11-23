# TASK-013 — Settings switch screen (BLOCKED)

Lane: `ui` · Difficulty: `normal` · Owner review required: `yes` · Label: `lane/ui` · Size: `M`

## Status: BLOCKED

Blocked by TASK-011, which first removes the modal Settings dialogs.

## Goal

Settings uses one consistent switch component for real, already-supported
options, with plain-language help and no placeholder controls that look live.
This finishes the Settings part of the app experience without adding settings
the controller does not implement.

## Files allowed

- `ui/components/switch.py` (new)
- `ui/pages/settings.py`
- `ui/strings.py`
- `ui/styles/__init__.py` (only for switch tokens)
- `tests/test_shell.py`
- `tests/test_styles.py`

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`
- `ui/shell.py`, `ui/pages/home.py`, `ui/pages/my_automations.py`,
  `ui/pages/activity.py`, `ui/pages/create_automation.py`
- `.github/`, `scripts/`, `docs/ai_engineering_log.md`, `docs/STATE.md`
- step schema, workflow validators, approval code

## Acceptance commands (run yourself)

```
python -m pytest -q tests/test_shell.py tests/test_styles.py
ruff check .
ruff format --check .
```

The owner ran these three commands on this base and they pass. Paste your real
summary lines in the PR.

## Screenshots

App-window captures of Settings at 960x600 and 1280x800, at 100% and 150%
scale, through the real `app.py` path. One sentence each versus
`docs/UI_SPEC.md`.

## Out of scope

Adding a smart-replay toggle that the app does not honour, changing
configuration storage, or adding new dependencies.

## Notes

If an option is not wired to the controller, show it as unavailable text, not
as a switch. Do not imply that observation-only replay is executable.

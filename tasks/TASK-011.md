# TASK-011 — Fix UX defects D9–D10 on Create and Settings (BLOCKED)

Lane: `ui` · Difficulty: `normal` · Owner review required: `yes` · Label: `lane/ui` · Size: `S`

## Status: BLOCKED

Blocked by TASK-007. The audit must be green before its findings can be used to
prove these fixes.

## Goal

The create flow no longer dead-ends behind a blocking modal, and Settings shows
information inline instead of through modal dialogs. This removes D9 and D10
from `docs/UX_AUDIT.md` and gives the later Settings switch screen a base.

## Files allowed

- `ui/pages/create_automation.py`
- `ui/pages/settings.py`
- `ui/strings.py`
- `ui/styles/__init__.py` (only for inline panel/banner tokens)
- `tests/test_shell.py`
- `tests/test_p2_shell.py`

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`
- `ui/shell.py`, `ui/pages/home.py`, `ui/pages/my_automations.py`,
  `ui/pages/activity.py`
- `.github/`, `scripts/`, `docs/ai_engineering_log.md`, `docs/STATE.md`
- step schema, workflow validators, approval code

## Acceptance commands (run yourself)

```
python -m pytest -q tests/test_shell.py tests/test_p2_shell.py
ruff check .
ruff format --check .
```

The owner ran these three commands on this base and they pass. Paste your real
summary lines in the PR.

## Screenshots

App-window captures of Create and Settings after a save/cancel at 960x600 and
1280x800 through the real `app.py` path. One sentence each versus
`docs/UI_SPEC.md`.

## Out of scope

Building the Settings switch screen (TASK-013), changing configuration storage,
or restoring the typed-description path.

## Notes

Keep the existing "observation only" wording for recording; this task changes
presentation, not replay capability.

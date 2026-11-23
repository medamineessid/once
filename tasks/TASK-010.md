# TASK-010 — Fix UX defects D7–D8 on Activity (BLOCKED)

Lane: `ui` · Difficulty: `good-first-task` · Owner review required: `yes` · Label: `lane/ui` · Size: `S`

## Status: BLOCKED

Blocked by TASK-007. The audit must be green before its findings can be used to
prove these fixes.

## Goal

Activity shows automation names and statuses instead of raw ids, and gives
timestamps plus a useful empty state with a next action. This removes D7 and D8
from `docs/UX_AUDIT.md` using data the controller already persists.

## Files allowed

- `ui/pages/activity.py`
- `ui/strings.py`
- `ui/styles/__init__.py` (only for row/empty-state tokens)
- `tests/test_activity_page.py`
- `tests/test_shell.py`

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`
- `ui/shell.py`, `ui/pages/home.py`, `ui/pages/my_automations.py`,
  `ui/pages/settings.py`, `ui/pages/create_automation.py`
- `.github/`, `scripts/`, `docs/ai_engineering_log.md`, `docs/STATE.md`
- step schema, workflow validators, approval code

## Acceptance commands (run yourself)

```
python -m pytest -q tests/test_activity_page.py tests/test_shell.py
ruff check .
ruff format --check .
```

The owner ran these three commands on this base and they pass. Paste your real
summary lines in the PR.

## Screenshots

App-window captures of a populated and an empty Activity page at 960x600 and
1280x800 through the real `app.py` path. One sentence each versus
`docs/UI_SPEC.md`.

## Out of scope

Adding new history fields to storage, changing run persistence, or inventing a
timestamp where none exists.

## Notes

If a name cannot be resolved from persisted data, say "Unnamed automation" in
plain language; never print the raw id in the default row text.

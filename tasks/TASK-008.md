# TASK-008 — Fix UX defects D1–D3 on Home (BLOCKED)

Lane: `ui` · Difficulty: `good-first-task` · Owner review required: `yes` · Label: `lane/ui` · Size: `S`

## Status: BLOCKED

Blocked by TASK-007. The audit must be green before its findings can be used to
prove these fixes.

## Goal

Home shows failed runs as plainly as successful ones, names automations instead
of ids, and lays the action panel out on the shared top-aligned page template.
This removes D1, D2 and D3 from `docs/UX_AUDIT.md`.

## Files allowed

- `ui/pages/home.py`
- `ui/strings.py`
- `ui/styles/__init__.py` (only for Home layout/contrast tokens)
- `tests/test_shell.py`
- `tests/test_p2_shell.py`
- `tests/test_contrast.py`

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`
- `ui/shell.py`, `ui/pages/my_automations.py`, `ui/pages/activity.py`,
  `ui/pages/settings.py`, `ui/pages/create_automation.py`
- `.github/`, `scripts/`, `docs/ai_engineering_log.md`, `docs/STATE.md`
- step schema, workflow validators, approval code

## Acceptance commands (run yourself)

```
python -m pytest -q tests/test_shell.py tests/test_p2_shell.py tests/test_contrast.py
ruff check .
ruff format --check .
```

The owner ran these three commands on this base and they pass. Paste your real
summary lines in the PR.

## Screenshots

App-window captures of Home at 960x600 and 1280x800, at 100% and 150% scale,
through the real `app.py` path. One sentence each versus `docs/UI_SPEC.md`.

## Out of scope

Changing run statuses in the engine, adding new strings that are not in
`ui/strings.py`, or touching other pages.

## Notes

Keep the failed-run wording honest: a failed run is still a real history row,
not a success with a different colour.

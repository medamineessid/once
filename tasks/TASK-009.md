# TASK-009 — Fix UX defects D4–D6 on My automations (BLOCKED)

Lane: `ui` · Difficulty: `normal` · Owner review required: `yes` · Label: `lane/ui` · Size: `S`

## Status: BLOCKED

Blocked by TASK-007. The audit must be green before its findings can be used to
prove these fixes.

## Goal

The Run action confirms inline instead of with a modal question, validation
errors say what to do next, and finishing a run refreshes Activity. This removes
D4, D5 and D6 from `docs/UX_AUDIT.md` without changing run semantics.

## Files allowed

- `ui/pages/my_automations.py`
- `ui/strings.py`
- `ui/styles/__init__.py` (only for inline confirm/banner tokens)
- `tests/test_my_automations_page.py`
- `tests/test_activity_page.py`
- `tests/test_shell.py`

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`
- `ui/shell.py`, `ui/pages/home.py`, `ui/pages/activity.py`,
  `ui/pages/settings.py`, `ui/pages/create_automation.py`
- `.github/`, `scripts/`, `docs/ai_engineering_log.md`, `docs/STATE.md`
- step schema, workflow validators, approval code

## Acceptance commands (run yourself)

```
python -m pytest -q tests/test_my_automations_page.py tests/test_activity_page.py tests/test_shell.py
ruff check .
ruff format --check .
```

The owner ran these three commands on this base and they pass. Paste your real
summary lines in the PR.

## Screenshots

App-window captures of the inline confirm and an error banner at 960x600 and
1280x800 through the real `app.py` path. One sentence each versus
`docs/UI_SPEC.md`.

## Out of scope

Changing the controller's run method, the validator messages themselves, or the
approval gate.

## Notes

An inline confirm must require a second deliberate click; do not replace the
modal with a single click that starts a run.

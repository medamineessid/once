# TASK-012 — Pick-one dialog and sample-fed run report view (BLOCKED)

Lane: `ui` · Difficulty: `normal` · Owner review required: `yes` · Label: `lane/ui` · Size: `M`

## Status: BLOCKED

Blocked by TASK-007 for the sample-data fixtures, and by TASK-009 for the run
data shown in the report. Do not build either from invented data.

## Goal

When a target is ambiguous, the user gets a non-modal picker that explains the
choices; after a run, a read-only report view shows the same plain-language
outcome and evidence from the sample data. Nothing in either view executes an
action.

## Files allowed

- `ui/components/pick_one_dialog.py` (new)
- `ui/pages/run_report.py` (new)
- `ui/shell.py` (only to wire the two views)
- `ui/strings.py`
- `ui/styles/__init__.py` (only for picker/report tokens)
- `tests/ui_fixtures/`
- `tests/test_run_report.py` (new)
- `tests/test_shell.py`
- `tests/test_b4_status_labels.py`

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`
- `ui/pages/home.py`, `ui/pages/my_automations.py`, `ui/pages/activity.py`,
  `ui/pages/settings.py`, `ui/pages/create_automation.py`
- `.github/`, `scripts/`, `docs/ai_engineering_log.md`, `docs/STATE.md`
- step schema, workflow validators, approval code

## Acceptance commands (run yourself)

```
python -m pytest -q tests/test_shell.py tests/test_b4_status_labels.py tests/test_contrast.py
ruff check .
ruff format --check .
```

The owner ran these three commands on this base and they pass. Add the new
`tests/test_run_report.py` to the pytest command before claiming done.

## Screenshots

App-window captures of the picker with two identical targets and of the report
with one successful and one observation-only step, at 960x600 and 1280x800.
One sentence each versus `docs/UI_SPEC.md`.

## Out of scope

Adding a new resolver, changing ambiguity policy, mutating targets from the
picker, or calling a controller method that runs a workflow from these views.

## Notes

The picker returns a reviewed selection; it never calls a mutating action
itself. The report view is read-only and must not show raw internal ids by
default.

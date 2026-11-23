# TASK-012 — Pick-one dialog and sample-fed run report view

Lane: `ui` · Difficulty: `normal` · Owner review required: `yes` · Label: `lane/ui` · Size: `M`

## Goal

When a target is ambiguous, show a non-modal picker that explains the choices;
after a run, show a read-only report with the same plain-language outcome and
evidence. Both views are fed by local sample data under `tests/fixtures/`, plus
`tests/ui_fixtures/` after TASK-007 lands. Neither view executes an action.

## Files allowed

- `ui/components/pick_one_dialog.py` (new)
- `ui/pages/run_report.py` (new)
- `ui/shell.py` (only to wire the two views)
- `ui/strings.py`
- `ui/styles/__init__.py` (explicitly allowed for picker/report tokens)
- `tests/fixtures/`
- `tests/ui_fixtures/`
- `tests/test_run_report.py` (new)
- `tests/test_shell.py`
- `tests/test_b4_status_labels.py`
- `docs/ui-reference/` (before/after app-window captures only)

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`
- `ui/pages/home.py`, `ui/pages/my_automations.py`, `ui/pages/activity.py`,
  `ui/pages/settings.py`, `ui/pages/create_automation.py`,
  `ui/pages/review.py`
- `.github/`, `scripts/verify.ps1`, `scripts/check_log_append_only.py`
- `docs/ai_engineering_log.md`, `docs/STATE.md`
- step schema, workflow validators, approval code

## Acceptance commands (run yourself)

```
python -m pytest -q tests/test_shell.py tests/test_b4_status_labels.py tests/test_contrast.py
ruff check .
ruff format --check .
```

The owner ran these three commands on this base and they pass. Add the new
`tests/test_run_report.py` to the pytest command before claiming done. Once
TASK-007 has landed, also run `python scripts/ui_audit.py` and paste its report.

## Screenshots

Screenshots before and after, app window only, one sentence per image: use the
current shell as before, then show the picker with two identical targets and the
report with one successful and one observation-only step.

## Out of scope

Changing the resolver or ambiguity policy, mutating targets from the picker, or
claiming a real desktop run from sample data.

## Notes

The picker returns a reviewed selection. The report view must not show raw
internal ids by default and must never execute a workflow.

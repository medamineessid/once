# TASK-014 — New scenario cases: Chrome-style tabs and lower result rows

Lane: `tests` · Difficulty: `normal` · Owner review required: `no` · Label: `lane/tests` · Size: `M`

## Goal

Add two deterministic cases to the scenario lab: one where extra Chrome-style
tabs push the "+" control, and one where the matching result sits lower on the
page after adverts. Both must be recorded from a real local surface and replayed
only through the existing lab; no resolver or policy change.

## Files allowed

- `tests/scenarios/qt_window.py`
- `tests/scenarios/web_app.py`
- `tests/scenarios/catalog.py`
- `tests/test_scenarios_lab.py`

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`, `ui/`
- `.github/`, `scripts/`, `docs/ai_engineering_log.md`, `docs/STATE.md`
- step schema, workflow validators, approval code

## Acceptance commands (run yourself)

```
python -m pytest -q tests/test_scenarios_lab.py
ruff check .
ruff format --check .
```

The owner ran these three commands on this base and they pass. Paste the real
summary lines in the PR.

## Screenshots

None — offscreen lab fixtures only. Save any diagnostic PNGs under
`shots/tmp/`, never as evidence of a real desktop run.

## Out of scope

Changing resolver weights, `MIN_CONFIDENCE`, `CLEAR_GAP`, existing expectations,
or any assertion in another test file.

## Notes

The Chrome-style case belongs beside `qt-tab-plus-moves`; the lower-result case
belongs beside the web row scenario. If a new case fails, report it; do not tune
the policy to make it pass.

# TASK-001 — Scenario-lab fixtures for existing smart replay cases

Lane: `tests` · Difficulty: `normal` · Owner review required: `no` · Label: `lane/tests`

## Goal

Add fixture data so the scenario lab can be replayed without touching any test
expectation. The lab is the deterministic side of smart replay:

- `tests/test_scenarios_lab.py` — the runner that walks `tests/scenarios/` and
  score/act each recorded step;
- `tests/scenarios/catalog.py` — the list of registered fixtures;
- `tests/scenarios/<name>.py` — one fixture per case.

Adding cases here does not change the resolver, the policy thresholds, or any
existing assertion.

## Files allowed

- `tests/scenarios/`
- `tests/test_scenarios_lab.py`

## Files forbidden

- `engine/`, `storage/`, `controller/`, `integrations/`
- `.github/`, `scripts/`, `docs/`

## Acceptance commands (run yourself)

```
python -m pytest -q tests/test_scenarios_lab.py tests/scenarios/catalog.py
ruff check .
ruff format --check .
```

## Screenshots

none — no UI change.

## Out of scope

Do not change resolver weights, `MIN_CONFIDENCE`, `CLEAR_GAP`, or any existing
assertion. If a new case fails, report the failure; do not tune the policy to
make it pass.

## Notes

Real layout on main is `tests/scenarios/` + `tests/test_scenarios_lab.py` +
`tests/scenarios/catalog.py`, not `tests/test_scenarios.py`.

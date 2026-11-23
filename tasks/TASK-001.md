# TASK-001 — Scenario-lab fixtures for existing smart replay cases

Lane: `tests` · Difficulty: `normal` · Owner review required: `no`

## Goal

Add fixtures to `tests/scenarios/` that describe three more recorded-element
cases (a renamed toolbar button, a moved dialog, two identical rows). The lab
already scores candidates deterministically; today the cases are written inside
test functions. Fixtures let the owner replay them without touching tests.

## Files allowed

- `tests/scenarios/`
- `tests/test_scenarios.py`

## Files forbidden

- everything under `engine/`, `storage/`, `controller/`, `integrations/`
- `.github/`, `scripts/verify.ps1`, `docs/ai_engineering_log.md`

## Acceptance commands

```
python -m pytest -q tests/test_scenarios.py
ruff check .
ruff format --check .
```

## Screenshots

none — no UI change.

## Out of scope

Do not change the resolver, the policy thresholds or any test expectation. If a
case fails, report it; do not adjust the assertion.

## Notes

`tests/scenarios/lab.py` builds candidates from plain data, so fixtures need no
Qt and no desktop.

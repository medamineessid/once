# TASK-002 — Extra tests for existing behaviour

Lane: `tests` · Difficulty: `good-first-task` · Owner review required: `no` · Label: `lane/tests`

## Goal

Add tests for behaviour that already works — never a new feature, never a guard
fix. Good candidates: a fresh code-path line that has no coverage, a happy-path
variant of an existing test, or an edge case the existing tests do not touch.

The test must be green before it is in the PR, and the whole `pytest` suite
must stay green.

## Files allowed

- `tests/` (only new or existing test files, appended; existing tests are not
  rewritten)

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `ui/`, `integrations/`
- `.github/`, `scripts/`, `docs/`

## Acceptance commands (run yourself)

```
python -m pytest -q <the new test file>
python -m pytest -q
ruff check .
ruff format --check .
```

Paste the real summary lines in the pull request.

## Screenshots

none — no UI change unless the behaviour you test is rendered, in which case
app-window screenshots follow the rule in `docs/COLLABORATOR.md`.

## Out of scope

Adding a skip, changing a test assertion to make coverage look higher, or
touching non-test code.

## Notes

Pick one idea per task. If unsure which path to test, ask the owner.

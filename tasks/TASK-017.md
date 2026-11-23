# TASK-017 — Demo kit `docs/DEMO.md` (BLOCKED)

Lane: `tests` · Difficulty: `good-first-task` · Owner review required: `yes` · Label: `lane/tests` · Size: `S`

## Status: BLOCKED

Blocked by TASK-014 for the new scenarios and TASK-015 for the evidence
template. A demo cannot cite a scenario or an evidence level that does not
exist yet.

## Goal

Write a short, repeatable demo script: what to open, which workflow to run, what
the user should see, which scenario fixtures back the claims, and where to
paste the evidence. It must be usable by the collaborator without inventing
steps.

## Files allowed

- `docs/DEMO.md`
- `docs/evidence/demo_run.md`

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`, `ui/`
- `.github/`, `scripts/`, `docs/ai_engineering_log.md`, `docs/STATE.md`,
  `docs/PLAN.md`, `docs/COLLABORATOR.md`
- step schema, workflow validators, approval code

## Acceptance commands (run yourself)

```
python -m pytest -q tests/test_docs_truth.py
ruff check .
ruff format --check .
```

The owner ran these three commands on this base and they pass. Paste the real
summary lines in the PR.

## Screenshots

None in this PR; the demo links to captures recorded with TASK-015's template.

## Out of scope

Running the demo on the real PC, adding new scenarios, changing the app, or
claiming `real desktop` evidence from a documented script alone.

## Notes

Use neutral machine paths. Mark every step that has not actually been run as
`not verified`.

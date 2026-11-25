# TASK-017 — Demo kit `docs/DEMO.md`

Lane: `tests` · Difficulty: `good-first-task` · Owner review required: `yes` · Label: `lane/tests` · Size: `S`

## Status: NOT BLOCKED

Draft the demo now from the scenarios and sample fixtures already in the repo.
Where a fixture or the evidence template from TASK-014/TASK-015 is not present
yet, write the step as `not verified` and leave a placeholder for the path. The
draft can be updated in a later PR when those tasks land; it is not required to
start.

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

# TASK-015 — Real-PC evidence template and desktop checklist

Lane: `tests` · Difficulty: `good-first-task` · Owner review required: `yes` · Label: `lane/tests` · Size: `S`

## Goal

Give the collaborator with the Windows PC one place to record what was actually
run: exact commands, app path, approval ID, observation, screenshots and what
could not be checked. The template must make a `real desktop` claim impossible
without the checklist being complete.

## Files allowed

- `docs/evidence/TEMPLATE.md`
- `docs/REAL_DESKTOP_CHECKLIST.md`

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

None — this task defines where screenshots go; it does not capture them.

## Out of scope

Performing the real-PC run, creating `docs/DEMO.md`, writing the privacy
checklist, or editing `docs/STATE.md`.

## Notes

The template must have explicit fields for evidence level and for "not
verified". Leave real machine names and personal paths as placeholders.

# TASK-018 — Privacy checklist for evidence and demos (BLOCKED)

Lane: `tests` · Difficulty: `good-first-task` · Owner review required: `yes` · Label: `lane/tests` · Size: `S`

## Status: BLOCKED

Blocked by TASK-015; the checklist must point at the real evidence template
fields rather than duplicate them.

## Goal

Give a one-page checklist that keeps personal data out of evidence bundles,
screenshots and demo notes: redact secrets, emails, keys, machine paths and
account names; keep full-desktop captures local; say what was removed and why.

## Files allowed

- `docs/evidence/PRIVACY_CHECKLIST.md`

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`, `ui/`
- `.github/`, `scripts/`, `docs/ai_engineering_log.md`, `docs/STATE.md`,
  `docs/PLAN.md`, `docs/COLLABORATOR.md`, `docs/DEMO.md`
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

None — documentation only.

## Out of scope

Changing redaction code, editing the recorder, or inspecting a real user's data
folder to make the checklist.

## Notes

The checklist is a human gate, not proof that redaction code works. Say that
plainly in the document.

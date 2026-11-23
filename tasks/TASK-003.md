# TASK-003 — README and docs improvements

Lane: `docs` · Difficulty: `normal` · Owner review required: `yes` · Label: `lane/ui`

## Goal

Improve the README and docs prose: clarity, ordering, and keeping the map of
what exists current. No new capability, no change to the verifier, the
orchestrator, the smart-replay wiring, or the governance rules.

Only `docs/` (and the README) may change.

## Files allowed

- `README.md`
- `docs/*.md`

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `ui/`, `integrations/`
- `scripts/verify.ps1`, `scripts/check_log_append_only.py`
- `docs/ai_engineering_log.md`, `docs/STATE.md`

## Acceptance commands (run yourself)

```
ruff check docs/ README.md
ruff format --check docs/ README.md
```

Paste the real lines in the pull request.

## Screenshots

none — prose only.

## Out of scope

Editing the append-only engineering log, and claiming a module works without
pasted evidence.

## Notes

Before this task lands, `docs/CONTEXT.md`, `docs/STATE.md` and
`docs/DECISIONS.md` must exist (TASK-005-style docs pass). Coordinate with the
owner if those depend on each other.

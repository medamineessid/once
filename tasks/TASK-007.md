# TASK-007 — Finish the UI audit tool from draft PR #12

Lane: `ui` · Difficulty: `normal` · Owner review required: `yes` · Label: `lane/ui` · Size: `M`

## Goal

Make the audit harness in draft PR #12 trustworthy: its six checks must fail on
the deliberately broken fixtures and pass on the real shell, so lane B can use
one repeatable command instead of eyeballing layouts. After this the audit can
be quoted as evidence for D1–D10.

## Files allowed

- `scripts/ui_audit.py`
- `scripts/ui_spec.py`
- `tests/test_ui_audit.py`
- `tests/ui_fixtures/`
- `docs/UI_SPEC.md`

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`, `ui/`
- `.github/`, `scripts/verify.ps1`, `scripts/check_log_append_only.py`
- `docs/ai_engineering_log.md`, `docs/STATE.md`
- step schema, workflow validators, approval code

## Acceptance commands (run yourself)

```
python -m pytest -q tests/test_shell.py tests/test_docs_truth.py
ruff check .
ruff format --check .
```

Paste the real summary lines in the PR. Add the new `tests/test_ui_audit.py`
to that pytest command before claiming done; the owner ran the two existing
files above on this base and they pass.

## Screenshots

None from the audit tool itself; keep audit PNGs under an ignored local folder.
Report the audit JSON summary in the PR, not full-desktop images.

## Out of scope

Fixing D1–D10, changing the shell UI, changing the verify gate, or merging draft
PR #12 yourself.

## Notes

Start from the owner's handoff of `ui/audit-harness-wip`; PR #12 says six tests
fail because `isVisibleTo()` is false before the offscreen window is mapped.
Fix the measurement, not the assertions.

# TASK-0NN — <short title>

Lane: `<tests|ui|engine>` · Difficulty: `<good-first-task|normal>` ·
Owner review required: `<yes|no>` · Label: `<lane/tests|lane/ui|lane/engine>`

## Goal

One paragraph. What a user can do after this that they cannot do now, or what
question this answers. If the answer is "nothing user-visible", say which risk
it removes.

## Files allowed

Only these may change. Globs end with `/` for a folder or use `*`.

- `path/to/file.py`
- `tests/`

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`
- `.github/`, `scripts/verify.ps1`, `docs/ai_engineering_log.md`

## Acceptance commands (run yourself)

```
python -m pytest -q <the test(s) you add>
ruff check .
ruff format --check .
```

Paste the real summary lines in the pull request.

## Screenshots

`<none — no UI change>` or: app-window screenshots follow the rule in
`docs/COLLABORATOR.md`, one sentence per image versus `docs/UI_SPEC.md`.

## Out of scope

List what a reader might reasonably try that this task does **not** include.

## Notes

Pick one idea per task. If unsure, ask the owner.

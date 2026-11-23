# TASK-004 — UI strings review (BLOCKED)

Lane: `docs` · Difficulty: `good-first-task` · Owner review required: `yes` ·
Label: `lane/ui`, `blocked`

## Status: BLOCKED

Do not start this until `docs/UI_SPEC.md` and `scripts/ui_audit.py` are on
`main`. Until then "one source of truth" for the UI strings is only a partial
claim — a string a page renders that is not in `ui/strings.py` cannot be a
compliance win.

## Goal (when unblocked)

Audit every string in `ui/strings.py` against the live app: every public label on
Home, My automations, Activity, Settings, the editor and the confirmation dialogs
should come from this file, and the file should have no duplicate strings. Report
any string the live app renders that the file does not own, and any file the file
owns that no live page renders, in one sentence each.

## Files allowed (when unblocked)

- `ui/strings.py`
- `tests/ui_strings_test.py` (new; reports the strings, does not assert UI)

## Files forbidden (when unblocked)

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`
- `.github/`, `scripts/verify.ps1`, `docs/ai_engineering_log.md`

## Acceptance commands (when unblocked)

```
ruff check ui/strings.py tests/ui_strings_test.py
ruff format --check ui/strings.py tests/ui_strings_test.py
```

Paste the real lines.

## Screenshots (when unblocked)

App windows for Home, My automations, Activity, Settings, the editor and every
dialog, with one sentence per image saying whether its strings come from
`ui/strings.py`.

## Out of scope (when unblocked)

Rewriting strings to "improve them" — that changes user-visible behaviour and is
a UI task, not a strings-review task.

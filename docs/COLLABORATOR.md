# Collaborator guide

For the two collaborators and their coding agents. The rules that already live in
`AGENTS.md` and `docs/WORKING_AGREEMENT.md` still apply; this page is the
short version plus the lane split.

## Getting running

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python app.py            # the app
.\.venv\Scripts\python -m pytest -q      # tests (use --basetemp under %TEMP%)
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
python scripts/ui_audit.py               # when it exists, before UI changes
```

## Folders, one line each

| folder | what lives there | who owns it |
| --- | --- | --- |
| `engine/` | the deterministic core, workflows, validators, executor | owner |
| `storage/` | SQLite schema, migrations, workflow JSON | owner |
| `recorder/` | event capture and redaction | owner |
| `controller/` | Qt-free services the UI calls | owner |
| `integrations/` | desktop, browser, coding-agent boundaries | owner |
| `ui/` | PySide6 widgets and pages only | lanes may work here |
| `tests/` | every test, mirrors the package layout | lanes may work here |
| `docs/` | decisions, specs, the append-only engineering log | owner for the log |
| `scripts/` | verify gate, fixtures, audit tools | owner for the gate |
| `tasks/` | one brief per task | owner writes, lanes read |

Read `docs/PLAN.md` for the three-lane order, task sizes and evidence levels.

## Lane permissions

- **Lane A — replay core (owner only):** `engine/`, `integrations/`,
  `recorder/`, `storage/`, `controller/`, the step schema,
  `docs/ai_engineering_log.md` and `docs/STATE.md`. Lanes B and C never edit
  these paths, even for a one-line fix.
- **Lane B — app experience:** may edit `ui/`, including
  `ui/styles/__init__.py`, **only when the brief lists the path**. May also
  edit UI test files listed in the brief and capture app-window screenshots.
- **Lane C — proof and delivery:** may edit `tests/`, packaging scripts named
  in the brief (`once.spec`, `scripts/packaging_spike.py`), `docs/DEMO.md` and
  `docs/evidence/`. No other `scripts/` or `docs/` path.

`.github/CODEOWNERS` records the owner review for each of these areas. It is a
review map, not permission to edit an owner-only path.

## Hard rules

1. Your branch is `feat/<lane>-<task>`, created from up-to-date `main`. Never
   commit or merge into `main` yourself; the owner merges.
2. Never force-push, never rewrite published history, never delete a branch.
3. Change only the files your task brief lists under "Files allowed".
4. These paths are owner-only, whatever the brief says: `engine/`, `storage/`,
   `recorder/`, `controller/`, `integrations/`, anything about approvals or
   safety, the step schema and migrations, `docs/ai_engineering_log.md`,
   `docs/STATE.md`, `scripts/verify.ps1`, `scripts/check_log_append_only.py`,
   `.github/`. `ui/styles/__init__.py` is allowed only for lane B when the brief
   names it.
5. Never delete, skip or weaken a test. If a test must skip, add a comment on
   the same line: `# allowed-skip: <reason>`.
6. No bare `except:`, no `except Exception: pass`.
7. No new dependencies without a reason in the PR and the
   `dependency-approved` label from the owner.
8. Never touch the real data folder (`%LOCALAPPDATA%/Once`) from a test or a
   script; use pytest `tmp_path` or `scripts/build_ui_fixtures.py`.
9. UI pull requests carry app-window screenshots and compare them with
   `docs/UI_SPEC.md`, one sentence per image.
10. Never claim something is done without pasted `pytest` and `ruff` output.
11. **State drift rule:** if `docs/STATE.md`, a brief or an old doc disagrees
    with code and pasted test output, the repo state wins. Report the mismatch
    to the owner; do not edit `docs/STATE.md` or upgrade an evidence level.
12. Ask the owner when unsure. A question costs minutes; a bad merge costs days.

## What "done" looks like in a PR

- `git diff --stat` pasted.
- `pytest` summary line pasted, and `ruff check .` / `ruff format --check .`.
- Screenshots for UI work, each described in one sentence.
- A line saying what was **not** verified and which evidence level from
  `docs/PLAN.md` the claim uses.
- `Task: tasks/TASK-0NN.md` in the body, so `pr-guards` can check the scope.
- The reviewer uses `docs/REVIEW_PROMPT.md` and answers APPROVE, REQUEST
  CHANGES or ESCALATE.

## Paste this at the start of every AI session

```text
Repository: once. You are one of three contributors.
Rules: docs/COLLABORATOR.md and AGENTS.md govern this session.
- Work only on branch feat/<lane>-<task> from up-to-date main.
- Touch only files under "Files allowed" in the task brief I name.
- Never edit engine/, storage/, recorder/, controller/, integrations/, .github/,
  ui/styles/__init__.py, docs/ai_engineering_log.md, scripts/verify.ps1.
- Never delete, skip or weaken tests; never add a bare except.
- Never touch the real %LOCALAPPDATA%/Once data folder.
- Run pytest and ruff yourself; paste the real output, never estimate.
- If a change seems to need anything outside the brief, stop and ask me.
Task brief: tasks/TASK-0NN.md
```

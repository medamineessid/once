# Once progress

- Last completed step: S3 merged to main (70d8ce1) after CHECKPOINT 3 approval; create-page crash found during the click-through fixed in 84b6443. Branch cleanup left a single branch, main, in sync with origin.
- Last commit: 84b6443 fix(ui): create automation button crashed reading its description
- Verified this session (PHASE 0): 
  - git branch --show-current: docs/ui-migration-plan
  - git status --short: ?? app.spec, ?? once-app.spec
  - git log --oneline -5: cd2e77e Merge redesign-ui: resolve conflicts in docs keeping both sides; 93cb6cb Merge branch 'desktop-automation-engine' into integration-full; f407c5b fix(browser): keep frame bytes coalesced with the handshake and reassemble continuation frames; 9857b18 build(packaging): add browser integration modules to PyInstaller hidden imports; c6e482f test(browser): transport-level WebSocket client tests over a local socket
  - app.py imports ui.main_window.MainWindow (app.py:20,120-127); ui/shell.py has separate MainWindow (shell.py:137); only tests/test_shell.py exercises it
  - ui/pages/ exists with home,my_automations,activity,create_automation,review,settings
  - ui/review_view.py, ui/verifier_dialog.py, ui/workers.py exist
  - tests/test_verifier_dialog.py does not exist (tests cover verifier dialog inline in test_review_ui.py)
- Next action: S4 - create automation and draft editing (ui/pages/create_automation.py currently only acknowledges a description; no workflow builder exists in the controller)
- Currently failing tests or known breakage: none
- Open items: see docs/ui_migration_plan.md for full details

## Work queue

### PHASE 0: READ-ONLY DISCOVERY (branch docs/ui-migration-plan, docs only) — DONE
- [x] P0-1: Verify starting facts (branch, app.py imports, shell vs main_window, pages, review_view/verifier_dialog/workers, untracked files) — DONE
- [x] P0-2: Write docs/ui_migration_plan.md with all required sections and file:line evidence — DONE
- [x] P0-3: Fill docs/PROGRESS.md with queue plus PHASE 1 and final items — DONE
- [x] P0-4: Commit, ff-merge to main, push (2f7dea6) — DONE

### PHASE 1: HOUSEKEEPING AND VERIFICATION TOOLING (branch chore/housekeeping)
- [x] P1-1: Run `git diff --no-index app.spec once-app.spec` and paste result; delete both untracked files; add build/, dist/, app.spec, once-app.spec to .gitignore (do not ignore once.spec) (e2f5c62) — DONE
- [x] P1-2: Add scripts/verify.ps1 (pytest offscreen with .venv\Scripts\python.exe, ruff check, ruff format --check, app.py --smoke-test, git status --short, pass/fail per check) - rewritten as real PowerShell in PHASE A (see verify-fix commit) — DONE
- [x] P1-3: Add .github/workflows/tests.yml (pytest offscreen, ruff check, ruff format --check on windows-latest, python 3.14) (e2f5c62) - 3.14 on windows-latest verified via actions/python-versions release 3.14.9 with win32 assets; no bash-in-PowerShell flaws found — DONE
- [x] P1-4: Run scripts/verify.ps1 and paste full output; commit, ff-merge, push - PASSED under Windows PowerShell 5.1 in PHASE A — DONE

### PHASE 2: UI MIGRATION SLICES
- [x] S1: Add --shell flag to app.py (slice/shell-flag). Default stays old window. --smoke-test works with and without --shell. Add tests. (2a0573b, style fix dab53da; CHECKPOINT 1 user-tested) — DONE — CHECKPOINT 1 passed
- [x] S2: Activity/history page wiring (slice/activity-page) (588ed21) — DONE
- [x] S3: My automations page (slice/my-automations-page, merged as 70d8ce1) — DONE: list/open/preview read-only + confirmed worker run, 14 new tests, screenshots docs/screenshots/slice-3/, CHECKPOINT 3 approved
- [ ] S4: Create automation and draft editing (slice/create-automation) — TODO
- [ ] S5: Recording lifecycle in shell (slice/recording-shell) — TODO
- [ ] S6: Review/approval and verifier configuration (slice/review-approval-shell) — TODO
- [ ] S7: Desktop and browser steps in create_automation (slice/desktop-browser-steps) — TODO
- [ ] S8: Switch default to shell (slice/switch-default) — **CHECKPOINT 2** before changing default/retiring main_window, stop and report — TODO

### FINAL ITEMS
- [ ] F1: Create docs/MVP_CHECKLIST.md (table of every old-window capability, new-window location file:line, test covering it, DONE/MISSING) — TODO
- [ ] F2: CHECKPOINT 2 report before default switch — TODO

## Status tracking
Each item: id, status (TODO/IN PROGRESS/DONE/BLOCKED), branch, commit hashes, raw test summary line.

- Environment: Windows 11 x64; Python 3.14.3; virtual environment `.venv`
- Browser sessions closed after approved runs/exit (atexit); hard crash can orphan Chrome/temp profile (documented limitation)
- engine/workflow.py _validate_wait_page_target has harmless unreachable selector block - leave alone
- Other worktrees exist (once-desktop, /tmp worktree) - do not touch/prune/remove

# Once progress

- 2026-10-29 user amendments: journeys reordered J2 -> J3 -> J4 -> J1 -> J5-J8 (user priority: automations cannot be created; buttons do nothing). Interim honest-control rule: until a control's journey wires its downstream signal to a real handler with an observable effect, the control is hidden; the unwired-button test follows signals through to handlers instead of only counting clicked connections.

- Last completed step: PHASE A repair (branch slice/repair-main, merged and pushed to main at 1685475): A1 working agreement, A2 flaky suite crash root-caused and fixed (0ecbea0), A3 ruff clean, A4 verify.ps1 rewritten as PowerShell 5.1 with append-only log guard + failure-detection proof, A5 docs citations re-verified, A6 box-shadow removed + tests/test_styles.py, A7 CI workflow confirmed (last GitHub Actions run on main passed), A8 full verify.ps1 run, ff-merge, push. Launcher run-shell.bat merged to main earlier (39f1d2d).
- In progress (branch slice/j2-create-automation): amendments committed (ccfd61b); chain-following unwired guard + honest hiding of Review Edit/Approve + removal of dead shell pass-wiring; suite 352 passed, 2 skipped; J2 create flow next.
- Last completed step: PHASE P1 truth-and-foundations (branch slice/p1-foundations): P1.1 twice full suite with -X faulthandler (clean, no crash/hang); P1.2 docs/BUTTON_AUDIT.md + 9 new qtbot.mouseClick behavior tests for shell controls incl. a found-and-fixed crash defect (shell Open -> review_page.set_workflow never existed); P1.3 unwired-buttons test extended to QToolButton + sidebar and provably failing; P1.4 authorized-folder held in the session through WorkflowService.set_allowed_root/allowed_root with tests (session-only, like the old window; not persisted to disk); P1.5 BLOCKED.md marked RESOLVED: Option A (user-approved); P1.6 scripts/capture_screenshots.ps1 capturing 6 pages x 3 sizes (18 distinct non-empty PNGs in docs/screenshots/latest/).
- Last completed step (PHASE B, branch slice/layout-foundation): B1 UX brief (docs/UX_BRIEF.md) and B2 PHASE C journey queue written; B3 done after the user approved BLOCKED.md option A (2026-10-28): four non-functional Settings groups removed and replaced by a real "Configure checker" entry wired to the existing VerifierConfigDialog, the three placeholder-proving tests in tests/test_shell.py rewritten to assert the honest state, duplicate Home "My automations" button removed, sidebar reduced to 4 nav buttons + brand + one footer label, SPACING_*/TYPE_*/FONT_STACK tokens in ui/styles drive the whole shell stylesheet, demo double-run fixed (page only emits the signal; the shell runs the demo once), ShellPages.CREATE state makes the sidebar reflect the create flow, 7 new layout/honest-controls tests, screenshots through the app.py --shell path in docs/screenshots/layout-foundation/.
- Last commit: see git log (this commit adds the PHASE B docs: UX brief, journey queue, B3 blocked decision).
- Verified this session (PHASE 0): 
  - git branch --show-current: docs/ui-migration-plan
  - git status --short: ?? app.spec, ?? once-app.spec
  - git log --oneline -5: cd2e77e Merge redesign-ui: resolve conflicts in docs keeping both sides; 93cb6cb Merge branch 'desktop-automation-engine' into integration-full; f407c5b fix(browser): keep frame bytes coalesced with the handshake and reassemble continuation frames; 9857b18 build(packaging): add browser integration modules to PyInstaller hidden imports; c6e482f test(browser): transport-level WebSocket client tests over a local socket
  - app.py imports ui.main_window.MainWindow (app.py:21) and ui.shell.MainWindow (app.py:22), selecting at app.py:78; ui/shell.py has its own MainWindow (shell.py:138); tests/test_shell.py and app.py --smoke-test --shell exercise it (re-checked 2026-10-27)
  - ui/pages/ exists with home,my_automations,activity,create_automation,review,settings
  - ui/review_view.py, ui/verifier_dialog.py, ui/workers.py exist
  - tests/test_verifier_dialog.py does not exist (tests cover verifier dialog inline in test_review_ui.py:371-440; re-checked 2026-10-27)
- Next action: run scripts/verify.ps1, commit B3, ff-merge slice/layout-foundation to main, push, then CHECKPOINT 1 for the user to test the new shell layout and Settings page; PHASE C journeys (J1-J9) wait for the user's "continue"
- Currently failing tests or known breakage: none (full suite green on slice/layout-foundation, 2026-10-28: "340 passed, 2 skipped in 331.81s", see ai_engineering_log.md)
- Known UI gaps (updated 2026-10-28): shell never calls review_page.set_service, so review approval still needs J6; review page's Edit button is wired to a pass handler (unwired rule will catch it in J6); create flow cannot build a workflow yet (J2)
- Known UI gaps (2026-10-29): the shell injects the service into settings since P1; it does NOT yet inject it into review_page, so review approval awaits J6; ui/shell.py has pass handlers (_on_approved, _show_run_details). Per the 2026-10-29 amendment, controls whose handlers do nothing are HIDDEN until their journey wires them.
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

### PHASE B: UX BRIEF AND DESIGN FOUNDATION (docs/UX_BRIEF.md written 2026-10-27)
- [x] B1: docs/UX_BRIEF.md from evidence (audience, journeys, page specs, honest-controls rule, layout rules, fact-7 defect list) — DONE
- [x] B2: replace this slice queue with the PHASE C journey queue — DONE
- [x] B3: slice/layout-foundation — layout rules, unwired controls removed per approved option A (see docs/BLOCKED.md), sidebar footer, spacing/type tokens in ui/styles, layout tests, screenshots in docs/screenshots/layout-foundation/ — DONE (commit: see git log, 2026-10-28)

**Safety rule for every journey below (unchanged):** `ui/` never mutates the file system — pages call controller services only (AGENTS.md S8); no new approval path, no policy/validator changes (working agreement hard rules 1-3).

### PHASE P1: TRUTH AND FOUNDATIONS (branch slice/p1-foundations) - DONE
- [x] P1.1 two faulthandler suite runs, teardown-bug hunt - DONE (340 passed, 2 skipped; run1_exit=0, run2_exit=0)
- [x] P1.2 docs/BUTTON_AUDIT.md + mouseClick behavior tests - DONE (27 passed in tests/test_shell.py)
- [x] P1.3 unwired-buttons test proven failing; extended to QToolButton + sidebar - DONE
- [x] P1.4 Settings authorized-folder persistence - DONE
- [x] P1.5 BLOCKED.md RESOLVED + log names replaced tests - DONE
- [x] P1.6 screenshot capture script - DONE (18 distinct captures)

### PHASE C: USER JOURNEYS (reordered 2026-10-29 by user: J2 first; CHECKPOINT 2 after J2, CHECKPOINT 3 after J9)

- [ ] J2 Create an automation: task form + draft step editing (add/move/remove), save, appears in My automations; entry point "Record what I do" — **CHECKPOINT 2** after J2 for the user to try — TODO
- [ ] J3 My automations: list, open, preview, run, cancel (wire run_requested and preview_requested through the shell/controller; keep the page-local working paths), delete only if the old window has it — TODO

- [ ] J4 Activity: history list and per-step results — TODO
- [ ] J1 Try a demonstration: Home's demo button runs the existing demo through the controller service, shows progress and result, appears in Activity — TODO
- [ ] J5 Recording lifecycle inside the create flow: record, stop, analyze offline, delete a recording — TODO
- [ ] J6 AI proposals: review and approve through the existing approval path (ui/review_view.py, ui/workers.py) — TODO
- [ ] J7 Desktop and browser steps in the create flow via engine/desktop.py approve_desktop_workflow; UI lists exactly which steps mutate something before approve is enabled; never a second approval path — TODO
- [ ] J8 Settings: authorized folder, verifier configuration, coding-agent connection only if it really works; no non-functional entries — TODO
- [ ] J9 docs/MVP_CHECKLIST.md: every old-window capability, new location (file:line), test, DONE or MISSING — **CHECKPOINT 3** before changing the default window in app.py or retiring ui/main_window.py: stop and report; never make that change without approval — TODO


## Status tracking
Each item: id, status (TODO/IN PROGRESS/DONE/BLOCKED), branch, commit hashes, raw test summary line.

- Environment: Windows 11 x64; Python 3.14.3; virtual environment `.venv`
- Browser sessions closed after approved runs/exit (atexit); hard crash can orphan Chrome/temp profile (documented limitation)
- engine/workflow.py _validate_wait_page_target has harmless unreachable selector block - leave alone
- Other worktrees exist (once-desktop, /tmp worktree) - do not touch/prune/remove

# Lane B progress / handoff note

> Handoff note (updated after every commit) — most recent at the top.

## Handoff (2026-11-01) — B3 LANDED on main (d58e42b)

- B3 landed after verify.ps1 ALL CHECKS PASSED and an empty lane-fence check. Review page now flows through the single approval path with non-modal banners; Approve test-clicked with a real service (saved workflow asserted via list_saved/load); Edit stays hidden pending B7 shell wiring.

## Handoff (2026-11-01) — B3 implementation on branch b/b3-review-wiring (about to commit)

- B3 done in code: ui/pages/review.py now (1) renders proposals through THE existing approval path — `preview_proposal` for the steps list (fixes the review.py:129 `proposal.steps` AttributeError, parity with old-window _show_preview), `approve_proposal` + `service.save_approved` on click; (2) Approve becomes visible ONLY with a service injected AND a valid proposal loaded (Edit stays hidden — needs the shell hand-off, recorded for B7); (3) errors are non-modal banners (blocking QMessageBox.warning removed); (4) invalid drafts keep approval hidden with a plain-language banner.
- Strings block "# --- lane B strings ---" appended to ui/strings.py (4 strings).
- New tests tests/test_b3_review_wiring.py: 7 tests (load/preview, visibility gating, click-Approve lasting effect via service.list_saved()/load, no-service guard, invalid-draft banner, dismiss, Edit-hidden). Focused: `7 passed in 0.81s`; neighbors test_review_ui.py + test_shell.py: `39 passed in 58.16s` (old hidden-buttons test still green because defaults stay hidden).
- Pending before landing: verify.ps1 + fence check + ff-merge.
- Next after B3 lands: B1 run-events contract.

## Handoff (2026-11-01) — B6 LANDED on main (f57f09d + a6ed06f)

- B6 done and landed: verify.ps1 ALL CHECKS PASSED on the task branch before the ff-merge; main pushed to a6ed06f. The fix ships behind `_detached_runs` + `_wait_out_detached_runs` (one-time atexit hook, 30 s grace join) in ui/workers.py.
- Follow-up commit fixed lint on my new test (imports sorted, removed unused local, reinstalled QApplication before QWidget construction — a parentless QWidget construction aborts the process; that failure mode escaped into a pytest run before).
- Next: B3 review page wiring. Then B1, B2, B5, B4, B7.
- Uncommitted: nothing.

## Handoff (2026-11-01) — after B6

- Done: B6 on branch b/b6-detach-exit — new tests/test_b6_cancel_detach_exit.py (2 tests: subprocess proves a cancel-ignoring worker through cancel_and_join's detach path exits cleanly; control test stays in-bound); fixed ui/workers.py cancel_and_join: the detach path now records (thread, worker) in a module-level `_detached_runs` registry and registers a one-time atexit hook granting a generous 30 s bounded join (DETACHED_RUN_EXIT_GRACE_MS) at interpreter exit, before PySide6 teardown destroys wrappers.
- Evidence for the crash the fix removes (pre-fix, raw): child stdout `DETACH=True`, then exit code 3221226505 (0xC0000409 fail-fast). Also proven: merely retaining refs at module level does NOT fix it (same fail code) — the thread must finish before teardown; hence the exit-hook join. Focused result after fix: `2 passed in 7.85s`; neighbors `tests/test_close_during_run.py tests/test_workers.py` `6 passed in 2.47s`.
- Residual limitation (logged, not hidden): a worker still running after the 30 s exit-grace join cannot be destroyed safely by PySide6 (removed ownership API); it may produce the same fail-fast at teardown — logged as warning; real engine runs honor cancel each step (≤60 s per step), so this is a pathological edge.
- Next: B3 review page wiring (service injection hook + proposal.steps defect + Edit/Approve unhide with click tests); then B1 run-events contract, B2 approval panel, B5 activity evidence, B4 record a task, B7 (A2c DONE ⇒ precondition met; gate only on a clean rebase).
- Uncommitted: this commit covers all of B6 + ledgers.

## Handoff (2026-11-01) — session start

- Done: verified clone (main == origin/main at afc342e, verify.ps1 ALL CHECKS PASSED: `468 passed, 2 skipped in 112.43s`); installed the project's pinned requirements into this clone's `.venv` (Python 3.14.3 — no dependency changes, exact pins from requirements-dev.txt); saved the session prompt verbatim to docs/LANE_B_PROMPT.md (`45706bc`, landed on main); created the docs/lane_b/ ledger scaffold.
- Environment fix (local-only, no repo content changed): this clone was checked out with CRLF by the Windows git while WSL-side git had `core.autocrlf` unset, so `git status` showed all 161 files modified (31,570 +/- each, pure line-ending noise, proven with `git diff --ignore-cr-at-eol` and `git -c core.autocrlf=true status -sb` => clean). Fix: `git config core.autocrlf true` in this clone only (mirrors the Windows checkout; per-blob content unchanged). See decisions.md B-001.
- Next: read docs (AGENT_PROMPT, WORKING_AGREEMENT, UX_BRIEF, BUTTON_AUDIT, design/visual_editor.md, PROGRESS.md), then the QUEUE in order: B6 (cancel_and_join detach-path subprocess test), B3 (review page wiring), B1 (run-events contract), B2 (approval panel), B5 (activity evidence), B4 (record a task), B7 (only if Lane A A2c is DONE).
- Uncommitted: nothing after this commit.

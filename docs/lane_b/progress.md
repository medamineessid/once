# Lane B progress / handoff note

> Handoff note (updated after every commit) — most recent at the top.

## Handoff (2026-11-01) — B1 LANDED on main (f7217c7); B2 implemented on branch b/b2-approval-panel (538b4cd)

- B1 landed (verify.ps1 ALL CHECKS PASSED before ff-merge; fence empty at that time).
- B2 done in code: new ui/components/approval_panel.py (DesktopApprovalPanel: lists exactly the mutating steps via engine MUTATING_DESKTOP_KINDS + mutating_kind_names, Approve enabled only while the list is shown, Approve click calls the real gate approve_desktop_workflow; gate refusals surface inline; read-only automations never show it). ui/pages/my_automations.py run flow: confirmed Run → mutating automation shows the panel and starts nothing; approval → run_requested + WorkflowWorker(desktop_approval=...) → service.run_desktop_approved; decline → nothing runs, page reusable; row switch or shutdown discards a waiting panel. ui/workers.py gained the additive desktop_approval mode (cancel_check + progress wired as before).
- tests/test_b2_approval_panel.py: 12 tests — panel hidden/read-only exactness, exact row list (kinds == mutating_kind_names), approve click → real DesktopApproval bound to the listed workflow, refuse mix → inline rejection + no approval, fresh-panel inert, unapproved-can't-run, approved-runs (fake providers, real engine gate + policy), decline runs nothing, row-switch discards panel, read-only runs without panel. Guards proven: approve-disabled guard violated deliberately during the session → test failed (`assert True is False`), then restored.
- Focus result: `12 passed in 0.57s`; neighbors test_my_automations_page + test_desktop_controller + test_b1: `38 passed in 1.71s` (combined run `50 passed in 1.71s` with B2); test_shell.py: `28 passed in 5.80s`; test_review_ui+test_during earlier neighbor run (51 passed incl. b6). ruff check clean on all touched files.
- Known product behavior surfaced (not an engine change on my side): the desktop gate REJECTS a REPORT step mixed into a desktop automation ("Replay does not allow these step kinds: REPORT"); the panel shows this inline. Question for owner in questions.md.
- Pending: verify.ps1 + fence + ff-merge + push main.
- Next: B5 activity evidence, then B4 record-a-task, then B7.

## Handoff (2026-11-01) — B1 implemented on branch b/b1-run-events (about to commit)

- controller/run_events.py: RunEventKind (7 kinds), frozen RunEvent (sequence, workflow/step ids, status, message, evidence, engine_run_id), RunEventStream (locked, closes after RUN_FINISHED — empty tuples afterwards), FakeRunEventSource for tests. Events derive ONLY from real engine results: skip/cancel classification keys off the engine's two canonical skip phrases; retries surface once with "(attempt N)" message and attempt evidence.
- docs/contracts/run_events.md: field table, honesty rules, thread-safety rules, delivery order, test-double note.
- ui/workers.py WorkflowWorker: additive run_event Signal + RunEventStream wiring (start before the run, per result, reconcile+finish, failure path emits RUN_FINISHED(FAILED)); queued-connection note in contract.
- tests/test_b1_run_events.py: 9 tests — identity, success order (REAL runner), failure+skipped fill, cancellation via real cancel flag, retry with a fake flaky desktop provider through the REAL engine, post-finish silence, worker delivery order + worker failure, fake-source contract. Focused: `9 passed in 0.43s`; neighbors: `15 passed in 11.04s`.
- Pending: verify.ps1 + fence + ff-merge.
- Next: B2 approval panel (My automations run flow), then B5, B4, B7.

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

## Handoff (2026-11-04) — run-truth B1/B2 on branch b/b2-approval-panel (owner-assigned tasks B1-B4)

- Branch note: the task brief named branch `lane-b/run-truth`; that branch does not exist here. Work continued on the current branch `b/b2-approval-panel` without switching, pushing, merging or rebasing.
- B1 (committed first: `1d76b5f` contract, then `ef842d9` engine): `docs/contracts/run-outcomes.md` published before any code. `StepStatus.OBSERVED` (REPORT steps), `WorkflowStatus.OBSERVATION_ONLY` (no non-REPORT step succeeded/verified), `_final_status` decision order with failures first, `OBSERVED` added to `controller.run_events._SUCCESS_STATUSES`, run-events contract row updated. History needs no migration (statuses are plain text, no CHECK constraint); old rows still load and keep their stored meaning. One out-of-lane but unavoidable edit: `ui/shell.py::_on_demo_finished` hard-coded `status.value == "SUCCEEDED"`, so the observation-only demo would have shown "Demonstration failed"; the branch now accepts `OBSERVATION_ONLY`. Only that condition changed.
- B1 tests: new `tests/test_b1_run_outcomes.py` (11 tests) plus expectation updates in `test_workflow.py`, `test_b1_run_events.py`, `test_b2_approval_panel.py`, `test_workers.py`, `test_smoke.py`, `test_shell.py`, `test_p2_shell.py`, `test_activity_page.py`, `test_editor_page.py` — all assert a report is not a success now.
- B2: `chrome` registered as a desktop application (`KNOWN_APPLICATIONS`, `WindowsApplicationRegistry.resolve` over the three standard install roots, injectable candidates for tests), launch forced onto a disposable `--user-data-dir`, and a step that supplies `--user-data-dir`/`--profile-directory` is refused. New `tests/test_b2_chrome_launch.py` (9 tests incl. two `windows_only`). No live Chrome was started; `close_application` and `PROCESS_TO_APPLICATION` do not exist in this tree (see questions.md).
- Next: B3 (`preview_proposal` must reflect `DESKTOP_INTERACTION_POLICY`), then B4 run-status labels.

## Handoff (2026-11-06) — Lane B follow-up on b/b2-approval-panel (merged tree, uncommitted merge)

- Chrome is closable end to end: `StepKind.CLOSE_APPLICATION` + registry-directed `_validate_close_target` (only `{"application": ...}`; executable/path targets are rejected with "unknown close fields"), `KNOWN_APPLICATIONS` = {notepad, vscode, chrome}, `DesktopActions.close_application` in the adapter contract, `PROCESS_TO_APPLICATION["chrome.exe"] = "chrome"` for recorder-mapped steps.
- The Windows adapter closes only windows whose `process_id` equals the pid recorded at launch (`_launched_processes`), never a title or image name; nothing launched in this run => FAILED "did not launch" with `registered=false`, and windows that will not disappear => FAILED within `CLOSE_TIMEOUT_SECONDS`.
- Merge defect found and fixed: my first conflict resolution dropped `vscode` from `KNOWN_APPLICATIONS` and the whole `close_application` adapter, so 24 tests failed; the same resolution also lost the B1-B4 `docs/ai_engineering_log.md` entries (restored, append-only).
- `test_launch_refuses_a_non_chrome_endpoint` is now a genuine negative case in the merged tree (`Browser: Edg/1.0` => refused, "does not belong to Chrome"); my pre-merge copy asserted refusal for a Chrome/141 payload, which the implementation correctly accepted. No skip needed.
- Run-truth fallout in the merged tree fixed: the editor banner reported an observation-only run as "Automation could not finish" (now a neutral `EDITOR_RUN_OBSERVED` message), and three stale `Succeeded`/`SUCCEEDED` expectations were updated to the honest observation label (test_p2_shell, test_editor_page, test_entry_acceptance). These are the only Lane A files touched, each a one-line expectation fix; flag for Lane A review.
- Verification: `pytest -q` => `601 passed, 2 skipped in 140.37s`; `ruff check .` => `All checks passed!`; `ruff format --check .` => `181 files already formatted`. NOT VERIFIED: live Chrome launch/close (no desktop automation was run in this session); `@pytest.mark.windows_only` real-desktop paths still need the manual check in questions.md.
- Uncommitted: the whole `origin/integration/preview` merge is staged and uncommitted in this tree; only the follow-up files are committed on top of it.

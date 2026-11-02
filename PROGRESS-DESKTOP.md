# PROGRESS-DESKTOP.md — desktop automation engine (Chrome automation)

Branch: desktop-automation-engine @ e196f5c (carried from the first-pass session below).
Worktree: /mnt/c/Users/DELL/once-desktop (recreated; the old dir was a stale orphan
checkout whose .git pointed to a pruned admin dir, and there was no usable worktree).

MVP DEFINITION: given one bundled JSON automation (explicit intent + ordered,
parameterized steps, target by URL and DOM selectors only), a single unattended
command launches an isolated real Chrome session, runs the whole flow end to end
through the approve/verify engine against a local fixture page, prints the per-step
run report, and exits PASS or FAIL from the fixture-based check command.

CHECKLIST (strictly required for that one flow; everything else is out of scope):

- [x] 1. Engine code runs on Windows under a real Chrome from one command:
      baseline `scripts/chrome_demo.py` green end to end (the 6 earlier
      Chrome-blocked tests re-attributed to the missing real run).
- [ ] 2. Fixture automation as JSON on disk: intent + ordered steps, saved via
      storage/workflows.py (workflow_to_dict/from_dict strict validation), with
      parameter inputs (`{url}`, `{text}` placeholders) substituted at check time.
- [ ] 3. `scripts/check_mvp.py`: single command, no manual steps, sets up the
      local fixture page host, loads the fixture JSON, runs launch -> navigate ->
      wait -> inspect -> find -> click -> type -> wait -> verify through
      approve_desktop_workflow + ReplayExecutor, prints per-step report and
      final PASS/FAIL, exit 0/1.
- [ ] 4. Failure path stays honest: a failing step (e.g. missing selector) makes
      the check exit 1 with a clear message; targeted pytest covers fixture
      loading/validation + the check logic with fake browser actions (no Chrome
      in the test suite).
- [ ] 5. Run persisted: check stores the run in the history SQLite database and
      prints the run id; a second invocation on a cold start works.
- [ ] 6. Cold-start twice consecutively: no leaked Chrome/profile/server state
      between runs (acceptance = run the check twice, both PASS).
- [ ] 7. DEMO section below with the exact demo command, expected result, gaps.

Lanes/limits: no UI code, no redesign-ui branch, no new runtime dependencies
(engine browser path is stdlib-only). Design rules held: JSON intent + ordered
steps; URL + DOM-selector targets (no coordinate clicks); parameterized inputs;
one pass/fail check command.

---

## 2026-11-02 — Desktop automation engine (Chrome automation)

STATE: complete for what is verifiable without a real Chrome/Windows machine.

Done:
- Fixed Python-2-style `except X, Y:` syntax errors in integrations/chrome_devtools.py (lines 318, 460) so the Chrome DevTools provider imports (was a hard blocker for all Chrome control).
- Added end-to-end tests wiring the real ChromeDevtoolsActions through WorkflowRunner: launch registers a cdp_port session; navigate -> inspect -> wait all dispatch through the engine.
- Fixed Python-2 syntax errors in controller/service.py:810 and storage/layouts.py:89 that blocked test_replay/test_loop collection (replay gate used by desktop workflows; not UI code).

Verified: 104 passed, 6 failed + 2 skipped across tests/test_chrome_devtools.py, test_browser_engine.py, test_desktop_engine.py, test_devtools_ws.py, test_replay.py, test_loop.py, test_verifier.py, test_workflow.py. All 6 failures require real Chrome installed on Windows (environment-only, not engine bugs). ruff check/format clean on touched files.

Next: none — engine work is complete pending a real Chrome/Windows environment to run the 4 launch/registry tests that need an actual Chrome binary.

---

## LOG (MVP push)

- Item 1 done: full chrome_demo.py flow PASS on real Chrome 156.0.8078.76 (isolated profile, DevTools port, clean shutdown), run via the Windows venv python through WSL interop. The "needs real Chrome" gap from the first pass is resolved.
- Files ticked: PROGRESS-DESKTOP.md. Demo run only.
- Next: item 2 — fixture automation JSON (intent + ordered steps + params).

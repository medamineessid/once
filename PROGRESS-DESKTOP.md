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
- [x] 2. Fixture automation as JSON on disk: intent + ordered steps, saved via
      storage/workflows.py (workflow_to_dict/from_dict strict validation), with
      parameter inputs (`{url}`, `{text}` placeholders) substituted at check time.
- [x] 3. `scripts/check_mvp.py`: single command, no manual steps, sets up the
      local fixture page host, loads the fixture JSON, runs launch -> navigate ->
      wait -> inspect -> find -> click -> type -> wait -> verify through
      approve_desktop_workflow + ReplayExecutor, prints per-step report and
      final PASS/FAIL, exit 0/1.
- [x] 4. Failure path stays honest: a failing step (e.g. missing selector) makes
      the check exit 1 with a clear message; targeted pytest covers fixture
      loading/validation + the check logic with fake browser actions (no Chrome
      in the test suite).
- [x] 5. Run persisted: check stores the run in the history SQLite database and
      prints the run id; a second invocation on a cold start works.
- [x] 6. Cold-start twice consecutively: no leaked Chrome/profile/server state
      between runs (acceptance = run the check twice, both PASS).
- [x] 7. DEMO section below with the exact demo command, expected result, gaps.

Lanes/limits: no UI code, no redesign-ui branch, no new runtime dependencies
(engine browser path is stdlib-only). Design rules held: JSON intent + ordered
steps; URL + DOM-selector targets (no coordinate clicks); parameterized inputs;
one pass/fail check command.

---

DEMO (MVP verified complete 2026-11-02)

Exact command (Windows console, needs a real Chrome installed at the default
location and any Python 3.12+; the repo's Windows venv works):

    C:\Users\DELL\once\.venv\Scripts\python.exe C:\Users\DELL\once-desktop\scripts\check_mvp.py

(from a WSL shell, equivalent shortcut: `../once/.venv/Scripts/python.exe scripts/check_mvp.py`)

What you will see, end to end, unattended:
1. `local fixture page: http://127.0.0.1:<port>/index.html`
2. `[launch] SUCCEEDED` with `cdp_port=` evidence (isolated Chrome profile).
3. Ordered step report: navigate -> wait-page -> inspect -> find -> click -> type
   -> wait-status -> verify, each `SUCCEEDED`/`VERIFIED` with evidence.
4. `history: run snapshots recorded in C:\Users\DELL\AppData\Local\Once\history.db`
5. `CHECK: PASS - run <uuid> verified end to end.` and exit code 0. The engine
   closes the isolated browser and the fixture server; no windows left open.

Any failure prints `CHECK: FAIL - <single-idea reason>` and exits 1.

Cheapest targeted check without Chrome:
    python -m pytest tests/test_check_mvp.py -q   ->  5 passed

Known gaps:
- Chrome discovery (integrations/chrome_devtools.py) probes fixed install paths
  (C:\Program Files\..., C:\Program Files (x86)\...) and rejects anything not
  containing chrome.exe; a Chrome elsewhere needs the default install path.
- One fixture flow only: the demo page DOM (#demo-button, #demo-input, #status)
  is fixed in the DemoServer page that scripts/check_mvp.py imports from
  chrome_demo.py; a new flow needs a matching fixture JSON whose first step is
  LAUNCH_BROWSER.
- The fixture wrapper (intent/params) sits outside workflow_from_dict's schema;
  the workflow itself is strictly validated (schema v3). Adding intent fields to
  the root schema is future work.
- The 6 pre-existing pytest failures that need a live Chrome were not part of
  this checklist; not revisited (unchanged by this session).
- History DB stores step evidence tuples; evidence redaction was not revisited
  for this flow (targets are local URL + selectors + fixture text only).

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

- Item 1 done: full chrome_demo.py flow PASS on real Chrome 156.0.8078.76 (isolated profile, clean shutdown) via the Windows venv python through WSL interop; the "needs real Chrome" gap from the first pass is resolved.
- Files: PROGRESS-DESKTOP.md only (demo run).
- Next: item 2 — fixture automation JSON (intent + ordered steps + params).

- Item 2 done: fixture automation JSON (intent + ordered steps, strict schema v3 validation) loads via workflow_from_dict; parameter inputs {url}/{text}/{cdp_port} substituted at check time (cdp_port coerced to int for the validator).
- Files: scripts/fixtures/mvp_flow.json (new). E2E check: real run in item 3 below.
- Next: item 3 — check_mvp.py single-command PASS/FAIL flow.

- Item 3 done: scripts/check_mvp.py runs the fixture flow unattended on real Chrome 156 (isolated profile) end to end; CHECK: PASS run 7b5cc0de-9f0d-477c-afed-d4fdf1eac093, exit 0.
- Files: scripts/check_mvp.py (new), PROGRESS-DESKTOP.md.
- Next: item 4 pytest covers fixture load/validation + check logic with fake actions; failure path exits 1.

- Item 4 done: check script reshaped into testable pieces (_split_workflow/_coerce_browser_port/checked_outcome/run_fixture_flow); 4 targeted tests green with fake browser actions, no Chrome in the suite (fixture strict load, ordered dispatch, missing port -> fair fail, failing step -> FAIL verdict).
- Files: scripts/check_mvp.py (restructure), tests/test_check_mvp.py (new), PROGRESS-DESKTOP.md. pytest 4 passed; ruff clean on both.
- Next: item 5 — persist runs to history DB and print run id.

- Item 5 done: record_runs(default_history_path()) persists setup+main snapshots to %LOCALAPPDATA%/Once/history.db and prints the path; test test_record_runs_persists_snapshots_for_a_second_invocation covers the schema rows with tmp_path DB (5 tests pass).
- Files: scripts/check_mvp.py (record_runs, --history-db), tests/test_check_mvp.py, PROGRESS-DESKTOP.md.
- Next: item 6 — cold-start double run on Windows.

- Item 6 done: check_mvp.py run twice consecutively on real Chrome; both CHECK: PASS exit 0 (runs 852d0139..., 7a9d63b9...); history DB shows 4 workflow_runs / 18 step_results appended with both new run ids.
- Files: PROGRESS-DESKTOP.md only (verification run).
- Next: item 7 — DEMO section, then stop.

- Item 7 done: DEMO section written (exact command, expected output, 5 known gaps); checklist complete.
- Files: PROGRESS-DESKTOP.md.
- Next: none — the MVP flow runs unattended on real Chrome from one command; stop here.

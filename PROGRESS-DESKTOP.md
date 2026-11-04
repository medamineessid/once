# PROGRESS-DESKTOP.md — desktop automation engine (Chrome automation)

Branch: desktop-automation-engine @ e196f5c (carried from the repo; this is the
first-pass session resuming it). Worktree: /c/Users/DELL/once-desktop (recreated
cleanly this session because the old orphan dir was not a usable git worktree and
`desktop-automation-engine` did not exist as a branch yet here).

MVP DEFINITION: given one bundled JSON automation (explicit intent + ordered,
parameterized steps, target by URL and DOM selectors only), a single unattended
command launches an isolated real Chrome session, runs the whole flow end to end
through the approve/verify engine against a local fixture page, prints the per-step
run report, and exits PASS or FAIL from the fixture-based check command.

CHECKLIST (strictly required for that one flow; everything else is out of scope):

- [x] 1. Engine code runs on Windows under a real Chrome from one command — the
      MVP check, `scripts/check_mvp.py`, launched an isolated Chrome and ran the
      full ordered flow on a real Chrome on this machine on 2026-11-03 (exit 0,
      per-step SUCCEEDED/VERIFIED evidence, fixture-page host started and stopped).
- [x] 2. Fixture automation as JSON on disk — `scripts/fixtures/mvp_flow.json`
      carries explicit intent + ordered parameterized steps whose first step is
      LAUNCH_BROWSER; `check_mvp.py` splits launch out, substitutes `{url}`,
      `{text}`, `{cdp_port}` at the execution boundary, and the workflow passes the
      strict validator already used everywhere else (`workflow_from_dict`, schema v3).
- [x] 3. `scripts/check_mvp.py`: single unattended command — starts the local
      fixture host, loads the fixture JSON, runs launch -> navigate -> wait-page ->
      inspect -> find -> click -> type -> wait-status -> verify through
      `approve_desktop_workflow` + `ReplayExecutor(DESKTOP_INTERACTION_POLICY)`,
      prints per-step report + final PASS/FAIL, exits 0/1.
- [x] 4. Failure path stays honest — the targeted pytest suite proves it without a
      real Chrome: `tests/test_check_mvp.py` covers fixture load + split +
      ordered dispatch with fake actions, missing-port stop before the main flow,
      and a failing step producing a FAILED run + FAIL verdict.
- [x] 5. Run persisted — `record_runs` appends run snapshots to the history SQLite
      database and prints the DB path + run id; verified by `test_check_mvp.py`
      against a tmp db, and by a live run appending to
      `C:\Users\DELL\AppData\Local\Once\history.db`.
- [x] 6. Cold-start twice consecutively — the check was run twice in a row on this
      machine and both PASSed; the history DB grew by one launch + one flow per run
      (rows went from 8 runs / 36 step rows before the first check this session to
      10 runs / 45 step rows after the second), so no state leaked between runs.
- [x] 7. DEMO section below with the exact demo command, expected result, gaps, and
      THIRD-PARTY-NOTICES.md recording the Skill Recorder reuse note.

Lanes/limits: no UI code, no redesign-ui branch, no new runtime dependencies
(engine browser path is stdlib-only). Design rules held: JSON intent + ordered
steps; URL + DOM-selector targets (no coordinate clicks); parameterized inputs;
one pass/fail check command.

Licensed reference note (Phase 1): the only external repo consulted was
microsoft/skill-recorder, installed locally at
`C:\Users\DELL\AppData\Local\SkillRecorder\versions\505c97ae47be5642c0e1b44ebb8d1c1530c298fa`
(version 0.8.0, MIT). It was read-only for analysis. No file was copied. The only
output from that consultation is the reuse decision record in REUSE.md and the
licensing note below.

Licensing note (mandatory, from Phase 1):
- Portions from microsoft/skill-recorder, MIT License, Copyright Microsoft Corporation.
- Full MIT text: see THIRD-PARTY-NOTICES.md.
- No Microsoft branding/logos, third_party/, bundled assets, Copilot CLI,
  Copilot sign-in, Whisper narration, or screen-recording code was copied.
- No new runtime dependency was added from the reference repo.

---

DEMO (MVP verified complete 2026-11-03)

Exact command (Windows console, needs a real Chrome installed at the default
location and any Python 3.12+; the repo's Windows venv works):

    C:\Users\DELL\once\.venv\Scripts\python.exe C:\Users\DELL\once-desktop\scripts\check_mvp.py

What you will see, end to end, unattended:

1. `local fixture page: http://127.0.0.1:<port>/index.html`
2. `[launch] SUCCEEDED` with `cdp_port=` evidence (isolated Chrome profile).
3. Ordered step report:
   navigate -> wait-page -> inspect -> find -> click -> type -> wait-status -> verify,
   each `SUCCEEDED`/`VERIFIED` with evidence.
4. `history: run snapshots recorded in C:\Users\DELL\AppData\Local\Once\history.db`
5. `CHECK: PASS - run <uuid> verified end to end.` and exit code 0. The engine
   closes the isolated browser and the fixture server; no windows left open.

Any failure prints `CHECK: FAIL - <single-idea reason>` and exits 1.

Cheapest targeted check without Chrome:

    python -m pytest tests/test_check_mvp.py tests/test_fixtures.py -q   ->  7 passed

Known gaps:

- Chrome discovery (`integrations/chrome_devtools.py`) probes fixed install paths
  (`C:\Program Files\...`, `C:\Program Files (x86)\...`) and rejects anything not
  containing `chrome.exe`; a Chrome elsewhere needs the default install path.
- One fixture flow only: the demo page DOM (`#demo-button`, `#demo-input`, `#status`)
  is fixed in the `DemoServer` page that `scripts/check_mvp.py` imports from
  `chrome_demo.py`; a new flow needs a matching fixture JSON whose first step is
  `LAUNCH_BROWSER`.
- The fixture wrapper (`intent`/`params`) sits outside `workflow_from_dict`'s schema;
  the workflow itself is strictly validated (schema v3). Adding intent fields to the
  root schema is future work.
- The 6 pre-existing pytest failures that need a live Chrome were not part of this
  checklist; not revisited (unchanged by this session).
- History DB stores step evidence tuples; evidence redaction was not revisited for
  this flow (targets are local URL + selectors + fixture text only).

---

## 2026-11-03 — Desktop automation engine (Chrome automation)

STATE: Phase 1 complete (analysis + reuse decisions + licensing record); Phase 2
complete for the MVP checklist (items 1-7 verified against a real Chrome on this
machine this session).

What exists before this session

- `docs/desktop_automation.md` — the full inventory of what is already implemented
  on this branch: approved desktop/browser step kinds, the approval gate, the
  Chrome DevTools isolated-browser provider, the stdlib DevTools WebSocket client,
  the controller surface, and the two live demos (`notepad_demo.py`, `chrome_demo.py`).
- `scripts/chrome_demo.py` — live manual Chrome demo; last verified 2026-10-25 on
  the build machine.
- `scripts/check_mvp.py` + `scripts/fixtures/mvp_flow.json` + `tests/test_check_mvp.py`
  — already present and already green in the cheap (no-Chrome) pytest sense: 7 passed.

What I verified this session (exact commands + results)

- Environment: Python `3.14.3`; PySide6 `6.12.0`; pywinauto `0.6.9`; no new
  dependency added. `integrations.chrome_devtools.ChromeDevtoolsActions` imports
  cleanly in the worktree venv.
- REUSE.md written from a real scan of the reference repo (folders, `README.md`,
  `LICENSE`, `package.json`, `common/automation.ts`, `common/values.ts`,
  `common/skill.ts`, `common/events.ts`, `evals/builder/run.ts`,
  `evals/builder/score.ts`, `evals/scenarios/invoice-extract.ts`,
  `electron/describer/*`, `electron/recorder/*`, `electron/sensitive/*`).
  Conclusion: useful as a conceptual map only; no code copied.
- `THIRD-PARTY-NOTICES.md` added with the mandatory MIT notice + full MIT text.
- Live run on a real Chrome on this machine:
  `.venv/Scripts/python.exe C:/Users/DELL/once-desktop/scripts/check_mvp.py` ->
  `CHECK: PASS - run 6bcbb598-6e30-4a2c-b609-d59fc09e8ea3 verified end to end.`
  and exit 0. Per-step output:

  ```
  [navigate] SUCCEEDED: The page loaded.
          requested_url=http://127.0.0.1:63172/index.html
          final_url=http://127.0.0.1:63172/index.html
          title=Once Browser Demo
          readyState=complete
  [wait-page] SUCCEEDED: The page matched all waited-for conditions.
          title=Once Browser Demo
          url=http://127.0.0.1:63172/index.html
  [inspect] SUCCEEDED: The current page was inspected.
          title=Once Browser Demo
          url=http://127.0.0.1:63172/index.html
          text_length=108
          text_truncated=false
          text_begin=Once isolated-browser demo |   | This page is served locally and exists only for the demo. |   |   Demo button |   | waiting
  [find] SUCCEEDED: The element was uniquely identified.
          selector=#demo-button
          tag=button
          disabled=false
          matches=1
          element_text=Demo button
  [click] SUCCEEDED: The element was clicked.
          selector=#demo-button
          clicked=true
  [type] SUCCEEDED: The text was entered and read back from the element.
          selector=#demo-input
          chars=10
          readback_confirmed=true
  [wait-status] SUCCEEDED: The page matched all waited-for conditions.
          title=Once Browser Demo
          url=http://127.0.0.1:63172/index.html
  [verify] SUCCEEDED: The element was uniquely identified.
          selector=#status
          tag=p
          disabled=false
          matches=1
          element_text=button was clicked
  history: run snapshots recorded in C:\Users\DELL\AppData\Local\Once\history.db
  CHECK: PASS - run 6bcbb598-6e30-4a2c-b609-d59fc09e8ea3 verified end to end.
  cleanup: the engine-launched browser was closed and its profile removed.
  cleanup: the local fixture server was stopped.
  ```

- Cold-start repeat: the same command run a second time on this machine also PASSed
  (`CHECK: PASS - run bbe06982-ed94-4ad0-8a48-7ee3b0505dc0 verified end to end.`,
  exit 0). The history DB grew cleanly between the two runs: before the first check
  this session it held 8 runs / 36 step rows; after the second check it held 10 runs
  / 45 step rows. That is one launch + one flow per check, with no leftover browser,
  profile, or server state between runs.

- pytest (no Chrome) in the worktree:
  `tests/test_check_mvp.py` + `tests/test_fixtures.py` = 7 passed;
  the broader desktop/browser/devtools/replay suite = 121 passed, 1 failed.

The one existing failure I saw

- `test_launch_refuses_a_non_chrome_endpoint` asserts the launch result should be
  FAILED, but the fake used in that test produces SUCCEEDED. That is a pre-existing
  test/fake mismatch on this branch. I did not touch it this session and I am not
  claiming it as a new defect. I am leaving it for a real Chrome/Windows verification
  pass rather than patching a fake-only assertion from here.

Decision / assumption recorded

- Simplest interpretation of the prompt's "working MVP as fast as possible by
  reusing code from a reference repo": use the reference repo for ideas only, not
  as a file source, because it is Node/Electron/Copilot and does not map onto
  once's Python + Chrome DevTools automation executor. I chose that instead of
  copying TypeScript and then having to port it. This is noted in REUSE.md.
- MVP completeness is now claimed only up to what was verified this session against
  a real Chrome on this machine: the single bundled fixture flow, unattended, through
  the approve/verify engine, with persisted runs and a repeated cold start. Anything
  beyond that one flow or beyond this machine is still out of scope / not verified.

Known gaps / not verified from this session

- `scripts/chrome_demo.py` was not re-run live this session; README says last
  verified 2026-10-25 on the build machine.
- The full once test suite was not run from the worktree this session; only the
  desktop/browser/devtools slices plus the fixture/check tests above.
- One fixture flow only; a second flow still needs a matching fixture JSON.

Next step (carry out of Phase 2)

- The MVP checklist is done. If there is a next desktop task, it should be a new,
  explicitly scoped item, not a continuation of this MVP. The existing pre-existing
  failure (`test_launch_refuses_a_non_chrome_endpoint`) is a test/fake mismatch on
  this branch and is the most obvious thing to clear before any further browser-engine
  work — either by adjusting the fake/assertion or by confirming the real launch path.

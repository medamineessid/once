# Once — AI Engineering Log

Append-only. Format per AGENTS.md. Human fills in the "Human review" line.

## 2026-10-21 — Step 0: Pre-flight, evidence, decisions   (commit: n/a — git repo not yet initialised; Step 1 runs `git init`)

- Task: Establish a verified, pinned toolchain decision record without writing application code: detect environment, look up current facts (Python support status, PySide6 + dev-tool versions/compatibility, Microsoft naming docs, `st_birthtime` availability), choose the Python version, record everything in `docs/decisions.md`.
- AI contribution: created `once/` folder, `AGENTS.md` (Master Prompt verbatim), `docs/decisions.md` (evidence + D1–D10 + version decision), this log. No application code written (per step constraint).
- Defect found: two retrieval attempts failed and were worked around honestly — (a) pypi.org/project/Send2Trash/ and /ruff/ served a bot "Client Challenge" page instead of content → used `pip index versions` (live PyPI query) and the PyPI JSON API; (b) github.com/arsenet/send2trash/releases returned 404 (wrong owner) → correct repo is arsenetar/send2trash, release date taken from a search snippet and flagged as best-evidence in decisions.md.
- Verification: ran locally — `py -0p` (3 interpreters listed), `python --version` (3.14.3), `git --version` (2.55.0.windows.4), `cmd //c ver` (10.0.26300.9550), `st_birthtime` presence check on 3.14.3 and 3.13.5 (True/True), `pip index versions` for pytest/pytest-cov/pytest-qt/ruff/pyinstaller/send2trash (latest: 9.1.1 / 7.1.0 / 4.5.0 / 0.17.1 / 6.22.3 / 2.1.0), `pip install --dry-run send2trash==2.1.0` on 3.14 → "Would install Send2Trash-2.1.0" exit 0. Fetched and cited: devguide.python.org/versions, pypi.org/project/PySide6 (6.12.0, Requires-Python >=3.10,<3.16, win_amd64 abi3 wheel present), learn.microsoft.com naming-a-file (reserved chars/names incl. superscript variants), pypi.org/pypi/send2trash/2.1.0/json (classifiers to 3.14). NOT verified: send2trash 2.1.0 release date (search snippet only), ruff `target-version = "py314"` support (checked at Step 1).
- Outcome: PASSED
- Human review: 

## 2026-10-22 — Draft editing and history detail inspection   (commit: 53e4ce0)
- Task: Improve the workflow editor and execution-history surface without
  moving workflow logic into the UI.
- AI contribution: added draft step reordering and removal, regenerated stable
  draft IDs after removal, selected-history result/evidence rendering, and
  thread-lifecycle locking until the worker thread finishes.
- Defect found: the GUI previously re-enabled controls as soon as the worker
  requested thread shutdown, allowing a second run attempt while the QThread
  was still alive; controls now re-enable from the thread-finished signal.
- Verification: `.\.venv\Scripts\ruff.exe format .` completed; `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`; `.\.venv\Scripts\python.exe -m pytest -q` printed `52 passed, 2 skipped`; `git diff --check` reported no whitespace errors.
- Outcome: PASSED
- Human review:

## 2026-10-22 — AI-assisted recorder specification amendment   (commit: pending)
- Task: Amend the product specification for AI-assisted recording while
  preserving deterministic execution, validation, privacy, and offline-first
  requirements.
- AI contribution: added the proposal-only AI contract, cloud consent and
  credential policy, recording privacy requirements, and revised recorder and
  replay roadmap entries; recorded the user's provider and credential
  decisions.
- Defect found: the previous specification listed desktop recording and cloud
  AI as permanently out of scope, which contradicted the approved recorder
  direction; the amendment now scopes them without permitting unrestricted
  execution.
- Verification: reviewed the affected specification and decision sections;
  no application code or dependency manifests were changed.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Bounded retries and postconditions   (commit: 7f65d76)
- Task: Add deterministic bounded retries, cancellation between attempts, and
  an optional path-existence postcondition to workflow steps.
- AI contribution: extended the workflow model and versioned JSON format,
  implemented retry attempt evidence and postcondition checks, and added
  engine/storage regression tests.
- Defect found: the first retry implementation checked cancellation before the
  initial attempt, changing the existing cancellation contract; the check now
  occurs only between attempts.
- Verification: `.\.venv\Scripts\ruff.exe format .` completed;
  `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`;
  focused pytest printed `20 passed, 1 skipped`.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Recorder compatibility and local event-log foundation   (commit: e12872e)
- Task: Verify recorder-library compatibility on Windows/Python 3.14 and add
  privacy-filtered local recording storage with deterministic raw drafts.
- AI contribution: pinned and smoke-tested `mss`, `pynput`, `pywinauto`, and
  `pywin32`; added immutable recording models, password redaction, JSON
  storage/deletion, and a non-runnable raw draft representation.
- Defect found: the initial redaction condition was unnecessarily complex and
  could obscure the password-only rule; simplified it to redact only events
  explicitly identified as password-field input.
- Verification: PyPI metadata was reviewed; package installation completed;
  monitor and UI Automation probes succeeded; `.\.venv\Scripts\ruff.exe
  check .` printed `All checks passed!`; recorder tests printed `3 passed`.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Provider-independent AI proposal boundary   (commit: e9af2bc)
- Task: Add an offline-testable AI provider contract, bounded interview
  behavior, approved credential sources, and an opt-in Gemini adapter.
- AI contribution: added provider request/response models, deterministic fake
  provider, strict draft validation, Windows Credential Manager lookup with
  environment fallback, and a standard-library Gemini REST adapter.
- Defect found: the first credential probe decoded Windows generic credential
  bytes as UTF-16; corrected it to UTF-8, matching the stored API-key format.
- Verification: `.\.venv\Scripts\ruff.exe format .` completed;
  `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`;
  provider tests printed `3 passed`; no live network request was made.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Bounded provider-driven interview   (commit: 6ceb702)
- Task: Coordinate provider questions and user answers without placing
  orchestration logic in Qt or allowing unbounded interview loops.
- AI contribution: added immutable interview state, bounded answer handling,
  empty-answer rejection, and provider-to-draft completion behavior.
- Defect found: none after focused testing; the session deliberately treats
  provider questions as conversation state and never executes the returned
  workflow.
- Verification: `.\.venv\Scripts\ruff.exe format .` completed;
  `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`;
  focused pytest printed `2 passed`.
- Outcome: PASSED
- Human review:

## 2026-10-22 — OS recorder adapter boundary   (commit: 1ac2ae8)
- Task: Add replaceable Windows capture adapters without placing OS APIs in
  the Qt UI or deterministic workflow engine.
- AI contribution: added injected `pynput` mouse/key capture, MSS keyframe
  capture, and best-effort pywinauto element metadata capture.
- Defect found: none after focused adapter tests; keyboard capture is opt-in
  and password-field key events are omitted.
- Verification: `.\.venv\Scripts\ruff.exe format .` completed;
  `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`;
  focused pytest printed `2 passed`; tests used injected callbacks and did not
  start global listeners or send input.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Controller and UI recording lifecycle   (commit: 16ee698)
- Task: Expose explicit Record/Stop controls through the controller without
  putting capture or persistence logic in the Qt layer.
- AI contribution: added a controller-owned recording service, application-data
  recording storage, and main-window Record/Stop actions with shutdown cleanup.
- Defect found: the first busy-state implementation would enable Stop after a
  workflow completed even when no recording was active; it now checks the
  controller's live recording state.
- Verification: `.\.venv\Scripts\ruff.exe format .` completed;
  `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`;
  focused pytest printed `10 passed`; no global listener was started.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Recording review and local-first approval UI   (commit: b578c03)
- Task: Connect saved recordings to review, offline analysis, bounded
  interview, proposal preview, explicit approval, deletion, execution, and
  persisted history.
- AI contribution: added recording timeline and metadata display, offline
  Analyze action, interview answer controls, proposal preview, approve/save
  action, explicit recording deletion, and a UI journey regression test.
- Defect found: the first UI journey test filled the workflow-name field
  instead of the interview answer field and opened a modal error; corrected it
  to target the dedicated answer input.
- Verification: focused UI journey printed `1 passed`; full verification is
  recorded after this milestone commit.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Approved proposal execution boundary   (commit: pending)
- Task: Ensure approved proposals have a dedicated controller execution path
  and document the complete local-first recording journey.
- AI contribution: added `run_approved`, updated the README demo instructions,
  and clarified current recording and offline-analysis capabilities.
- Defect found: none after adding the approval execution regression to the
  connected journey test.
- Verification: final full verification is recorded after this milestone
  commit.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Policy-gated read-only replay subset   (commit: pending)
- Task: Provide a real, safe replay boundary with an explicit allowlist and
  dry-run behavior.
- AI contribution: added `ReplayPolicy` and `ReplayExecutor`, allowing only
  read-only path inspection and existence verification with bounded steps.
- Defect found: the first test pass exposed an import-order lint error; the
  test imports were formatted and rerun.
- Verification: `ruff format engine\replay.py tests\test_replay.py`;
  `ruff check engine\replay.py tests\test_replay.py` passed; `pytest -q
  tests\test_replay.py` passed with 3 tests; `git diff --check` passed.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Controller and UI replay preview integration   (commit: pending)
- Task: Connect the replay allowlist to controller and Qt preview/execution
  actions with explicit authorized-folder selection and confirmation.
- AI contribution: added replay previews, controller `preview_replay` and
  `run_replay` entry points, replay-aware workers, and UI policy status,
  cancellation, progress, and confirmation controls.
- Defect found: the first lint run found an import-order issue in the worker;
  it was corrected before full verification.
- Verification: targeted replay, recording-flow, worker, and GUI tests passed;
  final full verification is recorded after this milestone commit.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Honest observed and inferred action presentation   (commit: pending)
- Task: Make the recording-to-proposal boundary explicit without claiming
  unsupported clicks, keystrokes, or reports can be replayed.
- AI contribution: labeled the recording timeline as observed/redacted data
  and added replay permission plus `source=AI inference` to proposal steps.
- Defect found: the first expected preview assertion retained the old format;
  it was updated to assert the new permission and provenance text.
- Verification: targeted recording, replay, and GUI tests passed with 15
  tests; final full verification is recorded after this milestone commit.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Replay cancellation and persisted-history coverage   (commit: pending)
- Task: Verify replay cancellation, progress reporting, and history persistence
  through the controller boundary.
- AI contribution: bounded replay preview eligibility by policy step limits and
  added a controller-level cancellation/history regression test.
- Defect found: the first assertion treated `WorkflowService.history()` as
  returning `HistoryRecord`; the actual service contract returns `WorkflowRun`.
  The assertion was corrected.
- Verification: targeted replay tests passed after the correction; final full
  verification is recorded after this milestone commit.
- Outcome: PASSED
- Human review:

## 2026-10-22 — First verified Windows UI Automation inspection   (commit: pending)
- Task: Add one narrowly scoped, read-only UI Automation action with explicit
  window identity and no focus or input fallback.
- AI contribution: added `INSPECT_WINDOW`, strict JSON target validation,
  `PywinautoWindowInspector`, replay policy integration, evidence, controller
  wiring, and persistence tests.
- Defect found: the first controller wiring passed the inspector to approved
  execution but not general replay; targeted tests caught and corrected it.
- Verification: fake-provider tests cover exact identity and ambiguity; a real
  Windows probe found 9 titled windows and completed identity inspection;
  final suite verification is recorded after this milestone commit.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Runtime approval-gate hardening   (commit: pending)
- Task: Prevent callers from bypassing explicit proposal approval by ignoring
  the `ApprovedProposal` type annotation.
- AI contribution: added runtime type checks to controller save and execution
  entry points and a regression test for both paths.
- Defect found: the first targeted lint run found an unused import and import
  ordering issue in the new regression test; both were corrected.
- Verification: final full verification is recorded after this milestone
  commit.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Read-only UI element inspection   (commit: pending)
- Task: Identify one unique UI Automation control inside one verified window
  without focus, input, text access, or mutation.
- AI contribution: added `INSPECT_UI_ELEMENT`, nested target validation,
  exact descendant matching, safe metadata evidence, replay/controller
  integration, persistence coverage, and ambiguity/error handling.
- Defect found: provider `ExecutionError` initially escaped the workflow runner;
  it was converted into an accurate failed step result and tested.
- Verification: deterministic provider and controller tests passed. A
  disposable Once process was launched with isolated local app data; real
  UI Automation found the replay-preview button by its exposed AutomationId
  and returned non-sensitive metadata. Final full verification follows.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Spec alignment with orchestrator vision   (commit: pending)
- Task: Align the authoritative scope and safety contract with the supervised
  test-and-fix product and define the Hotix synthetic-invoice target.
- AI contribution: rewrote the primary product/scope sections, added
  orchestrator invariants O1-O8 and decisions D11-D14, created
  `docs/product_vision.md`, and updated the README and progress log.
- Defect found: the prior specification did not define bounded evidence-driven
  test-and-fix work or the initial invoice-verification target.
- Verification: `git fetch`, `git status --short --branch`, and
  `git log origin/main -3 --oneline` completed; `git diff --check` is run
  before commit.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Headless acceptance-case verifier slice   (commit: 7ad9987)
- Task: Verify synthetic invoice outputs through an allowlisted command and
  produce bounded redacted JSON and Markdown evidence.
- AI contribution: added strict acceptance-case models, exact argv command
  allowlisting, bounded subprocess execution, exact/numeric-tolerance/
  case-insensitive comparisons, failure statuses, redaction, and evidence
  persistence.
- Defect found: the first test run used an overly short timeout for crash and
  malformed-output cases and asserted against a redaction marker; both tests
  were corrected. Ruff also required an explicit no-shell subprocess boundary.
- Verification: targeted verifier tests pass (`9 passed`); full suite and
  smoke verification are pending.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Gemini credential transport hardening   (commit: pending)
- Task: Verify the official Gemini authentication guidance and prevent API keys
  from appearing in request URLs.
- AI contribution: changed the REST adapter to use the documented
  `x-goog-api-key` header and added a regression test covering the request URL,
  header, and timeout.
- Defect found: the adapter initially appended the API key to the URL query
  string.
- Verification: official Gemini documentation was fetched; focused provider
  tests passed; no live network request was made.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Local recording review and approval flow   (commit: pending)
- Task: Connect persisted recordings, deterministic raw drafts, bounded
  interviews, proposal previews, explicit approval, and controller persistence.
- AI contribution: added recording listing/loading/deletion, proposal preview
  and approval types, an approved-save controller boundary, and a connected
  local-first integration test.
- Defect found: none after focused verification; the fake provider and
  recorder are injected and no cloud call or real input capture is used.
- Verification: `.\.venv\Scripts\ruff.exe format .` completed;
  `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`;
  focused pytest printed `6 passed`.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Revised vision milestone: workflow foundation   (commit: 2eaecb4)
- Task: Reconcile the file-management-first specification with the broader
  workflow automation vision and implement a real, testable orchestration base.
- AI contribution: revised the product definition and roadmap; added immutable
  workflow models, deterministic execution with failure propagation and
  cancellation, a Qt-free controller service, and a minimal UI trigger.
- Defect found: the existing controller package contained only `__init__.py`;
  the first implementation therefore added the missing service explicitly
  rather than placing workflow logic in the UI.
- Verification: `.\.venv\Scripts\ruff.exe format .` reformatted one file;
  `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`;
  `.\.venv\Scripts\python.exe -m pytest -q` printed `25 passed, 1 skipped`;
  `QT_QPA_PLATFORM=offscreen .\.venv\Scripts\python.exe app.py --smoke-test`
  exited 0. The skipped test reported that symbolic links are unavailable.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Milestone 1: workflow lifecycle validation   (commit: d6c02af)
- Task: Ensure malformed workflow definitions are rejected before execution.
- AI contribution: added bounded validation for workflow and step identifiers,
  names, message sizes, and duplicate step IDs.
- Defect found: the first new test expected wording that did not match the
  deliberately plain-language validation message; corrected the test.
- Verification: `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`;
  targeted pytest printed `16 passed in 0.15s`.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Milestone 2: versioned workflow persistence   (commit: b1feb9d)
- Task: Save and reopen strictly validated workflow definitions locally.
- AI contribution: added a versioned JSON representation, strict known-key and
  step-kind validation, UTF-8 save/load helpers, and isolated persistence tests.
- Defect found: none after reviewing the implementation and targeted tests.
- Verification: `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`;
  targeted pytest printed `15 passed in 0.32s`.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Milestone 3: SQLite execution history   (commit: 375dc79)
- Task: Persist real workflow runs and step outcomes, then connect the
  controller service to that history.
- AI contribution: added UTC run timestamps, SQLite schema and repository,
  history reconstruction, and controller integration tests for success and
  failure runs.
- Defect found: the first history reconstruction returned raw strings instead
  of enum values; fixed it by converting persisted statuses back to their
  domain enums.
- Verification: `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`;
  targeted pytest printed `17 passed in 0.36s`.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Lifecycle validation hardening   (commit: 0c4d791)
- Task: Prevent programmatic workflow callers from bypassing known step-kind
  validation.
- AI contribution: added explicit enum-type validation and a regression test
  for unknown step kinds.
- Defect found: an invalid string kind could otherwise fall through the runner
  as a successful report step.
- Verification: `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`;
  full pytest printed `39 passed, 1 skipped`; the offscreen app smoke test
  exited 0.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Milestone A: GUI workflow vertical slice   (commit: pending)
- Task: Make the real engine, workflow storage, and execution history usable
  through the Qt application without bypassing the controller boundary.
- AI contribution: added controller-owned app-data wiring, saved workflow
  listing/loading/saving, selected-workflow execution, history rendering, and
  GUI smoke coverage.
- Defect found: the placeholder-window smoke assertion expected the old startup
  label after the GUI became functional; updated the test to assert the new
  user-facing controls.
- Verification: `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`;
  focused pytest printed `13 passed in 1.10s`.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Milestones B/C: authorized action and verification   (commit: fb7dabf)
- Task: Add a reusable, bounded read-only path action with observable evidence
  and persistence of that evidence.
- AI contribution: added `INSPECT_PATH` and `VERIFY_PATH_EXISTS` steps,
  authorized-root checks, VERIFIED/INCONCLUSIVE outcomes, evidence capture,
  JSON target persistence, SQLite evidence persistence, and schema migration.
- Defect found: the first SQLite schema change did not account for existing
  databases created before the evidence column; added a narrow additive
  migration and regression coverage.
- Verification: `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`;
  full pytest printed `44 passed, 1 skipped`; the offscreen app smoke test
  exited 0.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Milestone A extension: declarative workflow editor   (commit: cdedb09)
- Task: Allow users to create and save supported workflows from the GUI rather
  than requiring hand-authored JSON.
- AI contribution: added a small controller-backed form for workflow name,
  step name, message, and the supported REPORT/FAIL step kinds.
- Defect found: the first implementation omitted the `StepKind` UI import;
  the application smoke test caught the NameError and the import was fixed.
- Verification: `.\.venv\Scripts\ruff.exe check --fix .` fixed two import-order
  issues; final lint printed `All checks passed!`; full pytest printed
  `45 passed, 1 skipped`; the offscreen app smoke test exited 0.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Application resource shutdown hardening   (commit: ae43b85)
- Task: Close controller-owned SQLite history connections when the Qt
  application exits.
- AI contribution: added explicit service/history close methods, a Qt close
  event hook, and smoke-path shutdown.
- Defect found: coverage still reports one ResourceWarning during the combined
  subprocess/Qt coverage run; the focused GUI test does not reproduce it.
- Verification: full pytest printed `45 passed, 1 skipped`; Ruff printed
  `All checks passed!`; the offscreen smoke test exited 0; coverage printed
  `83%` with `45 passed, 1 skipped, 1 warning`.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Multi-step editor and result evidence view   (commit: dfcf14a)
- Task: Let the GUI assemble multiple supported steps and expose every
  execution result and evidence item.
- AI contribution: added draft step accumulation, multi-step workflow saving,
  and per-step result/evidence rendering in the main window.
- Defect found: none after focused GUI and engine verification.
- Verification: `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`;
  focused pytest printed `14 passed in 1.72s`.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Verification safety and schema compatibility   (commit: b0bc57c)
- Task: Prevent symlink targets from bypassing authorized-root checks and keep
  existing schema-version-one workflows loadable after adding target fields.
- AI contribution: added explicit pre-resolution symlink rejection, schema
  version two with safe version-one loading, and regression tests.
- Defect found: path verification originally resolved the target before
  checking whether the user-selected path itself was a symlink.
- Verification: `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`;
  focused pytest printed `14 passed, 1 skipped`.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Responsive cancellable workflow execution   (commit: 7a06207)
- Task: Move workflow execution off the Qt GUI thread and expose cooperative
  progress/cancellation without introducing Qt into the engine.
- AI contribution: added engine progress callbacks, controller callback
  plumbing, a Qt worker wrapper, busy/cancel UI state, threaded SQLite
  serialization, and worker/UI regression tests.
- Defect found: SQLite connections were created on the GUI thread but used by
  the worker thread; enabled explicit cross-thread connection support and
  serialized repository access with an `RLock`.
- Verification: `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`;
  full pytest printed `51 passed, 2 skipped`; the offscreen app smoke test
  exited 0; coverage printed `84%` with `51 passed, 2 skipped, 1 warning`.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Step 1: Project foundation   (commit: d1375f0)
- Task: Establish the launchable Qt skeleton, pinned development environment, test fixtures, architecture guards, and quality configuration.
- AI contribution: completed the dependency manifest, Ruff and pytest configuration, deterministic Windows-safe fixture writes, and Step 1 validation.
- Defect found: fixture text writes used Windows newline translation, making the expected deterministic byte size wrong; switched fixture creation to UTF-8 bytes. Ruff's security and naming rules also needed test-specific ignores for required subprocess and `test_S<n>` safety names.
- Verification: `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` installed PyInstaller 6.22.3; PySide6 import probe printed `PySide6 import ok`; `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`; `.\.venv\Scripts\ruff.exe format --check .` printed `17 files already formatted`; `.\.venv\Scripts\python.exe -m pytest -q` printed `13 passed in 0.57s`; `.\.venv\Scripts\python.exe app.py --smoke-test` exited 0.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Step 2: Scanner and filters   (commit: 3c6b4c9)
- Task: Build a read-only folder scanner and pure filter utilities that return immutable `FileEntry` objects without mutating the filesystem.
- AI contribution: created `engine/scanner.py`, `engine/filters.py`, and `engine/fs.py`; expanded the domain model in `engine/models.py`; added `tests/test_scanner.py` covering hidden files, symlinks, Unicode names, suffix rules, and deterministic scans.
- Defect found: the first scanner version treated all files as hidden because it used Windows attribute checks incorrectly on a path object. The test fixture also used newline-sensitive byte-size assumptions that were not Windows-safe.
- Verification: `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`; `.\.venv\Scripts\ruff.exe format --check .` printed `20 files already formatted` after the final format pass; `.\.venv\Scripts\python.exe -m pytest -q` printed `20 passed, 1 skipped in 1.32s`.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Phase 0: Resume check   (commit: pending)
- Task: Confirm the repository boundary and resume state, preserve the existing Step 0 evidence, and establish progress tracking.
- AI contribution: verified the workspace, Git state, environment pins, existing skeleton, and baseline quality results; added progress tracking.
- Defect found: baseline fixture expected POSIX newline byte size on Windows; this is recorded for the Step 1 foundation fix.
- Verification: `git rev-parse --show-toplevel` returned `C:/Users/DELL/once` with no commits; `py -0p`, `python --version`, and `git --version` returned the recorded environment; `.venv` package list showed the pinned packages; smoke test passed; pytest reported `1 failed, 12 passed`; Ruff check passed and format check reported `tests/test_architecture.py`.
- Outcome: PASSED
- Human review:

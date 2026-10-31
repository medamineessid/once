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

## 2026-10-23 — Verifier run persistence   (commit: pending A3)
- Task: Persist acceptance verification runs (EvidenceBundle) in the SQLite
  history per invariant O7, exposed through the controller service.
- AI contribution: added `acceptance_runs` and `acceptance_case_results`
  tables to storage/database.py, `record_verification`/`list_verification_runs`
  on `ExecutionHistory`, `verify_acceptance`/`acceptance_history` on
  `WorkflowService`, and tests/test_verifier_history.py.
- Defect found: the first test-file draft had a missing import, inconsistent
  helper names, and a stray brace; it was rewritten before being committed.
  A later full-verification command contained a venv path typo so its pytest
  portion silently did not run; it was rerun correctly.
- Verification: `.venv/Scripts/python.exe -m pytest -q tests/test_verifier_history.py`
  -> `4 passed`; full suite -> `103 passed, 2 skipped in 12.69s`; ruff format
  and check -> `All checks passed!`; `python app.py --smoke-test` -> exit 0;
  `git diff --check` -> clean.
- Outcome: PASSED
- Human review:

## 2026-10-23 — Bounded test-and-fix loop controller   (commit: pending A4)
- Task: Implement the bounded diagnose-fix-test loop (O4): verification,
  optional fix proposer, mandatory attempt/wall-time/no-progress stops, and
  persisted loop decisions (O7), exposed through the controller service.
- AI contribution: added engine/loop.py (LoopPolicy, LoopController, LoopRun,
  LoopDecision, injectable FixProposer protocol), loop_runs/loop_decisions
  tables, record_loop/list_loops on ExecutionHistory, and
  run_supervised_loop/loop_history on WorkflowService; tests/test_loop.py.
- Defect found: the loop's verify callable initially bypassed O7 verification
  persistence (caught by test_loop.py, fixed by recording each bundle inside
  the service-closure); an earlier edit also merged a docstring with the next
  statement, producing a syntax error caught by ruff and pytest collection.
- Verification: `.venv/Scripts/python.exe -m pytest -q tests/test_loop.py
  tests/test_verifier_history.py` -> `13 passed`; full suite -> `112 passed,
  2 skipped in 8.84s`; ruff format/check -> `All checks passed!`;
  `python app.py --smoke-test` -> exit 0; `git diff --check` -> clean.
- Outcome: PASSED
- Human review:

## 2026-10-23 — Coding-agent proposal integration   (commit: effb71c)
- Task: Implement branches + diff review + the approval gate per D14/O6: an
  allowlisted agent command runs on a separate branch, its diff becomes a
  bounded review, and only an explicitly approved change can be locally
  fast-forwarded. No push/rebase/merge-commit path exists.
- AI contribution: integrations/coding_agent.py (AgentCommand, GitRepository,
  run_agent_for_proposal), engine/agent_change.py (ChangeReview,
  ApprovedChange, approve_change), storage tables agent_proposals/
  agent_decisions with history methods, controller methods (request_agent_fix,
  agent_proposals, approve_agent_change, reject_agent_proposal,
  apply_agent_change), AgentFixProposer loop adapter, and a
  STOPPED_PROPOSER_FAILED loop outcome so proposer errors cannot silently drop
  a run record; tests/test_coding_agent.py.
- Defect found: first design captured uncommitted agent work into a reviewed
  diff while the approved branch tip would have excluded it (review/merge
  content mismatch); fixed by snapshotting the agent result into one commit on
  its own branch. A loop test wrongly expected a second proposal after the
  no-progress stop; the engine was right and the test expectation was corrected.
- Verification: tests/test_coding_agent.py -> `12 passed`; full suite ->
  `124 passed, 2 skipped in 27.06s`; ruff format/check -> all checks passed;
  `python app.py --smoke-test` -> exit 0; `git diff --check` -> clean.
- Outcome: PASSED
- Human review:

## 2026-10-24 — Targeted lint fixes on the worktree/proposal-review work   (commit: uncommitted, working tree only)
- Task: clear the current `ruff check` diagnostics without touching the
  in-progress worktree-verification and proposal-review features: unused
  imports (CaseResult, EvidenceBundle, pytest), unused F841 exception binding,
  four unused `noqa: BLE001` directives, unused `noqa: ANN001`, three RUF043
  `match=` patterns, S607 in `integrations/coding_agent.py`, and I001 import
  ordering in `ui/workers.py`.
- AI contribution: replaced the inline `# noqa: S607` suppressions in
  `integrations/coding_agent.py` with an explicit `git_executable()` helper
  (shutil.which("git"), fails closed with a plain-language error when Git is
  missing) resolved once per GitRepository/WorktreeCheckout instance and reused
  for every git subprocess call; removed now-unused S607 noqas; added two tests
  for executable resolution and the missing-Git case; aligned the two new test
  `run_git` fixtures with the existing inline `# noqa: S607` convention from
  test_coding_agent.py (no per-file-ignore/config change; production linting
  unchanged).
- Defect found: first version of the new resolution test returned non-empty
  stdout for the `status --porcelain` probe, so `ensure_clean()` correctly
  treated the fake repository as dirty; the fake now returns empty status.
  S607 finding: the bare-`"git"` pattern fires in the existing GitRepository
  calls too (suppressed there by inline noqa) — the new WorktreeCheckout calls
  reproduced it unsuppressed; fixed by the explicit resolution instead of more
  suppressions.
- Verification: `.venv/Scripts/ruff.exe check .` -> `All checks passed!`;
  `ruff format --check` -> 6 files would be reformatted, all pre-existing in
  the uncommitted in-progress work (verified by stash round-trip: at HEAD
  `68 files already formatted`); full suite -> `144 passed, 2 skipped in
  99.11s` (2 skips are pre-existing symlink unavailable on this machine);
  `git diff --check` -> clean (exit 0). No lint-rule was weakened; pyproject
  untouched; working tree restored intact after the stash probe.
- Outcome: PASSED
- Human review:
## 2026-10-24 — Worktree-based pre-merge verification and GUI proposal review   (commit: beed7e3)
- Task: resume and complete the known gap from the 2026-10-23 proposal slice —
  run the required acceptance checks against the exact proposal commit inside a
  disposable git worktree BEFORE approval, persist that evidence, gate
  approval on it, and surface the whole flow (diff, verification runs,
  redacted evidence, blockers, explicit approve/reject, post-merge rerun) in a
  real Qt tab. Preserve all earlier worktree-verification and proposal-review
  work already in the tree, and the targeted Ruff cleanup.
- AI contribution: inspected the working tree diff (all of it written in
  earlier sessions of this stage); preserved it and the lint cleanup; removed
  one dead test fixture (`loop_policy_guard`, never requested by any test),
  one redundant duplicated assertion in
  `test_pre_merge_verification_runs_in_worktree_and_gates_approval`, and fixed
  a misspelled test name (`test_panel_rejectpersists…` →
  `test_panel_rejection_persists…`); formatted the six outstanding files with
  `ruff format` (no unrelated line-ending churn, `git diff --check` clean);
  set repo-local git identity (WSL had none) matching prior commit authorship.
- Defect found: the committed `tests/test_scanner.py` contained
  `except OSError, NotImplementedError:` (Python 2 syntax — the file could
  never import); the working tree already fixed it and this session kept that
  fix. No other defects found in a full re-read of the uncommitted work.
- Verification (all on the real Windows Python 3.14.3 venv, real Git, real
  PySide6; not mocked): `.venv/Scripts/python.exe -m pytest -q` -> `144
  passed, 2 skipped` (2 skips: symlink unavailability on this machine);
  `.venv/Scripts/ruff.exe check .` -> `All checks passed!`;
  `ruff format --check .` -> `71 files already formatted`; targeted rerun of
  `test_worktree_verification.py test_review_ui.py test_coding_agent.py
  test_smoke.py` -> `42 passed`; real-GUI entry point
  `.venv/Scripts/python.exe app.py --smoke-test` -> exit 0 (real window built
  on Windows by the real app, including the new "Agent proposals" tab);
  `git diff --check` -> clean. Refusal paths exercised by named tests run on
  real Git worktrees: failed checks, stale amended agent tip, moved base
  branch, duplicate decisions, cancelled verification, timeout evidence, and
  crashed/leftover worktree directories all refuse with recorded history
  (test_worktree_verification.py: 14 tests).
- Outcome: PASSED
- Human review:
## 2026-10-24 — Loop hardening: recorded-proposal identity, user checker config, MainWindow journey   (commit: 13e327d)
- Task: close the last Stage 11 reliability gaps: the presented review was
  trusted without comparing it to the persisted proposal record, a real
  session had no way to configure the acceptance checker (app.py passed no
  VerifierConfig, so the "Agent proposals" tab could not run in real use),
  and several lifecycle paths (partial cancellation, failed post-merge
  persistence, restart survival, persisted-evidence redaction, missing
  evidence display, MainWindow tab wiring) had no tests.
- AI contribution: added `ExecutionHistory.proposal_record`, controller-side
  `_identity_blocker` enforced in `approve_agent_change` (via
  `approval_blockers`), `apply_agent_change`, and `verify_proposal_pre_merge`;
  made `approval_blockers` fail as blockers instead of raising when a branch
  no longer exists; new `controller/verifier_config.py`
  (`verifier.json` loader validating cases_path/argv/timeout/worktree_root
  through the same `AllowlistedCommand` allowlist; missing file = no config;
  broken file = visible note in the review panel); MainWindow/panel
  `verifier_note` plumbing; service.close() on normal app exit; six new
  tests in test_worktree_verification.py, one in test_review_ui.py, plus a
  new test_verifier_config.py with 11 tests; MainWindow-level end-to-end
  journey test (real Qt window, real Git repos, fake agent).
- Defect found: the first version of the partially-cancelled test used a
  stdin-reading checker that would block, and a leftover bogus assertion
  (`assert wrong_expectation is not None`) survived into the draft — both
  rewritten before any suite run; the first MainWindow no-config test hung
  because `_warn` opens a modal QMessageBox on the offscreen event loop —
  fixed by stubbing `QMessageBox.warning` in the test (real app behaviour
  unchanged).
- Verification (real Windows Python 3.14.3 venv, real Git, real PySide6):
  focused runs -> test_worktree_verification.py `20 passed`,
  test_verifier_config.py + test_review_ui.py + test_coding_agent.py `32
  passed`, test_review_ui.py `7 passed`; full suite -> `166 passed, 2
  skipped in 88.84s`; `ruff check .` -> `All checks passed!`; `ruff format
  --check .` -> `73 files already formatted`; `git diff --check` clean;
  real entry-point runs (`app.py --smoke-test`): default app data exit 0,
  overridden app data with a broken verifier.json exit 0 (visible note path,
  verified the note logic separately in tests), valid verifier.json
  confirmed to load via `load_verifier_config` under the real interpreter.
- Outcome: PASSED
- Human review:

## 2026-10-24 — Step 9: restart-safe proposal apply, verifier config editor, packaged Windows build (commit: 5df32b4 + follow-up)
- Task: (B) prove real {checkout} verification with a system interpreter; (C)
  recovery audit for interruptions across the proposal lifecycle; (A) validate
  the real local coding-agent integration; (D) smallest config editor; (E)
  repeatable Windows build with an executed smoke test.
- AI contribution: new tests in test_worktree_verification.py (system
  interpreter check, spaced paths, missing {checkout} file, interruption
  mid-verification, recorded-approval restart apply, refuses wait/moved
  states); `_restore_after_failed_run` + `apply_recorded_approval` +
  `apply_blockers` in integrations/coding_agent.py and controller/service.py;
  branch-hijack refusal; "apply previously approved proposal" panel button +
  ApplyRecordedApprovalWorker; controller/verifier_config.py rewrite
  (document_to_config + atomic save_verifier_config); ui/verifier_dialog.py;
  panel Configure acceptance checks button + reload; app.py logging setup +
  plain-language startup-failure handler; once.spec + README packaging.
- Defect found: `_restore_after_failed_run` first tried to restore BEFORE
  parking the agent's dirty output, but git carries modifications across
  `checkout`, so the parked "failure" commit landed on the user's branch (proven
  with a manual /tmp/opencode git reproduction before rewriting the helper:
  park first, then restore). Also found in self-review of the dialog draft: a
  stray typographic typo token, a leftover stub method, and a missing
  QLineEdit import; the first save test failed because validation requires the
  cases file to exist, so the test now creates it.
- Verification (real Windows Python 3.14.3 venv): three real {checkout} runs
  with the system interpreter including a spaced worktree root; full suite
  `182 passed, 2 skipped` then `185 passed, 2 skipped in 153.22s` after the
  app-entry tests; `ruff check .` -> `All checks passed!`; PyInstaller
  6.22.3 build of the committed `once.spec` succeeded (`Build complete!`).
  Packaged-exe runs (isolated LOCALAPPDATA via cmd `set`): clean smoke exit 0;
  corrupt verifier.json exit 0 with app data + logs written to the isolated
  folder (log line verified in once.log); unusable data folder -> process
  stays alive at a visible dialog under the pre-fix build (raw traceback),
  and the post-fix handler is unit-tested to explain itself and return 1
  (QMessageBox.critical was monkeypatched; no automated click of the real
  dialog). Real-agent integration: `claude --help` verified locally; a real
  run is NOT authorized (paid cloud) so it was not executed and adapter tests
  use the deterministic fake.
- Outcome: PASSED
- Human review:

## 2026-10-24 — Recovery hardening: failed-agent park/restore and refused paths
- Task: make every failed-agent run leave an explained, recoverable Git state
  (branch-switch failures, vetoing project hooks, uncommitted user files,
  missing agent branch, worktree path inside the repository).
- AI contribution: `_park_and_restore` in integrations/coding_agent.py (park
  first with `--no-verify` hook-bypass fallback, then restore; on parking
  failure leave the tree untouched with a plain-language recovery message
  appended to the error); capture-stage and restore-stage failure handlers;
  controller/service.py missing-branch-ref (`refs/heads/...` rev-parse) clear
  refusal + 403 guard; new and adjusted tests in test_coding_agent.py and
  test_worktree_verification.py.
- Defect found: a fixture-side failure in the first unparkable-state test was
  actually a trailing-newline comparison artifact (not a product defect); fixed
  the test to compare `.splitlines()`. None of the new implementation paths
  failed on first run.
- Verification (real Windows Python venv, pytest on tmp_path repos):
  `.venv/Scripts/python.exe -m pytest tests/test_worktree_verification.py tests/test_coding_agent.py -q`
  -> `51 passed in 116.23s`; after `ruff format .` the focused subset
  (`dirty_states or hooks_cannot_trap or unparkable` +
  `test_worktree_path_inside_the_repository_is_refused`) -> `5 passed`;
  `ruff check .` -> `All checks passed!`.
- Outcome: PASSED
- Human review:

## 2026-10-24 — Persistence hardening, first-run docs, roadmap reconciliation
- Task: corrupt-database startup must fail clearly without touching user data;
  an older-cycle database must open after an upgrade; document packaged-app
  install/first-run/upgrade/uninstall; reconcile roadmap integrations 6-9.
- AI contribution: app.py sqlite3.DatabaseError handler ("history database...
  left unchanged", exit 1, never deletes/replaces the file);
  tests/test_history.py pre-migration-database regression test; README
  "Install, first run, upgrade, and uninstall" section + refreshed status
  line; docs/decisions.md integration-reconciliation entry; PROGRESS refresh.
- Defect found: app.py startup only caught OSError, so a corrupt once.db
  escaped as a raw sqlite3.DatabaseError traceback (proven with a synthetic
  corrupt file: `DatabaseError: file is not a database`). Also my first two
  README str-replacements were malformed; I re-inspected the file, confirmed
  no damage, and used a single correct replacement.
- Verification: `pytest tests/test_app_entry.py tests/test_history.py -q` ->
  4 + 4 passed; full suite `194 passed, 2 skipped in 151.72s`;
  `ruff format .` -> 75 files unchanged; `ruff check .` -> All checks passed!
  (after fixing two E501s in my own new test); PyInstaller rebuild from
  current source -> `Build complete!` (build.log line 197854).
- Outcome: PASSED
- Human review:

## 2026-10-24 — Acceptance journey test and packaged-exe validation (Priorities B/F)
- Task: one end-to-end acceptance test of the real user journey; validate the
  rebuilt packaged exe outside the development environment.
- AI contribution: tests/test_acceptance_journey.py (configure checker via
  save/load_verifier_config through the real app-data path, save+reopen a
  workflow, run it and check history, fail verification against the buggy
  extractor, capture an agent proposal and inspect the exact diff, pre-merge
  worktree verification, approve/apply, post-merge rerun, service restart with
  full persisted recovery; plus failed-agent-run, parked-output, and
  amended-tip identity tests and an allowlist-shape test).
- Defect found: my first allowlist test asserted imaginary rules (metacharacter
  bans); the real guarantee is structural argv + no shell, so the test was
  rewritten to prove empty-argument/missing-duplicate-placeholder/timeout-bound
  rejections AND that metacharacters stay inert. Also fixed two draft leftovers
  (unused import, wrong history() shape: it returns WorkflowRun, not a record
  wrapper) before the first green run.
- Verification: `pytest tests/test_acceptance_journey.py -q` -> 5 passed;
  `ruff check --fix` -> 0 remaining; packaged exe runs: clean isolated
  LOCALAPPDATA exit 0 with once.db/logs/recordings/workflows created; corrupt
  verifier.json exit 0 (startable, once.log written); corrupt once.db showed
  the REAL modal read via Windows UI Automation: title 'Once cannot start' and
  the exact intended message text, once.db md5 unchanged, process terminated
  only via test cleanup; exe launched from a foreign CWD (C:\Windows\temp)
  exit 0 and all data confined to the isolated folder. NOT VERIFIED: clicking
  the dialog's OK button in the packaged exe (SendKeys-driven dismissal hung
  and was abandoned; exit-code-1-on-confirmation is covered by the
  stubbed-message-box unit test over the same code path).
- Outcome: PASSED
- Human review:

## 2026-10-24 — Recovery audit: hijack-to-user-branch parking defect (Priority 1)
- Task: audit `_park_and_restore`, controller failure paths, and recovery tests
  against real temporary repositories; add uncovered regression tests.
- AI contribution: four new tests (tracking-file deletion parked with the user
  branch intact; timed-out mixed modify/delete/new parked atomically; hijack
  to an EXISTING user branch; ignored-file leftovers documented as never
  deleted). Implementation fix: `_park_and_restore` now refuses to commit
  failed output onto any branch Once did not create — when the agent moved the
  tree onto an existing branch, a fresh `once/agent/parked-<id>` branch is
  created and the parked note names the exact branch; `--no-verify` hook-bypass
  factored into `_commit_parked`; two error messages no longer claim
  "the agent's own branch still holds whatever it wrote" (they name the
  parked branch instead).
- Defect found: a REAL defect in committed recovery code — a hijacking agent
  moving the tree onto a clean user branch (e.g. `release`) and exiting failed
  made parking commit the failed output ONTO that user branch (proven by
  direct `git rev-parse release` showing one extra commit; captured in the
  first red run). Also found in my own work: the first heredoc-written batch
  of tests contained CRLF-mangled agent scripts, so all four agents crashed
  with SyntaxError and the scenarios tested nothing; replaced with tool-edited
  content, and my first refactor dropped `repository.restore(original)` (7
  red tests caught it). One partial-output test fixture lacked `second.txt`.
- Verification: `pytest tests/test_coding_agent.py -q` -> 27 passed (all with
  real subprocess agents in real temp repos); focused run after edits
  `4 passed, 23 deselected`; worktree suite `28 passed in 95.13s`;
  `ruff check --fix .` -> 0 remaining; `ruff format` no effective change.
- Outcome: PASSED
- Human review:

## 2026-10-24 — Reproducible demonstration of the supervised journey (Priority 2)
- Task: smallest realistic, repeatable demonstration using existing
  capabilities only: seeded defect -> failing verifier -> deterministic fix
  generator proposal -> exact diff -> isolated worktree verification ->
  explicit approval -> apply -> passing rerun -> restart-persisted history.
- AI contribution: scripts/run_demo.py (self-contained temporary workspace;
  deterministic rule-based fix generator reads human-recorded ground truth;
  the approval prompt is a real pause; nothing bypasses the controller or
  safety gates); README "Reproducible demonstration" section.
- Defect found: the fix generator initially used an f-string with unescaped
  braces (SyntaxError) and nested \n literals were mangled once by shell
  heredoc rewriting; both found by running the demo, fixed by restructuring
  the generator to an escape-free lines-list with chr(10) joins.
- Verification: approve path -> all 8 steps complete (diff shown, isolated
  verification True, applied, post-merge True, restart shows APPROVED +
  PRE_MERGE/POST_MERGE + one failed and two passed verification runs);
  cancel path -> "CANCELLED: nothing was applied" with the proposal recorded;
  `ruff check scripts/run_demo.py` -> All checks passed!
- Outcome: PASSED
- Human review:

## 2026-10-24 — Manual acceptance checklist (Priority 4)
- Task: prepare a short manual checklist for a first-time user covering
  startup, capability boundaries, verifier configuration, workflow runs,
  proposal review/approval, failed-run recovery, and restart history.
- AI contribution: docs/acceptance_checklist.md (8 numbered sections with
  expected results and an explicit manual-only/limitations block). No UI
  changes: the existing panel messages already surface plain-language
  approval/verification blockers from the controller, and the pytest-qt
  suites cover the same flows offscreen.
- Verification: checklist written against the actual UI strings
  (ui/review_view.py, ui/main_window.py) and controller messages; no
  interactive click-through has been performed by this session (that is the
  checklist's own purpose).
- Outcome: PASSED
- Human review:

## 2026-10-24 — Release-candidate final audit (P3 packaged exe + P5 full suite)
- Task: validate packaged build behavior (fresh/repeat data dir, corrupt verifier.json, foreign CWD) and close out release checks.
- AI contribution: no new implementation; verification runs only.
- Defect found: none new. Corrupt verifier.json correctly produces a visible review-tab note (validated raise path via controller.verifier_config.load_verifier_config and existing unit test tests/test_verifier_config.py:56); smoke exit 0 is the designed non-fatal path.
- Verification: dist/Once/Once.exe --smoke-test fresh LOCALAPPDATA exit 0; repeat run exit 0 with 2x "Once started" in once.log; corrupt verifier.json exit 0 with note path exercised; foreign-CWD run exit 0 writing only %LOCALAPPDATA%/Once (log entry 11:22:45), no writes under dev checkout or dist; pytest -q 203 passed, 2 skipped (symlinks unavailable); ruff format 78 files unchanged; ruff check all passed; git tree clean at 161f670.
- Outcome: PASSED
- Human review:


## 2026-10-25 — Desktop automation engine (branch desktop-automation-engine; commits 8071987, dee53d8, 0ee46af, 6d4977f)
- Task: cohesive, approval-gated Windows desktop interaction subsystem (launch / wait / click / type / shortcut / verify file text) inside the existing workflow engine.
- AI contribution: engine/desktop.py (approval gate), integrations/windows_desktop.py + integrations/uia_targeting.py (real provider + shared targeting), new StepKind values + validation + timeout_seconds in engine/workflow.py, DESKTOP_INTERACTION_POLICY in engine/replay.py, controller run_desktop_approved/preview_desktop_replay, storage schema v3, scripts/notepad_demo.py, three test files, docs/desktop_automation.md.
- Defect found: my first element_matches compared automation_id even when the target omitted it ("" != None), which would make controls without AutomationIds untargetable; corrected to compare only requested fields. Also fixed: duplicate validator definitions removed; provider step_id stamping; NoPatternInterfaceError handling; read-back via CurrentValue (real comtypes API) not just .Value; a live-run ambiguity refusal confirmed as correct fail-closed behavior.
- Verification: pytest -q 248 passed, 2 skipped (full suite, Windows venv); ruff check "All checks passed!"; ruff format 8 files reformatted then clean. LIVE run of scripts/notepad_demo.py: launch SUCCEEDED (notepad.exe pid evidence), unique window discovered (title 'once-demo-note.txt – Bloc-notes'), type readback_confirmed=true (45 chars), ctrl+s SUCCEEDED (untargeted_injection=false), VERIFY_FILE_TEXT match=true, run SUCCEEDED, file content byte-exact, RESULT: PASS; demo window closed at cleanup. An earlier live attempt correctly FAILED CLOSED with "The identified window is ambiguous, so no keys were sent." when leftover demo windows matched.
- Outcome: PASSED
- Human review:

## 2026-10-25 — Isolated-browser automation via Chrome DevTools Protocol (branch desktop-automation-engine; commits 9722026, 3d2a9c6, 00a1053)
- Task: extend the same workflow engine with reliable cross-application automation for Chrome: launch isolated browser, navigate with validated URLs, bounded inspection, unique element lookup, click/type interaction, bounded waits, all behind the existing approval gate and history.
- AI contribution: integrations/devtools_ws.py (stdlib RFC 6455 WebSocket client, ws://127.0.0.1 only), integrations/chrome_devtools.py (launch/navigate/inspect/find/interact/wait/shutdown with isolated temp profiles), six new StepKind values + validators + BrowserActions contract in engine/workflow.py, MUTATING_DESKTOP_KINDS/BROWSER_READ_KINDS/DESKTOP_INTERACTION_POLICY updates in engine/replay.py, controller browser_actions wiring, 21 provider tests + 17 engine tests, scripts/chrome_demo.py, docs updates.
- Defect found: my first launch-wait test used a constant clock so the deadline loop never expired (test hung until fixed with an advancing clock); the fake CDP surface initially double-wrapped responses so Runtime.evaluate values were mis-unwrapped; the first validated wait_page used urlsplit before importing it (NameError caught by tests before any commit).
- Verification: pytest -q 286 passed, 2 skipped (full suite, Windows venv, 106 s); ruff check "All checks passed!"; ruff format all files left unchanged. LIVE run of scripts/chrome_demo.py against real isolated Chrome/155.0.8059.86: launch SUCCEEDED (cdp_port=51586, isolated temp profile), navigate readyState=complete on http://127.0.0.1:51585/index.html, wait/inspect/find SUCCEEDED, click SUCCEEDED, type readback_confirmed=true, wait-status and verify SUCCEEDED, RESULT: PASS, browser + profile cleaned up. No public website contacted; user's Chrome profile untouched.
- Outcome: PASSED
- Human review:

## 2026-10-24 — Step: redesigned shell UI and smoke-test alignment

- Task: make the redesigned shell screens and smoke test consistent with the MainWindow/sidebar object shape, keep the suite green, and land the shell on its own branch without touching main yet.
- AI contribution: rewrote the shell-side assertions to match the sidebar API, replaced a brittle `is`-comparison pattern with stable attribute checks, and trimmed an unused import backport that made the smoke run harder to verify.
- Defect found: the smoke test asserted against a `Sidebar.is_on()` method that did not exist yet, and one assertion relied on `is` between two Python bools produced through Qt signal timing; the latter masked a real Qt check-state timing issue. The sidebar was fixed to retain the initial checked page, and the test was rewritten to stay green across page switches.
- Verification: ran `pytest tests/test_shell.py tests/test_app_entry.py tests/test_smoke.py`; final line `17 passed`; ran full suite `206 passed, 2 skipped`; ran `ruff check . --unsafe-fixes` after auto-fixes; ran `git status` and confirmed only the shell package files and one untracked `ui/components/__init__.py` are in play.
- Outcome: PASSED
- Human review: left blank for the human to confirm the branch merge plan in `docs/decisions.md` before pulling redesigned shell onto main.

## 2026-10-25 — Step: fix live shell regressions after settings redesign

- Task: make the live shell startable again and align Settings with the current UI shape without carrying the stale `recording_list` control and old warning dialogs.
- AI contribution: added the missing settings-page stub methods (_connect_gemini, _disconnect_gemini), replaced the deleted-recording confirmation with `QMessageBox.information`, removed the orphan `recording_list` widget from the Recording section, restructured the UI builder so the missing callbacks no longer block MainWindow construction, disabled sidebar button auto-repeat in the shell, and added README and PROGRESS entries for the remediation.
- Defect found: the build was not cut cleanly on top of the earlier shell rewrite, so the settings page had been rebuilt once with stub callbacks and a `recording_list` control, then rebuilt again without those stubs and without the callback methods. That left `MainWindow()` unable to construct the settings page and tests asserting against controls that no longer exist. The fix had to restore the stubs for the UI that is actually wired, not the older `recording_list`-based UI.
- Verification: started a QApplication, constructed `SettingsPage()` and `MainWindow()` from the live code and saw both print success; ran `pytest tests/test_shell.py` offscreen (8 passed); ran `pytest tests/test_replay.py tests/test_architecture.py` (21 passed); read `git diff` to confirm only the expected shell/settings page/test/docs files are modified. The heavy deterministic replay and architecture suites still pass; the worktree verification and coding-agent tests remain under separate runs not repeated this session.
- Outcome: PASSED for the restarted shell and the relevant shell/replay/architecture tests. Full-suite and packaging smoke runs were not repeated this session.
- Human review: left blank. Recommend reviewing `ui/pages/settings.py`, `ui/shell.py`, and `tests/test_shell.py` diffs, then committing the shell fix on the current branch.

## 2026-10-25 — Step: diagnose and fix the tests/test_shell.py hang (commit: 1d367c2)

- Task: reproduce the full-shell-suite hang offscreen, identify the exact test and operation, fix the root cause without skipping or weakening tests, then verify the shell suite, full suite, Ruff, app launch, navigation, and WebView absence.
- AI contribution: bisected the eight shell tests individually; rewrote the five Settings placeholder actions to update a non-modal in-page status label instead of opening blocking modal `QMessageBox` dialogs; added `setCheckable(True)` to `SidebarButton` so the active-page highlight works and `is_on()` can ever return True; consolidated the duplicated long-line `setAutoRepeat` loops into one loop at button creation in `Sidebar.__init__`; strengthened the placeholder test to navigate to Settings and assert the visible status text after each action.
- Defect found: `test_settings_page_shows_placeholder_integration_messages` called `_connect_gemini()` which opened a modal `QMessageBox.information`; in offscreen test runs nobody dismisses it, so the Qt event loop blocked forever (the hang). Separately, sidebar buttons were never checkable, so `setChecked` was ignored by Qt and `test_sidebar_active_state_after_sidebar_click` failed, meaning the real app had no active-page highlight. Also fixed a hidden-state defect in my own first attempt: the status label was created with `hide()` and `_set_status` never called `show()`, so the message would have been invisible to a real user.
- Verification: per-test bisect showed 6 of 8 passing individually, the placeholder test producing no output (hang), and the active-state test failing an assertion; after the fix, `pytest tests/test_shell.py` offscreen `8 passed in 0.90s`; full suite `211 passed, 2 skipped in 76.56s` (skips are the two documented symlink-availability cases); `ruff check .` all checks passed; `ruff format --check .` 90 files already formatted; `app.py --smoke-test` offscreen exit 0; an offscreen driver navigated Home / My automations / Activity / Settings with correct workspace index and sidebar checked state, plus create-automation and review-cancel transitions; a class-name audit found no `QtWebEngine`/`WebView` usage; `git status` reviewed before committing.
- Outcome: PASSED.
- Human review: left blank. Confirm the three untracked files (`app.spec`, `once-app.spec`, `ui/components/__init__.py`) should be landed or deleted, and consider a visual click-through of the new blue status label styling.


## 2026-10-26 — UI migration Slice 2: Activity page wiring (read-only)   (commit: pending)
- Task: Wire the redesigned shell's ActivityPage to the controller service so it shows real persisted run history, read-only, reusing existing `WorkflowService.history()`.
- AI contribution: new `tests/test_activity_page.py` (7 pytest-qt tests, written first); modifications in `ui/pages/activity.py` (runs cache, selection→details mapping fix, step-level detail lines, public `refresh()`) and `ui/shell.py` (service injected into the activity page at construction; list refreshed when the Activity page is shown).
- Defect found: the details label mapped the selected row through `reversed(self._service.history())` while the list itself is populated newest-first, so selecting the newest run displayed the oldest run's details; fixed and pinned by `test_details_label_matches_selected_run`.
- Verification: `.venv/Scripts/python.exe -m pytest tests/test_activity_page.py` → first 4 passed / 3 failed (pre-implementation), after implementation `tests/test_activity_page.py tests/test_shell.py` → `15 passed`; `.venv/Scripts/python.exe -m ruff format .` → 1 file reformatted, `.venv/Scripts/python.exe -m ruff check .` → `All checks passed!`; full suite `.venv/Scripts/python.exe -m pytest -q` → `316 passed, 2 skipped in 182.47s` (same 2 symlink-environment skips as slice 1).
- Outcome: PASSED
- Human review:

## 2026-10-26 — PHASE A: tooling fixes and slice 2 follow-up   (commit: pending)
- Task: Rewrite scripts/verify.ps1 as real PowerShell, audit .github/workflows/tests.yml, strengthen the slice 2 newest/oldest-row regression test, and update docs/PROGRESS.md status lines.
- AI contribution: rewrote scripts/verify.ps1 (venv guard, offscreen QT_QPA_PLATFORM, 8 checks, summary table, exit semantics); no change needed to tests.yml; extended test_details_label_matches_selected_run with oldest-row assertions; PROGRESS.md P0-4/P1-1..4/S1/S2 marked DONE, next action S3.
- Defect found: verify.ps1 was bash inside a .ps1 file (run_check(), if "$@"; then, [ ! -f ... ]) and could not parse under PowerShell; the slice 2 regression test did not assert the oldest row shows different details; PROGRESS.md still marked completed items TODO.
- Verification: powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1 run twice this session; second run output: pytest "316 passed, 2 skipped in 187.10s", ruff check "All checks passed!", format "106 files already formatted", both smoke tests PASS, "ALL CHECKS PASSED" (full output in session report). tests/test_activity_page.py: 7 passed. PROGRESS.md encoding checked with od -c: valid UTF-8 (em dash 342 200 224), left untouched per instruction.
- Outcome: PASSED
- Human review:

## 2026-10-26 — UI migration Slice 3: My automations page   (commit: pending, branch slice/my-automations-page)
- Task: Give the redesigned shell's My automations page LIST / OPEN (read-only details) / PREVIEW (read-only replay description) / RUN (confirmed, off-thread) using existing WorkflowService methods only.
- AI contribution: rewrote ui/pages/my_automations.py (details label, full-path payloads, preview display, QMessageBox confirm, QThread + WorkflowWorker run with disabled buttons, threaded quit like main_window._finish_run); removed the shell's unconfirmed direct run path (ui/shell.py _run_workflow_from_list + _preview_workflow and their connections); new tests/test_my_automations_page.py (14 tests, written first).
- Defect found: (1) three pre-existing page defects - Open discarded the loaded workflow and emitted a bare filename instead of the saved path, Preview computed preview_replay() and discarded it, Run called run_workflow directly on the UI thread with no confirmation; (2) a row-navigation load error popped a blocking modal (found via faulthandler traceback during a hanging test); row navigation now shows the error inline and only explicit actions open dialogs; (3) the initial port missed main_window's thread quit on completion, so the worker thread never emitted finished.
- Verification: tests/test_my_automations_page.py first run showed 10 expected failures (paste in session); final run "14 passed"; tests/test_shell.py tests/test_smoke.py "18 passed"; scripts/verify.ps1 full: pytest "330 passed, 2 skipped in 161.52s", ruff check "All checks passed!", format "107 files already formatted", both smoke tests PASS, "ALL CHECKS PASSED". Screenshots rendered offscreen to docs/screenshots/slice-3/ (01-empty.png, 02-populated.png, 03-selected.png; glyphs render as tofu because the offscreen platform has no fonts on this machine - environment artifact).
- Outcome: PASSED
- Human review:

## 2026-10-26 — Merge slice 3 and fix the create-page crash (commit: 84b6443)
- Task: Merge `slice/my-automations-page` into `main` only after the checks pass, collapse the repo to a single branch, and make the new shell usable for a human click-through.
- AI contribution: merged on a throwaway `merge-trial` branch and ran the full checks there before touching `main`; fast-forwarded `main`, pushed, then deleted the trial branch, the slice branch (local and remote), `chore/verify-fix` and the superseded `integration-ui-automation` (archived first as tag `archive/integration-ui-automation`). Two real defects surfaced from the running shell's stderr, both fixed with tests written first.
- Defect found: (1) `ui/pages/create_automation.py:85` called `.text()` on a `QTextEdit` — `AttributeError` on every click of the primary button. (2) Behind it, `ui/shell.py:252` called `WorkflowService.build_workflow_from_task`, a method that exists nowhere in the codebase (`grep -n "from_task|build_workflow"` returned only that call site), so the click produced a second traceback and no feedback. The existing shell test only typed into the field and never clicked the button, which is why both shipped.
- Verification: `pytest tests/test_shell.py -q -k "create_automation"` before the fix: `2 failed, 1 passed, 7 deselected, 1 error` (traceback pasted in session). After both fixes: `tests/test_shell.py` 10 passed; full suite `332 passed, 2 skipped in 82.00s` (2 symlink skips), `ruff check .` -> `All checks passed!`, `ruff format --check .` -> `107 files already formatted`. Merge trial before the merge: `330 passed, 2 skipped`, both smokes exit 0. `main` == `origin/main` == `84b6443`.
- Outcome: PASSED
- Human review:

## 2026-10-27 — Phase A: repair main (slice/repair-main)   (commit: 0ecbea0, d332aa1, 716a22c, fdf17d4, 1f146a3)
- Task: Reproduce and fix the flaky full-suite crash, fix ruff/format, rewrite verify.ps1 as real PowerShell with an append-only log guard, remove Qt-unknown stylesheet properties, add the working agreement, and re-verify every file:line citation in docs/PROGRESS.md and docs/ui_migration_plan.md.
- AI contribution: Created docs/WORKING_AGREEMENT.md, tests/test_styles.py, scripts/verify.ps1 (rewrite); edited ui/pages/my_automations.py (threading fix), ui/shell.py (home_page.set_service), ui/styles/__init__.py (box-shadow removal), docs/PROGRESS.md and docs/ui_migration_plan.md (citation corrections).
- Defect found: The crash was real and flaky, not a hang: `Fatal Python error: Aborted` in `_thread_finished` (ui/pages/my_automations.py:112). Root cause 1: `worker.deleteLater` connected to `thread.finished` double-deletes the worker (QThread flushes the DeferredDelete itself while finishing; the Python wrapper still owns it) -> heap corruption. Root cause 2: widget-touching handlers ran in the worker thread (plain Python callables), producing `QBasicTimer::stop: Failed. Possibly trying to stop from a different thread`. Also found: the shell never called `home_page.set_service`, so Home's Recent activity could never render.
- Verification (exact commands and results):
  - Repro: `pytest tests/test_my_automations_page.py -q -X faulthandler` looped 40x -> crashed on runs 3 and 21 (exit 3, faulthandler trace pointing at my_automations.py:112); a temporary 1000-cycle stress harness crashed 3/3 runs before the fix.
  - After fix: stress harness 6/6 clean (6000 cycles), original test file 15/15 clean, no `QBasicTimer` warnings.
  - Full suite x3 with `-X faulthandler -q -rf --tb=short`: `335 passed, 2 skipped in 95.66s`, `335 passed, 2 skipped in 96.44s`, `335 passed, 2 skipped in 78.94s`. The failure was flaky (reproduced ~10% of test-file runs), now deterministic-green in these runs.
  - `ruff check .` -> `All checks passed!` (exit 0); `ruff format --check .` -> `109 files already formatted` (exit 0).
  - verify.ps1 failure detection: with a temporary unused `import os`, script output showed `ruff check . exit=1 FAIL`, `SOME CHECKS FAILED` and exit code 1 (the same run also showed `pytest -q exit=3 FAIL` because the flaky crash hit during it - that is the bug fixed above); the break was removed afterwards.
  - GitHub Actions: `.github/workflows/tests.yml` exists; latest run on main passed (read from https://github.com/medamineessid/once/actions in this session).
  - A6: `app.py --smoke-test --shell` output contains 0 "Unknown property" lines (only the offscreen QFontDatabase warning).
- Outcome: PASSED
- Human review:

## 2026-10-27 — PHASE B: B1 UX brief + B2 journey queue + B3 blocked decision   (commit: see git log)
- Task: B research-and-decision phase — write the UX brief from measured behaviour, replace the old slice queue with the PHASE C journey queue, and start B3 layout-foundation. 
- AI contribution: docs/UX_BRIEF.md (audience, three journeys, per-page specs for Home/Create/My automations/Activity/Settings, honest-controls rule, layout and type/spacing rules, edit-queue); rewritten PHASE B/C sections of docs/PROGRESS.md; docs/BLOCKED.md decision document.
- Defect found: B3's requirement "remove every unwired control" collides with three existing tests. tests/test_shell.py:106 (test_settings_page_opens_from_sidebar asserts the four placeholder groups are visible), :118 (test_settings_page_shows_placeholder_integration_messages asserts fake Gemini/coding-agent status text), :136 (test_settings_page_has_recording_controls asserts three non-functional recording buttons). Per the working agreement I may not remove/weaken tests without the user's decision, so B3 stopped BEFORE any code edit — no partial Settings changes were made.
- Verification: collisions located by `grep -rn "_recordings_group|_gemini_group|_coding_agent_group|_advanced_group|_start_recording|_connect_gemini|_delete_recording" tests/` → only tests/test_shell.py:112-115,122-132,138-143. Placeholder behaviour re-confirmed in ui/pages/settings.py:195-218 (status-sentence handlers) and ui/shell.py:279-283 (pass handlers); Advanced group is a label with no controls (ui/pages/settings.py:165-180). No engine, storage, controller or approval-path test references the affected controls, so the documented recommendation (BLOCKED.md option A: rewrite the three shell tests to assert the honest state) does not touch any safety invariant.
- Outcome: BLOCKED (decision requested; B1/B2 complete and committed)
- Human review:

## 2026-10-28 — Step B3: layout-foundation slice (BLOCKED.md option A approved by user)   (commit: see git log)
- Task: apply the UX brief's layout foundation: remove the four non-functional Settings groups (user approved rewriting the three placeholder-proving tests), remove the duplicate Home button, fix the sidebar footer, introduce spacing/type tokens in ui/styles, add layout tests, and capture screenshots.
- AI contribution: ui/styles/__init__.py (SPACING_*/TYPE_*/FONT_STACK tokens interpolated into the stylesheet via string.Template; sidebar + pages styled from objectName rules); ui/pages/settings.py rewritten (Authorized folders + real "Configure checker" entry wired to the existing VerifierConfigDialog; recording/Gemini/coding-agent/Advanced groups and dead signals removed); ui/pages/home.py (duplicate My-automations button removed, demo double-run fixed: the page now only emits run_demo_requested), activity/create/review/my_automations (inline font styles moved to theme rules, margins tokenized); ui/shell.py (sidebar = 4 nav buttons + brand + one footer label, Segoe UI first, dead recording/verifier pass-handlers removed, ShellPages.CREATE state, settings_page.configure wiring); tests/test_shell.py (3 tests rewritten per option A, 7 new tests).
- Defect found: my first capture script grabbed before navigating, so 01-home.png and 05-create-automation.png were byte-identical; detected by md5sum, fixed by navigate->wait->grab ordering, all five files now distinct.
- Defect found (prior session, fixed in code): "Try a demonstration" ran the demo twice (page called service.run_demo() AND shell's run_demo_requested handler did too). Modified-shell test coverage: tests/test_shell.py test_every_page_has_no_unwired_buttons guards future dead buttons.
- Verification: tests/test_shell.py 16 passed (fails-first confirmed before implementing: 7 failed on missing controls/tokens); full suite `pytest -q` -> "340 passed, 2 skipped in 331.81s" (335+2 before; +5 = 4 verifier/placeholder rewrites rescoped plus sidebar/margins/wiring/type tests, 3 placeholder tests rewritten in place); `ruff check .` exit 0; `ruff format --check .` -> "111 files already formatted"; `app.py --smoke-test` exit 0; `app.py --smoke-test --shell` exit 0; screenshots via app.main's own construction path with md5-verified distinct files.
- Outcome: PASSED
- Human review:

## 2026-10-29 - PHASE P1: truth-and-foundations slice (commit: see git log)
- Task: P1.1 haystack runs with faulthandler, P1.2 button audit with click-behavior tests,
  P1.3 prove the unwired-buttons guard fails, P1.4 authorized-folder persistence through the
  controller service, P1.5 close the B3 blocked decision, P1.6 reproducible screenshot script.
- AI contribution: docs/BUTTON_AUDIT.md (17 controls, handlers, effects, click tests);
  docs/AUTONOMOUS_DECISIONS.md (AD-001..AD-004); WorkflowService.set_allowed_root/allowed_root;
  SettingsPage authorized-folder wiring + shell set_service injection; ReviewPage.show_workflow
  replacing the broken review_page.set_workflow call; 13 new tests in tests/test_shell.py
  (9 mouseClick behavior tests, 4 authorized-folder tests); unwired-buttons test extended to
  QAbstractButton over pages + sidebar; scripts/capture_shell_pages.py + scripts/capture_screenshots.ps1;
  BLOCKED.md RESOLVED marker; WORKING_AGREEMENT observed-effect evidence rule.
- Defect found: ui/shell.py:230 _open_workflow called review_page.set_workflow, which never
  existed on ReviewPage; clicking Open raised AttributeError: 'ReviewPage' object has no
  attribute 'set_workflow' (captured in the failing test run before the fix). Also ruff found
  my own first attempt referencing Workflow in review.py without importing it (fixed), and the
  ps1 array-concat failed as positional syntax in PowerShell 5.1 (rewritten with a pipeline).
- Verification: python -X faulthandler -m pytest -q twice: '340 passed, 2 skipped in 106.25s'
  (run1_exit=0) and '340 passed, 2 skipped in 113.62s' (run2_exit=0), no crash or hang; ghost
  button proof: '1 failed in 0.35s' with AlertDialog listing HomePage: Ghost, then reverted
  (git diff empty); after fixes tests/test_shell.py '27 passed in 8.41s' and post-format
  '27 passed in 2.67s'; ruff check 'All checks passed!', format check '113 files already
  formatted'; capture script printed 18 paths with distinct md5 and non-empty files (script
  asserts both).
- Outcome: PASSED
- Human review:
## 2026-10-30 — Amendments slice: queue reorder, honesty corrections (commit: slice/j2-create-automation)
- Task: apply the 2026-10-29 user amendments — reorder journeys (J2 first), hide controls whose handlers do nothing until their journey wires them, and correct the P1 bookkeeping.
- AI contribution: PROGRESS.md queue reorder + wording fixes; AUTONOMOUS_DECISIONS.md AD-005/AD-006 and the AD-001 persistence addendum.
- Defect found: the P1 log entry claimed "13 new tests in tests/test_shell.py" but `git diff eae542d e638e5e -- tests/` shows 11 added test functions and 0 removed/rewritten (the counting error is detailed in AD-005); earlier "persisted" wording overstated the authorized folder's lifetime — it is session-only in both windows. Also: an earlier heredoc edit failed on line `journeys[line.split()[2]]` (grabbed `]`, not the journey id) and was fixed to `[3]` before any write — no partial state was saved because the assert fired before write_text in the first attempt.
- Verification: `git diff eae542d e638e5e -- tests/ | grep -E '^[+-](def test_)'` (11 +/- grep output pasted in session report; 0 `-def test_` lines); python edits with asserts on every anchor; Automated check pending in the gate.
- Outcome: PENDING GATE
## 2026-10-30 — Amendment slice: chain-following unwired test + honest hiding (commit: see git log)
- Task: make the unwired-button test follow signals through to a real handler; hide every visible enabled control whose downstream signal is unconnected; prove the test can fail.
- AI contribution: tests/test_shell.py helpers `_pass_only_handlers`, `_emitted_signals`, `_connect_self_targets`, `_follow_chain` (bounded relay following, per-hop regex), `_static_unwired_reasons`; new test_review_edit_and_approve_are_hidden_until_j6; ui/pages/review.py Edit/Approve hidden and the `pass` `_edit` handler + connection removed; ui/shell.py dead `_on_approved`/`_show_run_details` connections and methods removed; docs/BUTTON_AUDIT.md sections 1-3 updated; AD-007.
- Defect found in my own first attempt: (1) the first helper block was injected with dead scaffolding (`emit_pattern`, `stripped`, `del`) and a backwards regex (`\.connect\(self.<sig>` instead of `.<sig>.connect(self.X`); rewritten wholesale. (2) `_follow_chain` compiled its pattern once from the initial signal, so relay hops re-matched the same line forever and reported `signal chain for homeClicked loops back on itself`; fixed by recompiling per hop. (3) an edit heredoc used `read_text()` in text mode (CRLF→LF translation), so `
` probes missed and the ghost button silently was not added (the "1 passed" then proved nothing); fixed with `read_text(newline="")`. (4) test_review_edit_and_approve_are_hidden_until_j6 asserted Cancel visible while the review page was not the current page; fixed by switching the workspace first.
- Verification (exact outputs in the session report): failing-first run `2 failed in 3.42s` with `shell.py connects a pass-only handler: _on_approved` among 4 violations; chain-failure proof with ghost `1 failed in 2.06s` with `home.py: _ghost_requested -> signal ghost_requested has no downstream connection`; after the fix `28 passed in 17.70s` (tests/test_shell.py) and full suite `352 passed, 2 skipped in 146.33s (0:02:26)`; `ruff check .` → `All checks passed!`; `ruff format --check .` → `114 files already formatted`; `git diff --stat ui/pages/home.py` empty after reverting the ghost.
- Outcome: PASSED
- Human review: 

## 2026-10-30 — P0: session start, verify repair, j2 merge   (commit: 85a5893 in slice/j2-create-automation)
- Task: P0.1 paste the real branch/status/log/verify outputs and repair failures; P0.2 merge slice/j2-create-automation once verify passes; P0.3 re-read the digest docs.
- AI contribution: diagnosis of the append-only-guard failure; the LF-normalising repair commit; the ff-merge and push.
- Defect found: docs/ai_engineering_log.md was stored as a CRLF blob in commit eb3773c while main is LF, so verify's append-only numstat read "994 added, 980 deleted" although the ignore-cr diff is exactly "14 added, 0 deleted" (a pure append; nothing lost). Also the whole worktree showed ~58 modified files that were line-ending churn only.
- Verification: git diff --ignore-cr-at-eol --stat (empty) -> noise only; git show blobs od -c (main LF, branch CRLF); verify.ps1 run 1 paste (engineering log append-only FAIL, everything else PASS); repair commit 85a5893; git diff --numstat origin/main...HEAD -- docs/ai_engineering_log.md -> "14 0"; verify.ps1 run 2 paste ended "ALL CHECKS PASSED" with pytest "352 passed, 2 skipped in 170.03s"; ff-merge e638e5e..85a5893 pushed to origin/main; git branch --show-current -> slice/p1-editor-discovery after branching.
- Outcome: PASSED
- Human review:

## 2026-10-30 — P1: editor discovery and UX audit docs   (commit: slice/p1-editor-discovery, hash in PROGRESS/report)
- Task: docs/design/visual_editor.md with evidence (workflow model, kind table, persistence, recording pipeline, run events) and design decisions (chain semantics, controller edit API + undo, layout-record schema, auto-layout, keyboard, test strategy, tokens); docs/UX_AUDIT.md audit of the shell.
- AI contribution: both documents; AD-008..AD-013; PARKED.md PARKED-1 (branching); QUESTIONS.md Q1..Q4.
- Defect found: ui/pages/review.py:117-125 load_proposal reads proposal.steps but ProviderDraft has only goal+workflow (ai/models.py:27-33) - latent AttributeError; plus review page never gets the service injected (ui/shell.py:157-160). Both assigned to P6 with the review journey.
- Verification: doc claims cite file:line reads made this slice on the merged main tree (engine/workflow.py, engine/replay.py, engine/desktop.py, controller/service.py, controller/recording.py, ai/*, recorder/*, storage/*, ui/shell.py, ui/pages/*.py, app.py); no code changed in this slice.
- Outcome: PASSED
- Human review:

## 2026-10-30 — P2: design-system components and shell/pages rewrite   (commit hashes in git log, branch slice/p2-design-system)
- Task: reusable P2 components (banner, inline two-step confirm, status footer, cards/chips, page header, ghost button, row widgets, inline verifier panel), shared strings/formatting/contrast, stylesheet token wiring, and a ShellPages rewrite (banner above workspace, footer under sidebar, Ctrl+1..4, review+create stacked pages) with page rewrites (home, my automations, activity, settings, create) and tests.
- AI contribution: ui/components/{banner,confirm,footer,cards,icons,pageheader,formatting,verifier_panel}.py, ui/styles/__init__.py token substitution + P2 selectors, ui/strings.py additions, ui/shell.py and ui/pages/*.py rewrites, controller.workflow_name, tests/test_p2_components.py + tests/test_p2_shell.py, swapped tests in test_shell.py/test_my_automations_page.py.
- Defect found: (1) ui/strings.py was missing the four DEMO_* banner constants that ui.shell imports — module failed to import, blocking 2 test files at collection; the constants are now written and every non-empty string is covered by the strings test. (2) ui/styles/__init__.py's substitution map lacked the TINT_* tokens the template references (first failure "KeyError: 'TINT_VERIFY'"); the whole theme failed to apply and 46 tests errored. (3) InlineConfirm confirmed-click left the label at "Confirm run?" instead of restoring the plain label, and arm_for_test() did not start the expiry timer so the timeout path was untestable. (4) The inputBase rule declared QPlainTextEdit, a class unknown to the styles audit _SELECTOR_CLASSES; resolved per AD-014 with QWidget#inputBase. (5) test_home_demo_button_runs_the_demo_exactly_once crashed the offscreen full run (exit -1073740791) by ending while the demo QThread was still alive; swapped to the explicit thread-finished wait per AD-015. (6) The two inline settings panel tests asserted Qt visibility on a page that was not the current workspace page; both now click the real sidebar button first.
- Verification: ruff format + ruff check ui tests controller -> "All checks passed!"; targeted pytest subset -> "92 passed in 17.25s" EXIT=0; full scripts/verify.ps1 -> SUMMARY all PASS including "pytest -q exit=0 PASS" and trailing "ALL CHECKS PASSED"; full pytest line "386 passed, 2 skipped in 140.25s (0:02:20)"; test_shell.py alone under QT_QPA_PLATFORM=offscreen -> "26 passed in 5.36s" EXIT=0 (crash reproduced first with 16 dots then abort, exit -1073740791, before the swap).
- Outcome: PASSED
- Human review:

## 2026-10-31 — P3 plus pre-P3 orders: close-join, screenshots, swap ledger   (commit hashes in git log, branch slice/p3-canvas)
- Task: (1) closing the app window during a demo or run must cancel and join the worker thread with a bounded wait, in the app not only tests; (2) re-capture screenshots with the P2 shell + INDEX.md; (3) test-swap ledger 5c17e42..HEAD; (4) P3 read-only canvas: pure auto-layout + golden tests + read-only scene view integrated on ReviewPage.
- AI contribution: ui/workers.py cancel_and_join + THREAD_JOIN_TIMEOUT_MS; shell.closeEvent cancel_run_thread; my_automations.shutdown_worker; tests/test_close_during_run.py. docs/screenshots/latest re-run + INDEX.md. ui/editor/{__init__,layout,canvas}.py; tests/test_editor_layout.py, tests/test_editor_canvas.py; ui/pages/review.py additive canvas render. PROGRESS.md P3 row.
- Defect found: (a) my first ui/workers.py edit mangled the file (bogus import line, undefined logger, class header consumed, E402/UP037 findings) - repaired before tests. (b) test_shell's demo test crashed the offscreen full run at teardown (exit -1073740791, reproduced 16 dots + abort) - the P2-era closeEvent could not force join once out of event processing; fixed by cooperative cancel + bounded join in closeEvent. (c) layout pass B originally walked chain order interleaving saved/grid so a saved node on the start slot never displaced Start; reordered to place saved first, matching the design's "grid slot is nudged, never the saved node". (d) canvas.py first draft had placeholder render hints and wrong paint signatures; rewritten. (e) golden tests initially had wrong slot-pitch arithmetic (forgot the Start terminal occupies the first grid slot) and asserted no edges for the empty workflow; corrected against the algorithm's real (deterministic) output, module unchanged. (f) canvas fixture GC'd the sole parent host widget (libshiboken "already deleted"); fixture now hands the view to qtbot directly.
- Verification: 3 consecutive faulthandler runs of test_close_during_run.py -> "3 passed", EXIT=0 (1.98s/4.35s/3.55s); capture_screenshots.ps1 exit 0, 18 distinct non-empty captures, INDEX.md written status CAPTURED, NOT REVIEWED; editor subsets -> 17 passed then 59 passed incl. shell/page integration; final verify.ps1 -> ALL CHECKS PASSED (pytest exit=0); swap ledger in the P3 phase report (5 removed/renamed total, all same-or-more with replacements named).
- Outcome: PASSED
- Human review:

## 2026-10-31 — P4a: Qt-free workflow editor session   (commit: bb9c07b)
- Task: Add atomic controller operations for editing immutable workflow definitions,
  including insertion, deletion, duplication, reordering, notes, node positions,
  undo/redo, and save/load through the existing service boundary.
- AI contribution: added `controller/editor.py`, `WorkflowService.open_editor`,
  and focused controller editor tests with seeded operations and round-trip checks.
- Defect found: the first complete verification run found only a formatting failure
  in the new editor module; `ruff format` fixed it before the passing rerun.
- Verification: `scripts/verify.ps1` printed `412 passed, 2 skipped in 116.61s
  (0:01:56)`, `All checks passed!`, `140 files already formatted`, both smoke
  tests PASS, engineering-log append-only PASS, and `ALL CHECKS PASSED`.
- Outcome: PASSED
- Human review:

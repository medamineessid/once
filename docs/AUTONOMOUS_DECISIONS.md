# Autonomous decisions (session-prompt protocol)

Format per item: id, date, question, options, choice, reason.

## AD-001 — 2026-10-29 — Where should the authorized folder live?

- Question: P1.4 requires the chosen authorized folder to "persist through the
  controller service". The old window kept it in a window attribute
  (`_authorized_root`, ui/main_window.py); the shell has several pages that now
  need the same value.
- Options: (a) store it in the shell window like the old window; (b) store it on
  `WorkflowService` (controller); (c) persist it to disk in the app data dir.
- Choice: (b) `WorkflowService.set_allowed_root()` / `WorkflowService.allowed_root`
  (controller/service.py), session scope.
- Reason: the prompt says "persists through the controller service"; pages are
  wired `ui -> controller`, so one service attribute reaches every page. Options
  (a) is the old-window state the migration is leaving; (c) exceeds parity — the
  old window kept the root in memory only, and persistence semantics overlap with
  the verifier configuration storage, which has its own tested path. The name
  `allowed_root` matches the parameter every engine entry point already takes
  (controller/service.py run_workflow/run_replay/run_desktop_approved).
- Addendum 2026-10-29: the authorized folder is SESSION-ONLY in both windows —
  it is not persisted across app restarts anywhere. The old window kept
  `_authorized_root` in memory (ui/main_window.py:62, assigned at 263); the shell
  keeps it as a `WorkflowService` attribute (controller/service.py:91,108-110).
  Earlier ledger wording "authorized-folder persisted through WorkflowService" meant
  "kept in the service for the session," not saved to disk; the ledger wording was corrected accordingly.

## AD-002 — 2026-10-29 — The shell's Open button called a nonexistent method

- Question: `ui/shell.py:230 _open_workflow` calls
  `self.review_page.set_workflow(workflow)`, but `ReviewPage` has no
  `set_workflow`; clicking Open raises
  `AttributeError: 'ReviewPage' object has no attribute 'set_workflow'` inside
  the Qt slot. P1.2 says every audited control is implemented or hidden.
- Options: (a) hide the Open button; (b) rename the call to a new read-only
  `ReviewPage.show_workflow`; (c) route Open through the proposal
  (`load_proposal`) by wrapping the workflow in a `ProviderDraft`.
- Choice: (b), implemented in this slice.
- Reason: smallest real fix with old-window parity — the old window showed an
  opened workflow as read-only steps. (a) would remove a working capability the
  old window has; (c) would show a saved workflow as if it were an untrusted AI
  proposal, misleading the review surface. Approve/Edit remain inert and are
  assigned to J6 in docs/BUTTON_AUDIT.md section 3.

## AD-003 — 2026-10-29 — Screenshot page list and file naming

- Question: P1.6 says "every page"; the shell has four sidebar pages plus two
  stacked pages (create flow, review). Which set, and what naming?
- Options: (a) capture only the four sidebar pages; (b) six pages
  (home, my-automations, activity, settings, create-automation, review) × 3 sizes
  as `<width>x<height>-<page>.png` in docs/screenshots/latest/.
- Choice: (b), 18 files.
- Reason: the create flow and review page are reachable shell pages (Review is
  opened with a real saved demo workflow so the screenshot shows real content);
  stable names let future slices diff against the same paths.

## AD-004 — 2026-10-29 — Cancel of the folder dialog

- The dialog-cancel test (test_settings_authorized_folder_cancel_keeps_previous_value)
  asserts the label and stored value are unchanged — old-window parity (the old
  window only assigned the root on a non-empty dialog result, ui/main_window.py
  `_choose_authorized_root`). Recorded because "cancel changes nothing" is a
  semantic the brief does not spell out.

## AD-005 — 2026-10-29 — Test arithmetic between eae542d and e638e5e

- Question: the suite went from 340 passed to 351 passed (+11) while the log
  entry for the P1 slice claimed "13 new tests in tests/test_shell.py". Which
  is right, and did any test get removed or rewritten?
- Evidence: `git diff eae542d e638e5e -- tests/` shows exactly 11 added
  `def test_` lines and 0 removed ones; tests/test_my_automations_page.py
  gained no test functions (10 inserted lines only, the FakeService edits).
  The 340 -> 351 delta is exactly the 11 new test functions.
- Answer: 11 new tests in tests/test_shell.py, 0 tests removed, 0 rewritten
  (function signatures were never touched after eae542d; only bodies and lines
  inside them changed). The "13" figure in the P1 log entry and the ledger was
  wrong; corrected here and in the log append (the log is append-only).
  List of the 11 added tests: test_settings_authorized_folder_persists_through_service,
  test_settings_authorized_folder_cancel_keeps_previous_value,
  test_settings_displays_a_previously_chosen_folder,
  test_shell_injects_the_service_into_the_settings_page,
  test_sidebar_click_settings_switches_and_checks,
  test_sidebar_click_home_returns_to_home,
  test_home_create_button_clicks_into_create_flow,
  test_home_demo_button_runs_the_demo_exactly_once,
  test_open_button_click_shows_opened_workflow_on_the_review_page,
  test_review_cancel_button_click_returns_home,
  test_activity_run_click_shows_its_steps.

## AD-006 — 2026-10-29 — Does set_allowed_root validate like the old flow?

- Question: does `WorkflowService.set_allowed_root` check as much as the old
  window's authorized-root flow?
- Old flow: `ui/main_window.py:259-265` (`_choose_authorized_root`) opens
  QFileDialog.getExistingDirectory, returns early when the dialog result is
  empty, then stores `Path(directory)` in the in-memory attribute. No existence
  check, no directory check, no canonicalization.
- New flow: `ui/pages/settings.py` `_choose_authorized_folder` reads the same
  dialog, returns early on empty result, and stores via
  `controller/service.py:108-110` (`set_allowed_root`), which stores
  `Path(root)` when root is not None. No existence check, no directory check.
- Choice: no parity work needed — the two flows check exactly the same amount
  (dialog non-empty only). Recorded rather than silently assumed.
- Reason: the flows are equal, not weaker; adding existence checks here would
  be new validation behavior beyond parity, and approval/policy/validator
  semantics are frozen by the working agreement.

## AD-007 — 2026-10-29 — What "hide until the signal is wired" means

- Question: the amendment says to hide every visible enabled control whose
  downstream signal is unconnected until J3, and the unwired test must follow
  signals through to a handler. How far does that go?
- Choice: three concrete rules, applied in this slice:
  1. A connected `pass`-only handler is dead wiring: the connection and the
     handler are REMOVED (not hidden), because the page itself does the work
     (`activity_page.run_selected` → `_show_run_details`,
     `review_page.approved` → `_on_approved` in ui/shell.py).
  2. A visible enabled control with no observable click effect is HIDDEN
     (Review Edit and Approve until J6; Edit's `pass` handler was deleted
     with its connection).
  3. Controls whose click has a real page-local effect (My automations
     Preview and Run, Activity row selection — each asserted by an existing
     mouseClick test) stay VISIBLE; their extra page→shell signals are wired
     in their assigned journeys (J3, J4), where the test then follows them.
- Reason: (3) follows the working agreement's "observable effect" definition —
  the control is not inert, only its shell-level signal is pending — and the
  user's explicit J3 instruction ("wire run_requested and preview_requested
  through the controller") implies those buttons exist and are used until
  then. Hiding a working control and re-showing it one slice later would churn
  the UI for no honesty gain.
- Evidence: the strengthened `test_every_page_has_no_unwired_buttons` now fails
  on rule-2 cases (pasted in the log: 4 violations including
  `shell.py connects a pass-only handler: _on_approved`) and on chain breaks
  (pasted: `home.py: _ghost_requested -> signal ghost_requested has no
  downstream connection` from a temporary emit-only ghost button, reverted).
## AD-008 — 2026-10-29 — Missing spec files and reference image

- Question: the session prompt names `docs/specs/visual_workflow_editor.md` and
  `docs/specs/reference/workflow_editor.png` as strong guidance. Do they exist?
- Evidence: `ls docs/specs` shows only an empty `reference/` folder;
  `find docs/specs -type f` returns no files. Nothing to read.
- Options: (a) wait for the files to appear; (b) work from the prompt only.
- Choice: (b). Work from the prompt's MISSION/DESIGN LANGUAGE/ACCEPTANCE sections
  and record every place a judgement call deviates (this file and PARKED.md).
- Reason: the prompt says to do exactly that ("If the spec files are missing, work
  from this prompt and record that"). One known consequence: the DESIGN LANGUAGE
  tokens cannot be refined by sampling the reference image with QImage; they are
  taken from the prompt's textual description (single blue accent ≈ #2563EB, dark
  primary ≈ #111827, category tints, dot grid) and refined by tests (contrast),
  not by an image sample (refinement note in docs/design/visual_editor.md §2.6).

## AD-009 — 2026-10-29 — When the first-time acceptance test completes it fully

- Question: P2 must "add the first-time-user acceptance test" whose journey ends
  with `Create from scratch -> add a step -> save -> it appears in the list -> open
  -> run -> Activity shows the result`. That leg needs the visual editor (adding a
  step is an editor operation), which lands in P3/P4, while the shell redesign lands
  in P2.
- Options: (a) duplicate the create journey in P2 with a minimal non-canvas
  add-a-step form (the list-style page the prompt forbids); (b) deliver the
  acceptance test when its last leg exists (P4), with P2 covering the earlier legs
  (demo → Activity; list; open).
- Choice: (b), same test text as P2, executed through the real editor in P4.
- Reason: the prompt explicitly forbids building the list-style create page and
  defines the editor as the create surface; test-first sequencing is respected by
  writing the P4 test brief now. The P2 acceptance covers every leg that exists by
  then.

## AD-010 — 2026-10-29 — The editor graph is a linear chain

- Question: how does the canvas represent a workflow definition?
- Evidence: the engine iterates `enumerate(workflow.steps)` in tuple order and stops
  the remaining steps on failure or cancel (engine/workflow.py:832-869); steps are
  frozen dataclasses with no successor field (engine/workflow.py:70-90); no
  branching exists anywhere in the model (PARKED.md PARKED-1).
- Options: (a) free graph with draggable independent nodes and arbitrary wires;
  (b) a linear chain: Start → step[0] → … → step[n-1] → Finish, connections exactly
  as adjacent edges; (c) delayed until branching exists.
- Choice: (b). Connections represent execution order; insert-on-connection = tuple
  insertion at that index; delete/duplicate/move are tuple ops. Terminals are
  rendered, never persisted.
- Reason: the editor and the engine must share one executable definition (prompt
  pre-decision); (a) would imply semantics the engine cannot run; (c) loses the core
  editor. A later branching engine can extend (b) — nodes stay on a laid-out chain
  with explicit lanes at that point (PARKED-1).

## AD-011 — 2026-10-29 — Presentation metadata is not undoable-definition state

- Question: are "move node" and note edits part of the undoable editor command
  stack?
- Choice: no. Undo/redo reverse definition edits only (prompt pre-decision);
  node positions and notes are presentation metadata in the storage-layer layout
  record (new `workflow_layouts` table via the existing CREATE TABLE mechanism,
  storage/database.py:9-132 pattern). Moving a node rewrites the record directly.
- Reason: undo/redo would otherwise mix configuration state with cosmetics and make
  "Repeat undo until definition equals the saved one" ambiguous; the prompt's own
  ruler says notes/positions "never affects execution".

## AD-012 — 2026-10-29 — Node category tints and their boundaries

- Question: the prompt fixes tint families ("application and file interaction peach
  or orange; wait and verification pale green; decision lavender; start and manual
  review pale yellow; note soft yellow; finish light grey") but the engine has
  categories the list does not name (REPORT, FAIL) and no decision or manual-review
  steps exist.
- Choice: families in force (docs/design/visual_editor.md §2.6): mutating steps →
  peach; inspect/wait/verify → pale green; REPORT → pale-blue "progress"; FAIL →
  pale red "stop" (each state has icon + word, never color alone); Start → pale
  yellow; Finish → light grey; notes → soft yellow. The decision (lavender) and
  manual-review (pale yellow) families stay unused while branching is parked
  (PARKED-1) — they appear only if P7 lands.
- Reason: every of the 18 kinds must land in one family; FAIL as pale green would
  falsely suggest a benign step.

## AD-013 — 2026-10-29 — Blocking modals leave the shell

- Question: the pre-decided shell rule bans blocking modals, but several existing
  controls rely on them (audit C1: ui/shell.py:240-245, ui/pages/settings.py:125-137,
  ui/pages/my_automations.py:185-191,246,250, ui/pages/review.py:102) and their tests
  monkeypatch `QMessageBox` — the tests must change with the behavior.
- Choice: in the SHELL only, replace with non-modal banners and inline two-step
  confirm; the verifier configuration becomes an inline panel (no `QDialog.exec`)
  and the affected tests are replaced with tests asserting the same or more
  (banner text, config actually saved, signal emitted; the swap is logged in the
  slice commit). The old window (ui/main_window.py) keeps its dialogs and tests.
- Reason: the prompt's pre-decided errors rule overrides the current pattern;
  replacing rather than suppressing keeps evidence real (no handler behind a hidden
  modal). Swapped tests are enumerated in the P2 commit message.

## AD-014 — 2026-10-30 — Theme selectors stay inside the styles audit's widget map

- Question: the verifier panel styles its arguments field with
  `QPlainTextEdit#inputBase`, but `tests/test_styles.py`'s unknown-property audit
  is the anchor test and its `_SELECTOR_CLASSES` map does not list QPlainTextEdit
  (test_styles.py must stay green unmodified under the working agreement).
- Choice: declare the rule once as `QWidget#inputBase` (focus variant
  `QWidget#inputBase:focus`) in ui/styles/__init__.py. Qt type selectors match
  subclasses, so the same rule styles the panel's QLineEdit/QTextEdit/QPlainTextEdit
  inputs; no third class name is introduced into the template.
- Reason: widening the audit's map per-slice would let the stylesheet outgrow the
  one test that proves Qt actually parses every rule; keeping the map small forces
  objectName-based classes and one audited widget per name.

## AD-015 — 2026-10-30 — Demo-thread lifetime is part of the test contract

- Question: after a demo run test clicks the demo button, the run completes but
  the worker QThread may still be tearing down when the window fixture closes.
  Under the offscreen platform the process aborts (Windows exit -1073740791,
  0xC0000409) because Qt destroys a running QThread owned by the window.
- Choice: any test that starts a shell demo waits, before teardown, for both the
  footer to return to Ready and `window._demo_thread is None` (the waits the
  in-repo P2 demo tests already use); the test-side change is a same-or-more
  swap of `test_home_demo_button_runs_the_demo_exactly_once` and is logged in the
  P2 commit. Real users are covered by the shell's closeEvent quit+wait (2000 ms).
- Reason: policy/exit-code failures must never depend on thread scheduling; the
  deterministic wait makes the teardown crash structurally impossible instead of
  timing-luck.

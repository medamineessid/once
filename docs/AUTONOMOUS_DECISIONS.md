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

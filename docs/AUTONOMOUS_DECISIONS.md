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

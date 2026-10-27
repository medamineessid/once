# UI Migration Plan (evidence-based)

Branch: `docs/ui-migration-plan` (created from `main` @ `cd2e77e`).  
Starting facts verified by commands:
- `git log --oneline -1`: `cd2e77e Merge redesign-ui: resolve conflicts in docs keeping both sides`  
- `app.py:1-138` imports `from ui.main_window import MainWindow` (app.py:21) and `from ui.shell import MainWindow as ShellMainWindow` (app.py:22); it chooses and constructs the window at app.py:78-86 (`window_cls = ShellMainWindow if use_shell else MainWindow`). The old window stays the default; `--shell` selects the new one.  
- `ui/main_window.py:46` defines `class MainWindow(QMainWindow)`. `ui/shell.py:138` defines its own separate `class MainWindow(QMainWindow)`; it is launched only with the `--shell` flag (app.py:78) and is exercised by `tests/test_shell.py` (150 lines).  
- `ui/pages/` contains `__init__.py`, `activity.py`, `create_automation.py`, `home.py`, `my_automations.py`, `review.py`, `settings.py` (verified via `ls`).  
- `ui/review_view.py`, `ui/verifier_dialog.py`, `ui/workers.py` exist at repo root under `ui/` (verified).  
- Untracked `app.spec` and `once-app.spec` were deleted in PHASE 1 (P1-1); `ls app.spec once-app.spec` now reports "No such file or directory". `once.spec` is tracked.  
- `tests/test_verifier_dialog.py` does **not** exist (verified: `ls tests/ | grep -i verifier` shows test_verifier.py, test_verifier_config.py, test_verifier_history.py only). `tests/test_review_ui.py` (440 lines) tests `ui.review_view.ProposalReviewPanel` and `ui.main_window.MainWindow` with agent proposals, and contains the verifier-dialog tests inline (test_review_ui.py:371-440).

**Re-verified 2026-10-27 (slice/repair-main, A5):** every file:line citation below was re-checked with `grep -n` against the current files and corrected where wrong. Line counts quoted at discovery time were stale for most files (they had drifted); the current numbers are used.

## 1) User-facing capabilities of ui/main_window.py mapped to pages

**ui/main_window.py** (608 lines) is a tabbed window: tabs "Workflows" and "Agent proposals" (ui/main_window.py:202-203, review panel created at 195). It holds service/recording_service/verifier_config/app_data_dir, maintains `_current_workflow`, `_authorized_root`, `_replay_preview`, `_draft_steps`, interview/proposal state, and runs work via `ui.workers.WorkflowWorker` (ui/main_window.py:317-347).

### Workflows tab capabilities (what user can do)
- **Run local demo**: button "Run local demo" (`_demo_button`, ui/main_window.py:81, connected at 114) calls `_run_demo()` → `_start_run(self._service.demo_workflow())` (ui/main_window.py:314-347). Status shown via `_status_label` (ui/main_window.py:64).
- **List saved workflows**: `_workflow_list` populated by `_refresh()` from `self._service.list_saved()` (ui/main_window.py:66,208-219). Selection loads via `_select_workflow()` → `self._service.load(Path(path))` (ui/main_window.py:221).
- **Preview replay**: "Preview selected replay" (`_run_button`, ui/main_window.py:73) calls `_preview_selected_replay()` → `self._service.preview_replay(self._current_workflow)` (ui/main_window.py:238,243), shows steps in `_result_list` (ui/main_window.py:68), sets status based on `executable`. Requires workflow selected.
- **Choose authorized folder**: "Choose authorized folder" (`_choose_root_button`, ui/main_window.py:75, connected at 112) calls `_choose_authorized_root()` (ui/main_window.py:259) which opens `QFileDialog.getExistingDirectory()`, stores in `_authorized_root`, enables execute if preview executable.
- **Execute approved replay**: "Execute approved replay" (`_execute_replay_button`, ui/main_window.py:77) calls `_execute_replay()` (ui/main_window.py:274) which confirms with `QMessageBox.question()`, calls `_start_run(..., replay=True, allowed_root=self._authorized_root)`.
- **Create workflow from form**: form fields `_workflow_name`, `_step_name`, `_step_message`, `_step_kind` (REPORT/FAIL, ui/main_window.py:101-104); draft list `_draft_list` (ui/main_window.py:69); buttons "Add step to draft" (`_add_step_button`, 90), "Move step up/down" (`_move_up_button` 91 / `_move_down_button` 92), "Remove step" (`_remove_step_button` 93), "Create workflow from form" (`_create_button`, 89). `_create_from_form()` builds `Workflow` from form+draft steps, calls `self._service.save(...)` (ui/main_window.py:293).
- **Open/Save workflow JSON**: "Open workflow JSON" (`_open_button`, ui/main_window.py:87, connected at 118) → `_open_workflow()` (ui/main_window.py:391); "Save current workflow" (`_save_button`, 88, connected at 119) → `_save_current()` (ui/main_window.py:406).
- **Cancel run**: "Cancel run" (`_cancel_button`, ui/main_window.py:82, connected at 115) → `_cancel_run()` (ui/main_window.py:347) calls `self._worker.cancel()` when running.
- **Record/Stop/Delete recordings**: "Record" (`_record_button`, ui/main_window.py:83, connected at 116) → `_start_recording()` (ui/main_window.py:570); "Stop recording" (`_stop_record_button`, 84, connected at 117) → `_stop_recording()` (ui/main_window.py:583); "Delete selected recording" (`_delete_recording_button`, 95, connected at 128) → `_delete_recording()` (ui/main_window.py:462). Uses `self._recording_service`.
- **View recordings and events**: `_recording_list` and `_recording_events` (ui/main_window.py:70-71), `_show_recording()` loads recording and displays events with redaction note for password elements (ui/main_window.py:423).
- **Analyze recording (offline)**: "Analyze selected recording (offline)" (`_analyze_button`, ui/main_window.py:94, connected at 127) → `_analyze_recording()` (ui/main_window.py:444) creates `InterviewSession(deterministic_demo_provider(), AnalysisRequest(build_raw_draft(recording)))`, shows interview state.
- **Interview Q&A and proposal approval**: `_question_label` (99), `_answer_input` (98), `_answer_button` "Submit answer" (96, connected at 129), `_proposal_goal` (100), `_proposal_list` (72), `_approve_button` "Approve and save proposal" (97, connected at 130). `_answer_interview()` (ui/main_window.py:476) feeds answer; `_show_interview_state()` (ui/main_window.py:487) shows preview via `preview_proposal()`, enables approve; `_approve_proposal()` (ui/main_window.py:501) calls `approve_proposal()` then `self._service.save_approved()`.
- **History and step results**: `_history_list` (ui/main_window.py:67) populated from `self._service.history()` by `_refresh()` (ui/main_window.py:208-219); `_result_list` (ui/main_window.py:68) shows step results via `_show_step_result()` (ui/main_window.py:384).

### Agent proposals tab
- Uses `ProposalReviewPanel` (imported at ui/main_window.py:39, created at 195, added as tab at 203). Panel provides proposal list, diff view, verification runs/evidence, verify/approve/apply/reject/configure actions (see section 3).

### Mapping to ui/pages/
- **ui/pages/home.py** (125 lines): "Create an automation" button emits `created_automation` (home.py:21, emitted at 96), "Try a demonstration" emits `run_demo_requested` (home.py:22, emitted at 99) and calls `self._service.run_demo()` if set (home.py:100-101), "My automations" emits `my_automations_requested` (home.py:23, emitted at 104). Recent activity reads `self._service.history()` in `_refresh_activity()` (home.py:106-122); `set_service()` is home.py:123-124. **Has matching widgets** for create/demo/my-automations and activity; **lacks**: full workflow form/draft editing, replay preview/execute with authorized folder, cancel, full recording UI, interview/proposal UI, history details in main window style.
- **ui/pages/my_automations.py** (270 lines): lists workflows via `self._service.list_saved()` (my_automations.py:258), "Open" emits `opened_workflow(Path(name))` (signal my_automations.py:30, `_open_selected()` 140-151), "Preview" loads and calls `self._service.preview_replay(workflow)` then emits `preview_requested()` (signal 32, `_preview_selected()` 153-175), "Run" loads and calls `self._service.run_workflow(workflow)` then emits `run_requested(Path(name))` (signal 33, `_run_selected()` 179-198). `set_service()` is my_automations.py:268. **Has matching widgets** (QListWidget + Open/Preview/Run). **Differs**: Preview/Run call the service directly without the old window's authorized-folder selection/confirmation flow; no replay preview list display in page.
- **ui/pages/create_automation.py** (94 lines): task entry; `task_entered` signal (create_automation.py:20) is emitted by `_create_from_description()` (84-87). The shell handler `MainWindow._handle_task_entered` (ui/shell.py:253-265) only acknowledges the text with a "Not available yet" message — **no builder exists in the controller**, so nothing is created (this replaced an earlier handler that called a nonexistent `build_workflow_from_task`). **Lacks**: full form editor (name/step kind/message/draft list/move/remove) that main_window provides.
- **ui/pages/activity.py** (102 lines): `ActivityPage` (activity.py:20) shows history; `run_selected` signal (activity.py:23, emitted at 69) is connected to `MainWindow._show_run_details`, which is still a stub (`pass`, ui/shell.py:273-274). `set_service()` is activity.py:100. **Lacks**: full history details with step results like main_window.
- **ui/pages/review.py** (111 lines): `ReviewPage` (review.py:24) with `approved` (27) / `cancelled` (28) signals; shell connects them to `_on_approved` (ui/shell.py:267) and `_on_review_cancelled` (ui/shell.py:270), both currently stubs. **Known gap**: `ReviewPage.set_service()` (review.py:110-111) is never called by the shell, so `_approve()` returns early at review.py:91 — the approve button cannot work yet. **Different from ProposalReviewPanel** — this is for workflow review, not agent proposal review.
- **ui/pages/settings.py** (232 lines): `SettingsPage` (settings.py:43) has verifier config UI and signals `verifier_configured`, `recording_started`, `recording_stopped` (settings.py:44-46, emitted at 220/223). **Known gap**: `SettingsPage.set_service()` (settings.py:231-232) is never called by the shell either. **Lacks**: full recording management UI (list recordings, view events, analyze, delete) that main_window has.

## 2) ui/shell.py MainWindow constructor vs app.py
- **ui/shell.py:141-149** `MainWindow.__init__(self, service: WorkflowService | None = None, recording_service: RecordingService | None = None, verifier_config: VerifierConfig | None = None, verifier_note: str | None = None, app_data_dir: Path | None = None) -> None` - same signature.
- **app.py:78-86** passes: `window_cls(service, recording_service, verifier_config=verifier_config, verifier_note=verifier_note, app_data_dir=app_data_dir)`. **Identical args/signature**. Shell MainWindow stores them as `self._service`, `self._recording_service`, `self._verifier_config`, `self._verifier_note`, `self._app_data_dir` (ui/shell.py:152-156) and injects them into pages via `set_service` at ui/shell.py:172-174 (home, activity, my automations). `review_page.set_service` (review.py:110) and `settings_page.set_service` (settings.py:231) are still **not called** — open defect tracked in docs/PROGRESS.md.

## 3) ui/review_view.py, ui/verifier_dialog.py, ui/workers.py
### ui/review_view.py (527 lines)
Provides `ProposalReviewPanel(QWidget)` (review_view.py:47-527). Lists proposals via `self._service.agent_proposals()` (review_view.py:153), shows diff/evidence/verification records, actions: verify (`VerifyProposalWorker`, review_view.py:363), approve+apply (`ApplyProposalWorker`), apply recorded approval (`ApplyRecordedApprovalWorker`), reject, configure checks via `VerifierConfigDialog` (`_configure_checks()`, review_view.py:317). Depends on `ui.workers`, `ui.verifier_dialog`, controller service methods. Used by **main_window "Agent proposals" tab** (ui/main_window.py:195,203). Long-running work off-thread via QThread workers.

### ui/verifier_dialog.py (123 lines)
Provides `VerifierConfigDialog(QDialog)`. Collects cases path, argv (one per line, must contain `{input}`), timeout, worktree root. Calls `save_verifier_config()` and returns saved config. Used by `ProposalReviewPanel._configure_checks()`. **No tests/test_verifier_dialog.py exists**; the dialog is covered inline in tests/test_review_ui.py:371-440.

### ui/workers.py (186 lines)
QThread workers: `WorkflowWorker` (workers.py:17) runs workflow/replay via service with cancel/progress; `VerifyProposalWorker` (workers.py:66) pre-merge verification; `ApplyProposalWorker` (workers.py:110) applies approved change; `ApplyRecordedApprovalWorker` (workers.py:131) applies recorded approval; `PostMergeVerifyWorker` (workers.py:152) post-merge verification. Used by **main_window** for running workflows (ui/main_window.py:317-347) and by **ProposalReviewPanel** for proposal operations (review_view.py:37-40,363+).

## 4) Tests covering old-window behavior
- **tests/test_smoke.py** (274 lines): tests `MainWindow` construction, controls, demo run, form creation, draft reordering/removal, recording/analyze/approve flow with fake recorder, app smoke test. Covers main_window workflows tab features.
- **tests/test_review_ui.py** (440 lines): tests `ProposalReviewPanel` and `MainWindow` agent proposals tab with real temp git repos and fake agent; verifier dialog tests inline at 371-440; QMessageBox.warning monkeypatched (e.g. test_review_ui.py:313).
- **tests/test_app_entry.py** (102 lines): tests app entry point, logging, startup failures, smoke test (including the `--shell` path).
- **tests/test_shell.py** (150 lines): tests `ui.shell.MainWindow` (navigation, pages, service wiring, run confirmation).
- **tests/test_workers.py** (64 lines): tests worker behavior.
- **tests/test_styles.py**: captures Qt's message handler while applying the theme and fails on any property Qt reports as unknown (added in PHASE A, A6).

## 5) Ordered slice list (lowest risk first)
Each slice keeps old window working and all tests green. `app.py` keeps `ui.main_window` as default until last slice. Add `--shell` flag for manual testing.

**Slice 1 (special): Add `--shell` flag to app.py**  
- Branch: `slice/shell-flag`  
- Add arg parsing for `--shell` (keep `--smoke-test`). If `--shell`, import and instantiate `ui.shell.MainWindow` with same args (service, recording_service, verifier_config, verifier_note, app_data_dir) as main_window gets; else use `ui.main_window.MainWindow` (default). Both windows must work with `--smoke-test`. Add tests in `tests/test_app_entry.py` or new test. Produce screenshots of all pages through real `app.py --shell` path into `docs/screenshots/slice-1/`. **CHECKPOINT 1** after merge/push - stop for user to test. — DONE (2a0573b; screenshots still missing, see docs/PROGRESS.md)

**Slice 2: Activity/history page wiring (read-only)**  
- Branch: `slice/activity-page`  
- Wire `ActivityPage` to `controller.service` for history display. Make it read-only, reuse existing service methods. Add pytest-qt tests. Screenshots. — DONE (588ed21)

**Slice 3: My automations page (list/open/preview/run)**  
- Branch: `slice/my-automations-page`  
- Pass service to `MyAutomationsPage` (has `set_service()`). Wire Open/Preview/Run to use service properly. Add tests. — DONE (70d8ce1)

**Slice 4: Create automation and draft editing**  
- Branch: `slice/create-automation`  
- Wire `CreateAutomationPage` fully; add draft step editing capabilities similar to main_window, or ensure task->workflow flow works. Add tests. — TODO (superseded by journey J2 in PHASE C of the session prompt)

**Slice 5: Recording lifecycle in shell**  
- Branch: `slice/recording-shell`  
- Wire recording UI in shell/SettingsPage to use `RecordingService` same as main_window (start/stop/list/events/analyze/delete). Add tests. — TODO (journey J5)

**Slice 6: Review/approval and verifier configuration**  
- Branch: `slice/review-approval-shell`  
- Wire `ReviewPage` and/or integrate `ProposalReviewPanel` functionality into shell; wire verifier configuration dialog. Reuse existing workers/panels. Add tests. — TODO (journey J6/J8)

**Slice 7: Desktop and browser steps in create_automation**  
- Branch: `slice/desktop-browser-steps`  
- Add support for creating/previewing desktop steps (LAUNCH_APPLICATION, WAIT_WINDOW, CLICK_UI_ELEMENT, TYPE_TEXT, PRESS_SHORTCUT, VERIFY_FILE_TEXT) and browser steps (LAUNCH_BROWSER, NAVIGATE_BROWSER, INSPECT_PAGE, FIND_PAGE_ELEMENT, INTERACT_PAGE_ELEMENT, WAIT_PAGE). Must reuse `engine.desktop.approve_desktop_workflow` and show mutating step kinds before approval enabled (use `mutating_kind_names`/`requires_desktop_approval`). Never create second approval path. Add tests. — TODO (journey J7)

**Slice 8 (final): Switch default to shell, retire/keep main_window per decision**  
- Branch: `slice/switch-default`  
- **CHECKPOINT 2** before changing default in app.py or retiring ui/main_window.py - stop and report. User decides. Do not make change without approval. — TODO (journey J9 checkpoint)

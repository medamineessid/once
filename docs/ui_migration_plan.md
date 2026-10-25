# UI Migration Plan (evidence-based)

Branch: `docs/ui-migration-plan` (created from `main` @ `cd2e77e`).  
Starting facts verified by commands:
- `git log --oneline -1`: `cd2e77e Merge redesign-ui: resolve conflicts in docs keeping both sides`  
- `app.py:1-133` imports `from ui.main_window import MainWindow` and launches it (app.py:20,120-127).  
- `ui/main_window.py:46` defines `class MainWindow(QMainWindow)`. `ui/shell.py:137` defines its own separate `class MainWindow(QMainWindow)`; app.py never imports/launches it (only `tests/test_shell.py` exercises it).  
- `ui/pages/` contains `__init__.py`, `__pycache__/`, `activity.py`, `create_automation.py`, `home.py`, `my_automations.py`, `review.py`, `settings.py` (verified via `ls`).  
- `ui/review_view.py`, `ui/verifier_dialog.py`, `ui/workers.py` exist at repo root under `ui/` (verified).  
- Untracked: `app.spec`, `once-app.spec` exist (verified). `once.spec` is tracked.  
- `tests/test_verifier_dialog.py` does **not** exist (searched). `tests/test_review_ui.py` exists and tests `ui.review_view.ProposalReviewPanel` and `ui.main_window.MainWindow` with agent proposals (tests/test_review_ui.py:1-523).  

## 1) User-facing capabilities of ui/main_window.py mapped to pages

**ui/main_window.py** (609 lines) is a tabbed window: tabs "Workflows" and "Agent proposals" (ui/main_window.py:314-330). It holds service/recording_service/verifier_config/app_data_dir, maintains `_current_workflow`, `_authorized_root`, `_replay_preview`, `_draft_steps`, interview/proposal state, and runs work via `ui.workers.WorkflowWorker` (ui/main_window.py:48-343).

### Workflows tab capabilities (what user can do)
- **Run local demo**: button "Run local demo" (`_demo_button`, ui/main_window.py:97,250-251) calls `_run_demo()` → `_start_run(self._service.demo_workflow())` (ui/main_window.py:400-401,473-492). Status shown via `_status_label` (ui/main_window.py:84,345-546).
- **List saved workflows**: `_workflow_list` populated by `_refresh()` from `self._service.list_saved()` (ui/main_window.py:86,345-354). Selection loads via `_select_workflow()` → `self._service.load(Path(path))` (ui/main_window.py:356-369).
- **Preview replay**: "Preview selected replay" (`_run_button`, ui/main_window.py:88,371-389) calls `self._service.preview_replay(self._current_workflow)`, shows steps in `_result_list`, sets status based on `executable`. Requires workflow selected.
- **Choose authorized folder**: "Choose authorized folder" (`_choose_root_button`, ui/main_window.py:90,391-404) opens `QFileDialog.getExistingDirectory()`, stores in `_authorized_root`, enables execute if preview executable.
- **Execute approved replay**: "Execute approved replay" (`_execute_replay_button`, ui/main_window.py:92-93,406-421) confirms with `QMessageBox.question()`, calls `_start_run(..., replay=True, allowed_root=self._authorized_root)`.
- **Create workflow from form**: form fields `_workflow_name`, `_step_name`, `_step_message`, `_step_kind` (REPORT/FAIL, ui/main_window.py:115-117,250-262); draft list `_draft_list` (ui/main_window.py:87,273-279); buttons "Add step to draft" (`_add_step_button`), "Move step up/down" (`_move_up_button`/`_move_down_button`), "Remove step" (`_remove_step_button`), "Create workflow from form" (`_create_button`) (ui/main_window.py:107-113,264-279,423-592). `_create_from_form()` builds `Workflow` from form+draft steps, calls `self._service.save(...)` (ui/main_window.py:423-442).
- **Open/Save workflow JSON**: "Open workflow JSON" (`_open_button`, ui/main_window.py:103,514-528) opens file dialog, loads via `self._service.load()`, saves via `self._service.save()`; "Save current workflow" (`_save_button`, ui/main_window.py:104,530-546).
- **Cancel run**: "Cancel run" (`_cancel_button`, ui/main_window.py:99,494-507) calls `self._worker.cancel()` when running.
- **Record/Stop/Delete recordings**: "Record" (`_record_button`, ui/main_window.py:100,624-633), "Stop recording" (`_stop_record_button`, ui/main_window.py:101,635-645), "Delete selected recording" (`_delete_recording_button`, ui/main_window.py:112,701-710). Uses `self._recording_service`.
- **View recordings and events**: `_recording_list` and `_recording_events` (ui/main_window.py:90-91,273-277), `_show_recording()` loads recording and displays events with redaction note for password elements (ui/main_window.py:666-683).
- **Analyze recording (offline)**: "Analyze selected recording (offline)" (`_analyze_button`, ui/main_window.py:111,685-699) creates `InterviewSession(deterministic_demo_provider(), AnalysisRequest(build_raw_draft(recording)))`, shows interview state.
- **Interview Q&A and proposal approval**: `_question_label`, `_answer_input`, `_answer_button` (ui/main_window.py:118-120,279-282), `_proposal_goal`, `_proposal_list`, `_approve_button` (ui/main_window.py:121-122,114,282-287). `_answer_interview()` feeds answer; `_show_interview_state()` shows preview via `preview_proposal()`, enables approve; `_approve_proposal()` calls `approve_proposal()` then `self._service.save_approved()` (ui/main_window.py:712-752).
- **History and step results**: `_history_list` populated from `self._service.history()` (ui/main_window.py:85,345-354,594-622), `_result_list` shows step results via `_show_step_result()` with evidence (ui/main_window.py:86,301-307,508-546,594-622).

### Agent proposals tab
- Uses `ProposalReviewPanel` (ui/main_window.py:27,325-330). Panel provides proposal list, diff view, verification runs/evidence, verify/approve/apply/reject/configure actions (see section 3).

### Mapping to ui/pages/
- **ui/pages/home.py** (173 lines): "Create an automation" button emits `created_automation` (home.py:112-135), "Try a demonstration" emits `run_demo_requested` and calls `self._service.run_demo()` if set (home.py:137-149), "My automations" emits `my_automations_requested` (home.py:151-152). Recent activity reads `self._service.history()` for SUCCEEDED runs (home.py:154-173). **Has matching widgets/placeholders** for create/demo/my-automations and activity; **lacks**: full workflow form/draft editing, replay preview/execute with authorized folder, cancel, full recording UI, interview/proposal UI, history details in main window style.
- **ui/pages/my_automations.py** (187 lines): lists workflows via `self._service.list_saved()` (my_automations.py:160-187), "Open" loads via `self._service.load()` and emits `opened_workflow(Path(name))` (my_automations.py:128-149), "Preview" loads and calls `self._service.preview_replay(workflow)` but emits `preview_requested()` (my_automations.py:140-149), "Run" loads and calls `self._service.run_workflow(workflow)`, emits `run_requested(Path(name))` (my_automations.py:150-159). **Has matching widgets** (QListWidget + Open/Preview/Run). **Differs**: Preview/Run call service directly without authorized folder selection/confirmation like main_window; no replay preview list display in page.
- **ui/pages/create_automation.py** (95 lines): task entry; emits `task_entered` (shell wires to `_handle_task_entered` → builds workflow via service, shows review page). **Has placeholder** for task entry; **lacks**: full form editor (name/step kind/message/draft list/move/remove) that main_window provides.
- **ui/pages/activity.py** (93 lines): activity list; shell connects `run_selected` to `_show_run_details` (stub). **Has placeholder/list**; **lacks**: full history details with step results like main_window.
- **ui/pages/review.py** (112 lines): workflow review; shell connects `approved` to `_on_approved` (stub), `cancelled` to `_on_review_cancelled` (goes home). **Different from ProposalReviewPanel** - this is for workflow review, not agent proposal review. Main_window uses `ProposalReviewPanel` directly in tab; shell uses `ReviewPage` differently.
- **ui/pages/settings.py** (232 lines): has verifier config UI elements and signals `verifier_configured`, `recording_started`, `recording_stopped` (settings.py:40-55, 70+). **Has matching signals** for recording/verifier; **lacks**: full recording management UI (list recordings, view events, analyze, delete) that main_window has in Workflows tab.

## 2) ui/shell.py MainWindow constructor vs app.py
- **ui/shell.py:196-217** `MainWindow.__init__(self, service: WorkflowService | None = None, recording_service: RecordingService | None = None, verifier_config: VerifierConfig | None = None, verifier_note: str | None = None, app_data_dir: Path | None = None) -> None` - same signature.
- **app.py:104-133** passes: `MainWindow(service, recording_service, verifier_config=verifier_config, verifier_note=verifier_note, app_data_dir=app_data_dir)` (app.py:120-127). **Identical args/signature**. Shell MainWindow stores them as `self._service`, `self._recording_service`, `self._verifier_config`, `self._verifier_note`, `self._app_data_dir` (shell.py:214-219) but does **not** pass them to pages in `__init__` (no `set_service` calls visible). HomePage has `set_service()` (home.py:170-172), MyAutomationsPage has `set_service()` (my_automations.py:185-187) - **not wired in shell currently**.

## 3) ui/review_view.py, ui/verifier_dialog.py, ui/workers.py
### ui/review_view.py (527 lines)
Provides `ProposalReviewPanel(QWidget)` (review_view.py:111-527). Lists proposals via `self._service.agent_proposals()` (review_view.py:203-246), shows diff/evidence/verification records (review_view.py:248-362), actions: verify (`VerifyProposalWorker`), approve+apply (`ApplyProposalWorker`), apply recorded approval (`ApplyRecordedApprovalWorker`), reject, configure checks via `VerifierConfigDialog` (review_view.py:364-527). Depends on `ui.workers`, `ui.verifier_dialog`, controller service methods. Used by **main_window "Agent proposals" tab** (main_window.py:27,325-330). Long-running work off-thread via QThread workers.

### ui/verifier_dialog.py (151 lines)
Provides `VerifierConfigDialog(QDialog)` (verifier_dialog.py:65-151). Collects cases path, argv (one per line, must contain `{input}`), timeout, worktree root. Calls `save_verifier_config()` and returns saved config. Used by `ProposalReviewPanel._configure_checks()` (review_view.py:436-447). **No tests/test_verifier_dialog.py exists**.

### ui/workers.py (187 lines)
QThread workers (workers.py:35-187): `WorkflowWorker` runs workflow/replay via service with cancel/progress (workers.py:35-87); `VerifyProposalWorker` pre-merge verification (workers.py:90-138); `ApplyProposalWorker` applies approved change (workers.py:141-161); `ApplyRecordedApprovalWorker` applies recorded approval (workers.py:164-184); `PostMergeVerifyWorker` post-merge verification (workers.py:187+). Used by **main_window** for running workflows (main_window.py:27,473-492) and by **ProposalReviewPanel** for proposal operations (review_view.py:37-42,459-527).

## 4) Tests covering old-window behavior
- **tests/test_smoke.py**: tests `MainWindow` construction, controls, demo run, form creation, draft reordering/removal, recording/analyze/approve flow with fake recorder, app smoke test (test_smoke.py:1-264). Covers main_window workflows tab features.
- **tests/test_review_ui.py**: tests `ProposalReviewPanel` and `MainWindow` agent proposals tab with real temp git repos and fake agent (test_review_ui.py:1-523). Covers proposal review/verification/approval/journey.
- **tests/test_app_entry.py**: tests app entry point, logging, startup failures, smoke test (test_app_entry.py:1-140).
- **tests/test_shell.py**: tests `ui.shell.MainWindow` (separate window) - 52 lines shown earlier, exercises shell.
- **tests/test_workers.py** exists (seen in earlier file list) - tests worker behavior.
- **tests/test_verifier_dialog.py**: **does not exist**. ProposalReviewPanel tests use QMessageBox monkeypatching in some cases (test_review_ui.py:452-477, 523 shows QMessageBox.warning monkeypatch). Verifier dialog tests exist inline in test_review_ui.py (test_review_ui.py:478-523).

## 5) Ordered slice list (lowest risk first)
Each slice keeps old window working and all tests green. `app.py` keeps `ui.main_window` as default until last slice. Add `--shell` flag for manual testing.

**Slice 1 (special): Add `--shell` flag to app.py**  
- Branch: `slice/shell-flag`  
- Add arg parsing for `--shell` (keep `--smoke-test`). If `--shell`, import and instantiate `ui.shell.MainWindow` with same args (service, recording_service, verifier_config, verifier_note, app_data_dir) as main_window gets; else use `ui.main_window.MainWindow` (default). Both windows must work with `--smoke-test`. Add tests in `tests/test_app_entry.py` or new test. Produce screenshots of all pages through real `app.py --shell` path into `docs/screenshots/slice-1/`. **CHECKPOINT 1** after merge/push - stop for user to test.

**Slice 2: Activity/history page wiring (read-only)**  
- Branch: `slice/activity-page`  
- Wire `ActivityPage` to `controller.service` for history display. Add service injection if needed (ActivityPage currently takes no service). Make it read-only, reuse existing service methods. Add pytest-qt tests. Screenshots.

**Slice 3: My automations page (list/open/preview/run)**  
- Branch: `slice/my-automations-page`  
- Pass service to `MyAutomationsPage` (has `set_service()`). Wire Open/Preview/Run to use service properly; ensure preview uses replay preview flow where appropriate. Add tests.

**Slice 4: Create automation and draft editing**  
- Branch: `slice/create-automation`  
- Wire `CreateAutomationPage` fully; add draft step editing capabilities similar to main_window (add/move/remove steps) if needed, or ensure task->workflow flow works. Add tests.

**Slice 5: Recording lifecycle in shell**  
- Branch: `slice/recording-shell`  
- Wire recording UI in shell/SettingsPage to use `RecordingService` same as main_window (start/stop/list/events/analyze/delete). Add tests.

**Slice 6: Review/approval and verifier configuration**  
- Branch: `slice/review-approval-shell`  
- Wire `ReviewPage` and/or integrate `ProposalReviewPanel` functionality into shell; wire verifier configuration dialog. Reuse existing workers/panels. Add tests.

**Slice 7: Desktop and browser steps in create_automation**  
- Branch: `slice/desktop-browser-steps`  
- Add support for creating/previewing desktop steps (LAUNCH_APPLICATION, WAIT_WINDOW, CLICK_UI_ELEMENT, TYPE_TEXT, PRESS_SHORTCUT, VERIFY_FILE_TEXT) and browser steps (LAUNCH_BROWSER, NAVIGATE_BROWSER, INSPECT_PAGE, FIND_PAGE_ELEMENT, INTERACT_PAGE_ELEMENT, WAIT_PAGE). Must reuse `engine.desktop.approve_desktop_workflow` and show mutating step kinds before approval enabled (use `mutating_kind_names`/`requires_desktop_approval`). Never create second approval path. Add tests.

**Slice 8 (final): Switch default to shell, retire/keep main_window per decision**  
- Branch: `slice/switch-default`  
- **CHECKPOINT 2** before changing default in app.py or retiring ui/main_window.py - stop and report. User decides. Do not make change without approval.

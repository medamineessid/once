# Button audit (P1.2) — every clickable control in the shell

Date: 2026-10-29. Branch: slice/p1-foundations. Scope: `ui/shell.py` and
`ui/pages/*.py` only (the old window `ui/main_window.py` is being retired and is
not part of the MVP surface; its behaviour is the parity reference for journeys
J1-J7 instead).

Rule applied (docs/WORKING_AGREEMENT.md): a control counts as WORKING only when
a test clicks it and asserts an observable effect. Connection counting alone is
not evidence. Every control below has an observable effect; `pass`-bodied
handlers and dead signals are listed in section 3 and assigned to journeys —
they are not claimed as working.

Handler defences found on this audit pass and fixed in this slice:

- `ui/shell.py:230` `_open_workflow` called `review_page.set_workflow(...)`,
  which never existed on `ReviewPage` (ui/pages/review.py). Clicking "Open"
  raised `AttributeError: 'ReviewPage' object has no attribute 'set_workflow'`
  in the Qt slot (captured stderr in the failing test run). Fixed by adding
  `ReviewPage.show_workflow` (ui/pages/review.py:99) read-only display; test
  `test_open_button_click_shows_opened_workflow_on_the_review_page`.

## 1. audited controls (page, label, handler, effect, test)

| # | Page | Control | Handler (file:line) | Observable effect | Test that clicks it and asserts |
|---|------|---------|--------------------|-------------------|--------------------------------|
| 1 | Sidebar | Home QToolButton | `ui/shell.py:203` via `sidebar.homeClicked` | Workspace → Home, sidebar checked | test_sidebar_click_home_returns_to_home (tests/test_shell.py) |
| 2 | Sidebar | My automations QToolButton | `ui/shell.py:206` | Workspace → My automations, list refreshed | test_page_navigation_switches_workspace |
| 3 | Sidebar | Activity QToolButton | `ui/shell.py:210` | Workspace → Activity, history refreshed | test_sidebar_active_state_after_sidebar_click |
| 4 | Sidebar | Settings QToolButton | `ui/shell.py:214` | Workspace → Settings | test_sidebar_click_settings_switches_and_checks |
| 5 | Home | "Create an automation" QPushButton | `ui/pages/home.py:83` → `created_automation` → `ui/shell.py:223` | Workspace → create flow | test_home_create_button_clicks_into_create_flow |
| 6 | Home | "Try a demonstration" QPushButton | `ui/pages/home.py:86` → `run_demo_requested` → `ui/shell.py:227` `service.run_demo()` | One demo run persisted in history (SUCCEEDED) | test_home_demo_button_runs_the_demo_exactly_once |
| 7 | My automations | workflow list row | `ui/pages/my_automations.py:119` | Details label shows workflow steps | test_details_match_selected_automation (tests/test_my_automations_page.py) |
| 8 | My automations | Open QPushButton | `ui/pages/my_automations.py:136` → shell `_open_workflow` `ui/shell.py:230` | Review page shows the opened workflow's steps | test_open_button_click_shows_opened_workflow_on_the_review_page |
| 9 | My automations | Preview QPushButton | `ui/pages/my_automations.py:149` | Details label shows read-only preview steps and executability; never runs | test_preview_shows_steps_and_never_calls_run |
| 10 | My automations | Run QPushButton | `ui/pages/my_automations.py:175` → `_start_run` (ui/workers.py WorkflowWorker) | Confirmation question, then a real run with progress lines and final status; buttons disabled while running | test_run_with_confirmation_calls_run_once_with_loaded_workflow, test_run_button_stays_disabled_until_run_finishes |
| 11 | Activity | history run row | `ui/pages/activity.py:41` `_on_selection_changed` | Details label shows id, status, step lines | test_activity_run_click_shows_its_steps |
| 12 | Review | Edit QPushButton | `ui/pages/review.py:83` | none — body is `pass` | clicks asserted impossible until J6 (see section 3) |
| 13 | Review | Cancel QPushButton | `ui/pages/review.py:86` → `cancelled` → `ui/shell.py:252` | Workspace → Home | test_review_cancel_button_click_returns_home |
| 14 | Review | Approve and run QPushButton | `ui/pages/review.py:89` | Real handler, but inert until the page has a service and a proposal (see section 3, J6) | scheduled for J6 acceptance test |
| 15 | Create | "Create automation" QPushButton | `ui/pages/create_automation.py:77` `_create_from_description` | Non-blank text emits `task_entered`; shell acknowledges in plain language (J2 replaces) | test_create_automation_button_emits_typed_task, test_create_automation_button_ignores_blank_input |
| 16 | Settings | "Choose folder" QPushButton | `ui/pages/settings.py` `_choose_authorized_folder` | Dialog → `service.set_allowed_root`, label shows the chosen folder; cancel changes nothing | test_settings_authorized_folder_persists_through_service, test_settings_authorized_folder_cancel_keeps_previous_value |
| 17 | Settings | "Configure checker…" QPushButton | `ui/pages/settings.py` `_configure_verifier` | Real `VerifierConfigDialog`; on save emits `verifier_configured` | test_settings_verifier_button_saves_and_signals |

Run confirmation modal (control 10): `QMessageBox.question` confirms before a
run. Working agreement forbids blocking modals in tests; tests monkeypatch the
question. Parity: the old window confirmed replay execution the same way
(docs/ui_migration_plan.md section 1). Destructive-action inline confirm (per
the session decision) does not apply — a workflow run is not a delete.

## 2. signals connected to the shell

- `home_page.created_automation` → `_show_create_automation` (works)
- `home_page.run_demo_requested` → `_run_demo_from_home` (works, exactly one run)
- `my_automations_page.opened_workflow` → `_open_workflow` (works after this slice)
- `create_automation_page.task_entered` → `_handle_task_entered` (acknowledge; J2 builds)
- `review_page.cancelled` → `_on_review_cancelled` (works)
- `activity_page.run_selected` → `_show_run_details` (`pass`, ui/shell.py:255; J4)
- `review_page.approved` → `_on_approved` (`pass`, ui/shell.py:249; J6)
- `my_automations_page.run_requested` `preview_requested` — emitted but never connected (J3)
- `settings_page.verifier_configured` — emitted but not connected; its only
  effect today is the page's own `_verifier_config` update (acceptable: the
  verifier dialog persists the configuration itself; J8 may surface a banner)

Unwired-controls guard: `test_every_page_has_no_unwired_buttons` covers
QPushButton **and** QToolButton on every page plus the sidebar; proved able to
fail by temporarily adding an unconnected visible "Ghost" button on Home — the
test failed with `FAILED tests/test_shell.py::test_every_page_has_no_unwired_buttons`
(AssertionError listing `HomePage: Ghost`); the temporary button was removed
immediately afterwards (git diff confirmed zero changes in ui/pages/home.py).

## 3. `pass` bodies and dead wiring (assigned, not claimed as-working)

| Location | What doesn't work yet | Assigned journey | Interim honest state |
|---|---|---|---|
| `ui/shell.py:255` `_show_run_details` body `pass` | selecting a run emits a signal the shell ignores; details come from the page itself | J4 | Activity page still shows steps in its own details label (test 11) |
| `ui/shell.py:249` `_on_approved` body `pass` | approving a proposal has no effect | J6 | approval path exists at `ai.approval.approve_proposal`; page's approve handler is real but inert without service/proposal |
| `ui/pages/review.py:83` `_edit` body `pass` | Edit button does nothing | J6 | audited, deferred; hidden only if J6 leaves it without a real effect |
| `my_automations_page.run_requested`/`preview_requested` | signals no listener | J3 | buttons still have direct service effects (they do not depend on the signals) |

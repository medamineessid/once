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
| 12 | Review | Edit QPushButton | none — hidden (2026-10-29 amendment) | hidden until J6 wires it; no pass handler exists any more (removed with the connection) | test_review_edit_and_approve_are_hidden_until_j6 |
| 13 | Review | Cancel QPushButton | `ui/pages/review.py:86` → `cancelled` → `ui/shell.py:252` | Workspace → Home | test_review_cancel_button_click_returns_home |
| 14 | Review | Approve and run QPushButton | none — hidden (2026-10-29 amendment) | hidden until J6 wires Approve through the approval path | test_review_edit_and_approve_are_hidden_until_j6 |
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
- `activity_page.run_selected` — the dead `pass` connection was REMOVED (2026-10-29);
  details come from the page's own selection handler (test 11)
- `review_page.approved` — the dead `pass` connection was REMOVED (2026-10-29);
  Approve itself is hidden until J6
- `my_automations_page.run_requested` `preview_requested` — emitted but never connected (J3)
- `settings_page.verifier_configured` — emitted but not connected; its only
  effect today is the page's own `_verifier_config` update (acceptable: the
  verifier dialog persists the configuration itself; J8 may surface a banner)

Unwired-controls guard (strengthened 2026-10-29): `test_every_page_has_no_unwired_buttons`
covers QPushButton **and** QToolButton on every page plus the sidebar, and now
follows the wiring statically (AST): a connected handler may not be `pass`-only,
and a handler that only emits a signal must chain to a downstream shell handler
(relay hops like the sidebar's `clicked_custom` → `homeClicked` are followed,
bounded to 6 hops). Proved able to fail twice, both pasted in the log:
(1) pass-only — before the fix it reported `shell.py connects a pass-only
handler: _on_approved` and 3 more; (2) chain — with a temporary emit-only
"Ghost" button on Home it reported `home.py: _ghost_requested -> signal
ghost_requested has no downstream connection`. Both temporaries were reverted
(`git diff ui/pages/home.py` empty afterwards).

## 3. `pass` bodies and dead wiring (assigned, not claimed as-working)

| Location | What doesn't work yet | Assigned journey | Interim honest state |
|---|---|---|---|
| `ui/pages/review.py` `_edit` (removed) | Edit button has no handler | J6 | button hidden and unconnected; test asserts it stays hidden until J6 |
| `ui/pages/review.py` `_approve` (hidden) | approving needs a service + proposal the shell does not inject yet | J6 | button hidden; shell does not call `review_page.set_service` yet |
| `my_automations_page.run_requested`/`preview_requested` | signals have no listener | J3 | buttons have direct page-local service effects and stay visible; J3 wires them through the shell |
| `ui/shell.py` `_on_approved`/`_show_run_details` (removed) | — | J6/J4 | dead `pass` connections deleted, not hidden: their pages show the effects themselves |

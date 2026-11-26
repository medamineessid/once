# MVP checklist

Status: current
Last verified: 2026-11-26 · `main f2e6ca3`
Owner: lane C (proof and delivery)

A capability is marked **working** only when a named test or command exercises
the real service or entry point. The capability list with an evidence level per
row lives in `docs/STATE.md`; this page is the gate that was used to decide the
shell is the default window.

| Capability | Status | Proof |
|---|---|---|
| Start the shell through the real entry point | Working | `tests/test_app_entry.py::test_smoke_test_with_shell_flag_exits_zero` |
| Classic-window escape hatch | Working | `tests/test_app_entry.py::test_smoke_test_with_classic_flag_exits_zero` |
| Create an automation | Working | `tests/test_editor_page.py::test_empty_editor_add_step_button_creates_an_editable_node` |
| Rename, edit, undo, redo, save | Working | `tests/test_editor_page.py` |
| Persist layout positions and notes | Working | `tests/test_workflow_layouts.py` |
| Review and edit a saved automation | Working | `tests/test_shell.py::test_review_edit_button_opens_saved_workflow_in_editor` |
| Record a local task into a reviewable draft | Working | `tests/test_shell.py::test_recording_review_approval_opens_editable_draft` |
| Approve recorded drafts | Working | `tests/test_shell.py::test_recording_review_approval_opens_editable_draft` |
| Run a saved automation | Working | `tests/test_editor_page.py::test_saved_editor_definition_runs_and_refreshes_activity` |
| Live step state and evidence | Working | `tests/test_editor_page.py::test_editor_shows_step_result_and_evidence_in_inspector` |
| Cancel safely during a run | Working | `tests/test_close_during_run.py` |
| Approval gate for mutating desktop steps | Working | `tests/test_editor_page.py::test_editor_shows_existing_desktop_approval_gate` |
| First-time journey through `app.py` | Working | `tests/test_entry_acceptance.py::test_first_run_home_offers_two_working_entry_points` |
| Editor acceptance through the real entry point | Working | `tests/test_entry_acceptance.py::test_first_time_journey_through_entry_point_creates_and_runs` |
| Honest run outcomes | Working | `tests/test_b1_run_outcomes.py` |
| Delete a run / an automation, with a readable dialog | Working | `tests/test_delete_flows.py`, `tests/test_confirm_dialog.py` |
| Buttons and sidebar defects V5, V8 | Fixed (tests only) | PR #27, `tests/test_layout_geometry.py` |
| Packaged executable | Built once | `once.spec`; `Once.exe --smoke-test` exited 0 on the build machine (2026-11-22, not re-run since) |
| Smart replay in the app path | Not wired | `ONCE_SMART_REPLAY` is read only in `engine/smart_replay.py` |
| Branching / decision nodes | Parked | not in scope for the MVP |

## Release gate

The switch to the shell as the default window was made only after every
MVP-scope row above was working, the first-time acceptance path passed through
`app.py`, the editor acceptance path passed, and the packaged executable started.
`--classic` remains available, and `docs/REAL_DESKTOP_CHECKLIST.md` is the
person-run pass that upgrades a row from **tests only** to **real desktop**.

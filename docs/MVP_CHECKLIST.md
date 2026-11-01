# Once MVP checklist

This checklist records the current shell MVP gate. A capability is marked
**working** only when a test exercises the real service or application entry
point.

| Capability | Status | Implementation | Proof |
|---|---|---|---|
| Start the shell through the real entry point | Working | `app.py --shell` | `tests/test_app_entry.py::test_smoke_test_with_shell_flag_exits_zero` |
| Explicit classic-window escape hatch | Working | `app.py --classic` | `tests/test_app_entry.py::test_smoke_test_with_classic_flag_exits_zero` |
| Create an automation | Working | `ui/pages/editor.py` | `tests/test_editor_page.py::test_empty_editor_add_step_button_creates_an_editable_node` |
| Rename, edit, undo, redo, and save | Working | `controller/editor.py`, `ui/pages/editor.py` | `tests/test_editor_page.py` |
| Persist layout positions and notes | Working | `storage/layouts.py`, `controller/editor.py` | `tests/test_workflow_layouts.py` |
| Review and edit a saved automation | Working | `ui/pages/review.py` | `tests/test_shell.py::test_review_edit_button_opens_saved_workflow_in_editor` |
| Record a local task into a reviewable draft | Working | `controller/recording.py`, `ui/shell.py` | `tests/test_shell.py::test_recording_review_approval_opens_editable_draft` |
| Approve recorded drafts | Working | `ai/approval.py`, `ui/pages/review.py` | `tests/test_shell.py::test_recording_review_approval_opens_editable_draft` |
| Run a saved automation | Working | `ui/workers.py`, `controller/service.py` | `tests/test_editor_page.py::test_saved_editor_definition_runs_and_refreshes_activity` |
| Show live step state and evidence | Working | `ui/editor/canvas.py`, `ui/editor/inspector.py` | `tests/test_editor_page.py::test_editor_shows_step_result_and_evidence_in_inspector` |
| Cancel safely during a run | Working | `ui/workers.py`, `ui/shell.py` | `tests/test_close_during_run.py` |
| Require approval for mutating desktop steps | Working | `engine/desktop.py`, `ui/pages/editor.py` | `tests/test_editor_page.py::test_editor_shows_existing_desktop_approval_gate` |
| Branching / decision nodes | Parked | `docs/PARKED.md` PARKED-1 | Intentionally out of MVP scope |
| Packaged executable | Working | `once.spec`, `dist/Once/Once.exe` | PyInstaller build completed; isolated `Once.exe --smoke-test` exited 0 and created `once.db` |
| Default shell window | Pending | `app.py` | Switch only after this checklist has no MVP-scope Missing rows |

## Release gate

P9 may switch the default window only after all MVP-scope rows are Working,
the first-time acceptance path passes through `app.py`, the editor acceptance
path passes, and the packaged executable starts. The classic window remains
available through `--classic`; `--shell` remains an explicit alias.

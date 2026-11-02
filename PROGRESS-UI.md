# UI redesign progress

NEXT TASK: Close the two pending MVP acceptance rows (docs/MVP_CHECKLIST.md) by driving the first-time editor journey (create → rename → save → run → Activity) through the real `app.py` entry point in an automated test — choice noted: one shared journey test proves both pending rows.

## Log
- 2026-11-02: DONE. Entry-point acceptance: extracted `app.build_window`, added `tests/test_entry_acceptance.py` (first-run Home + full create → rename → save → run → Activity journey through real wiring on isolated LOCALAPPDATA). Files: app.py, tests/test_entry_acceptance.py, PROGRESS-UI.md. Checks: pytest tests/test_entry_acceptance.py tests/test_app_entry.py → 8 passed; ruff check/format clean. Next: update the two MVP_CHECKLIST rows to Working with the new proof, then commit docs.
- 2026-11-02: DONE. MVP_CHECKLIST first-time-journey and editor-acceptance rows marked Working with the new test names (docs/MVP_CHECKLIST.md). Checks: docs-only change. Next: UX audit D14 relabel of the opened-workflow review mode.
- 2026-11-02: DONE. Review page opened-workflow mode retitled "Automation details" (audit D14), strings moved to ui/strings.py, shell test updated. Files: ui/strings.py, ui/pages/review.py, tests/test_shell.py. Checks: pytest tests/test_shell.py -k review → 6 passed; ruff clean. Next: refresh docs/screenshots/latest through the real capture path and update INDEX.md.

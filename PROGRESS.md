# Autonomous Execution Progress & Decisions

## Plan Progress
- [x] **1. Housekeeping**: Replaced bare `except Exception:` in `WorkflowService.__init__` (`controller/service.py`) with `except (ImportError, OSError, RuntimeError):`. Tested `HotkeyKillSwitch` (`Ctrl+Alt+Q`); `SetWindowsHookEx(WH_KEYBOARD_LL)` installs a valid hook handle, though synthetic keystrokes from a headless subshell cannot trigger the low-level hook without an interactive foreground desktop window / physical keyboard input.
- [x] **2. Recorder fix**: Updated `WindowEventMonitor` (`integrations/recorder.py`) and `_win32_windows()` to include `hwnd` and track windows by stable `(process_name, hwnd)` identity. Added `WINDOW_TITLE_CHANGED` in `recorder/models.py` and `recorder/drafts.py`. Added regression test using `tests/fixtures/recording-1794212626041060300.json`.
- [x] **3. Draft generator fix**: Filtered OS shell processes (`StartMenuExperienceHost.exe`, `ApplicationFrameHost.exe`, `ShellExperienceHost.exe`, `SearchHost.exe`, `TextInputHost.exe`, `SystemSettings.exe`, `explorer.exe`) in `ai/provider.py`. Added `_is_flapping_or_title_change` so title-change closes do not emit `CLOSE_APPLICATION`. Allowed titlebar Close clicks on non-launched (e.g. UWP/Start-launched) windows to emit `CLICK_UI_ELEMENT` ("Close <window>"). Added regression test on `recording-1794212626041060300.json`.
- [x] **4. Click fallback**: Added defined fallback order in `PywinautoDesktopActions.click_element` (`integrations/windows_desktop.py`): UIA `Invoke` pattern first, then re-verify window/element presence & bounds and click element bounding box center via injectable `mouse_click` (`pywinauto.mouse.click`). Added unit tests in `tests/test_windows_desktop.py`.
- [x] **5. Prove it on real desktop**: Ran `WindowEventMonitor` and `WorkflowService.run_desktop_approved` with Notepad on the real Windows 11 desktop. `WindowEventMonitor` recorded `WINDOW_OPEN ('Bloc-notes')` -> `WINDOW_TITLE_CHANGED ('Sans titre – Bloc-notes')` -> `WINDOW_CLOSE` with zero spurious close/open flapping. Full `LAUNCH_APPLICATION -> WAIT_WINDOW -> TYPE_TEXT -> CLOSE_APPLICATION` workflow returned `SUCCEEDED` (`s1` launched, `s2` window appeared, `s3` typed `"Hello Once"` into `RichEditD2DPT`, `s4` reported launcher stub already exited on Win11 Store Notepad).
- [x] **6. Phase 2 UX fixes**: Home (run names, plain status wording `X of Y steps ran`, failure reasons + `View details`, unified grid width, empty/loading states), Automation details (friendly labels + icons, no internal ids or `Observation N:`, full-page scroll, inline step edit, fit-to-view diagram without minimap overlap, `Back`/`Edit automation`/`Run` buttons), fixed sidebar highlight on details, clean Activity step details, focus rings and WCAG 4.5:1 contrast.
- [x] **7. Phase 3 anti-slop**: Centralized remaining component colors into `ui.styles` tokens, removed inline toolbar stylesheet, verified zero filler copy and zero hardcoded hex colors outside `ui/styles/`.
- [x] **8. Delete runs and automations**: Per-run Delete on Activity and Home recent runs, Clear all runs on Activity, and Delete on My automations and Automation details. In-progress runs refuse deletion in the UI and controller. Confirm dialogs name the target and default to deleting its runs; automation deletion can keep history. Deletion is limited to Once's workflow files and its own database rows. Tests cover one run, clear all, automation with/without runs, the running-run refusal, and every page entry point.
- [x] **9. Storage safety**: Recording IDs are now confined to the recordings folder (traversal and symlink escapes refused for save/load/delete), and workflow/recording saves write a unique temporary sibling before replacing the destination, so an interrupted write keeps the previous file. Tests: `tests/test_storage_safety.py` (3).
- [x] **10. UI leak in My automations**: Automation details, preview heading, and live run progress no longer show workflow IDs, step IDs, or enum names; they use the existing friendly step labels and status text. Tests updated in `tests/test_my_automations_page.py`.
- [x] **11. Silent blocker-check failure**: The coding-agent review panel now narrows broad catches to `OnceError`, `OSError`, and `sqlite3.Error`, includes the real failure in the visible message, and logs it before showing it. Regression test: `tests/test_review_ui.py::test_blocker_check_failure_is_shown_and_logged`.
- [x] **12. Legacy recording delete confirmation**: The legacy window now asks "Delete recording '…'? This cannot be undone." with Cancel as the default before deleting a saved recording. Test: `tests/test_legacy_delete.py`.
- [x] **13. README flag drift**: README now names `--classic` (the flag `app.py` implements) instead of the nonexistent `--legacy`. Test: `tests/test_docs_truth.py`.
- [x] **14. Silent recorder UI Automation failures**: UIA point/focus/window inspection now catches only expected import, attribute, OS, runtime, value, type, and loaded-COM errors, logs a warning with the real reason, and keeps recording without metadata instead of failing silently. Regression test: `tests/test_recorder_logging.py` (verified failing before the fix and passing after).
- [x] **15. Activity page test fix**: Fixed `test_activity_page_lists_history_runs` failing assertion `"demo-local-workflow" in first_item.text()` by setting `QListWidgetItem` text to `friendly_run_name()` instead of empty string in `_refresh()`. All 683 tests pass, 2 skipped.
- [x] **16. Ruff formatting/lint fixes**: Fixed unused `os` import and `noqa` directives in `scripts/capture_ui_shots.py`; resolved E501 line length. All checks green.
- [x] **17. Fonts actually load**: Six of seven bundled files were corrupt (`0a0a0a0a` headers / 14-byte Inter-Regular). Replaced with static Inter Regular/Medium/SemiBold from rsms/inter v4.0 and kept the official static Anton. `scripts/diagnose_fonts.py` now reports 0 failing files and no `qt.qpa.fonts` messages. `load_fonts()` runs in `app.py` and in the shell; the app sets Inter as the default font. `tests/test_font_family.py` is strict via a subprocess and fails unless QFontInfo resolves "Anton" and "Inter".
- [x] **18. Tokens restored**: `GLACIER_600` is glacier blue `#2472B0` (was gray `#86868B`), and `NAVY`, `WHITE`, `LEMON`, `HERO_BLUE`, `HERO_BLUE_CONTRAST` were added. `FONT_STACK` now starts with Inter; `DISPLAY_FONT_STACK` is Anton. `scripts/audit_tokens.py` prints every token and contrast pair (white on hero 5.11:1, lemon on hero 3.71:1 at 128px).
- [x] **19. Run proof**: `python app.py` stayed alive for 18 seconds with an empty console (no font warnings, no traceback), verified by a process-liveness check rather than an exit code.
- [x] **20. Screenshot/diagnose flags**: `app.py --screenshot PATH --page NAME` and `--diagnose --page NAME` build the real shell, wait 800 ms, and capture or print QFontInfo measurements. All five pages captured to `shots/design-v3/`. Pixel diff vs the pre-redesign Home (shots/ui-after/home.png) is 88.3%, so the design is visibly changed.
- [x] **21. Pages and motion**: Home uses a reusable `Hero` (Anton 128px lines, real saved-automation count). My automations, Activity, Settings, and Automation details gained a `MicroLabel` with a real count and Anton page titles. Dialogs now fade and scale 0.98 -> 1.0 in 220 ms; hero lines reveal 16px/280ms/60ms stagger; reduced-motion tests assert both are instant when animations are off.
- [x] **22. Unsafe-fix review**: `git show --stat fbd46e4` shows 3 files, 6 deletions (literal-to-token and item-text changes; no functions or imports removed). This session's earlier `--unsafe-fixes` run had corrupted `ui/components/formatting.py` to `except TypeError, ValueError:`; the bundled `ruff format` (reported 0.17.1) also rewrites `except (TypeError, ValueError):` into that invalid form, so the handler now names a module-level `_TARGET_PARSE_ERRORS` tuple. `ruff format --check` and `py_compile` both pass. Also rewrote the over-broad `tests/test_tokens_scan.py` to assert the real invariant (no hex colors outside the token file) instead of xfail-ing every geometry literal.- [x] **23. Design v4 (intense + consistent)**: Navy sidebar with the lemon Anton wordmark, lemon active pill and Phosphor 24px icons at a 14px gap; every page header is a colour band with an Anton 72px title cropped at the band edge, a real-count micro label and one guiding line; Home has the clipped uppercase hero with a 128px lemon Record circle and an outlined Build button, plus three real-data stat blocks and the real recent-runs list; My automations rows own Run/Open/Delete with a last-status pill and a saved date, drafts get a title derived from their first meaningful step, and "Clear unnamed drafts" confirms first; Activity is a compact band plus one 48px-icon empty state; Settings uses section cards, not group boxes. One button system (lemon fill/navy text, navy fill/lemon text, outlined navy secondary, outlined red destructive), brand lemon only as fill/display, motion 260ms page transitions and 220ms dialog fade, all instant when Windows animations are off. Proven by `shots/design-v4/*.png`, `app.py --diagnose` (Anton 72px title, 24x24 icon with a 14px gap, 48x48 empty icon, 0 font warnings) and `tests/test_design_v4.py` (22 tests); full suite `752 passed, 2 skipped in 104.95s`.
- [x] **24. Make the product work on a real desktop**: `Ctrl+Alt+Q` now actually fires (pynput's hotkey parser never matched the key on this layout; the switch tracks ctrl/alt/virtual-key itself), and `scripts/prove_kill_switch.py` went from FAILED (`triggered: false`) to `status: CANCELLED`, `kill switch triggered: True`, 0 leftover windows. A **Stop** button appears in the footer only while a run is live and cancels the active run. **Close works on Windows 11 Notepad**: ownership is "window new since launch + same image file name", the app's own save prompt is answered with "don't save" (no file is written), and a window that vanishes mid-close counts as closed. Recorded drafts no longer contain window-title-change steps, and launch/close steps are named "Open Notepad" / "Close Notepad". Activity rows carry duration and the first plain failure reason, with per-run **Run again** (through the same approval gate) and a red **Delete**. A missing control reports "Could not find the 'Save' button in Notepad." and a retried step waits 0.4s instead of repeating the same miss. `{name}` in a step is asked for at Run and substituted before approval. `ruff` targets py312 again, so `except (A, B):` stays parseable on the supported minimum. Proven by `scripts/prove_notepad_flow.py` (real desktop: 7 recorded events -> 4 clean steps -> two runs, both SUCCEEDED, 0 windows left behind), `shots/after/notepad-flow.json`, `shots/after/kill-switch.json`, `shots/design-v4/activity-runs.png`, `tests/test_run_controls.py`, `tests/test_parameters.py`, `tests/test_app_starts.py`, and a full suite of `782 passed, 3 skipped in 118.36s`.


## Decisions
1. **Kill switch testing in headless shell**: Since `run_command` executes in a background shell without physical keyboard input and Windows `WH_KEYBOARD_LL` ignores synthetic input when no interactive console/foreground window is attached, we verified hook installation (`SystemHook` handle non-zero) and unit-tested trigger semantics via `FakeListener`, documenting the physical-input limitation.
2. **OS shell process list**: Filtered `startmenuexperiencehost.exe`, `applicationframehost.exe`, `shellexperiencehost.exe`, `searchhost.exe`, `textinputhost.exe`, `systemsettings.exe`, and `explorer.exe` from `LAUNCH_APPLICATION` / `CLOSE_APPLICATION` lifecycle steps because they are Windows shell/UWP container hosts, not standalone user-launched applications.
3. **Titlebar Close button handling**: Kept `Close` button clicks on `launched` apps as `REPORT` (preserving `test_titlebar_close_button_click_maps_to_report_step`), while allowing `Close` button clicks on interactively opened windows (like UWP Settings) to emit `CLICK_UI_ELEMENT` ("Close Paramètres").
4. **Activity list item text**: QListWidgetItem display text should show the friendly run name (via `friendly_run_name()`) rather than being empty, so both test assertions and UI readability are consistent.
5. **Ruff script fixes**: `scripts/capture_ui_shots.py` lint errors (unused import, noqa directives, line length) are cosmetic/script-internal; do not affect UI or engine behavior.
- [x] **25. List rows stay inside their list**: My automations sized its list from a row height measured before stylesheet padding applied, so a third saved automation was cut off with the scrollbar switched off. The page now measures the rendered rows and re-fits on `showEvent`; `shots/design-v4/automations-rows.png` shows all three rows and `tests/test_my_automations_page.py::test_every_row_fits_inside_the_list` pins it. Full suite `783 passed, 3 skipped in 101.68s`, `ruff check .` clean.

## Log ordering exception (PR #1, 2026-11-21)

`docs/ai_engineering_log.md` on `lane-a-merged` is not a strict append of
`main`'s copy. The branch inserted 459 lines between the file header and the
first `2026-10-21` entry instead of appending at the end. No line was lost or
edited: all 1289 of `main`'s lines are present, in order (verified by a line
subsequence check, 1289 of 1289). The one "deleted line" reported by
`git diff --numstat` is `main`'s final line, which has no trailing newline.

- HEAD 1-4: header.
- HEAD 5-281: 17 entries, 2026-11-07 down to 2026-11-01, inserted out of order.
- HEAD 282-1567: the original log, starting at `2026-10-21 -- Step 0`.
- HEAD 1568-1748: 9 entries appended at the end, 2026-11-01 to 2026-11-18.
- HEAD 293-294: two blank lines added inside the separator before
  `2026-10-22 -- Draft editing`.

The log is not reordered or edited to fix this: moving 276 lines inside an
append-only file is itself a rewrite. Until PR #1 merges, the CI gate runs
`scripts/check_log_append_only.py --mode boundary`, which requires every base
line to survive in order and every inserted block to start at an entry boundary
(next non-blank line is a `## ` heading, or end of file). `--mode prefix` stays
the default and the permanent rule; a follow-up PR switches `verify.ps1` back to
it after PR #1 merges, with a test that a middle insertion fails.

## Blocker C: intermittent FileNotFoundError in the review-panel test (resolved)

`tests/test_review_ui.py` failed about one run in three with
`FileNotFoundError` on `repo/extractor.py`. The cause was in the test:
`qtbot.waitSignal()` returns a `SignalBlocker` and does not block unless it is
used as a context manager, so three bare calls waited for nothing and the test
polled the repository while `git merge --ff-only` was still running. `git`
unlinks each file before writing the merged version, and a poll can land in
that window.

Fixed by wrapping the action inside the wait
(`with qtbot.waitSignal(...): panel._apply_recorded_approval()`). The earlier
explanation - a shared pytest temp root - was wrong and is retracted; a unique
`--basetemp` did not prevent the failure. The test then passed 5 consecutive
runs and the full suite passed.

## CI gate and SonarCloud triage (PR #1, 2026-11-21/22)

`main` carried a rule that counted deleted lines in
`docs/ai_engineering_log.md` with `git diff --numstat`. It reported a deletion
whenever the base copy ended without a trailing newline, which `main`'s copy
did, so the gate failed on a file that had only gained lines. The rule is now
`scripts/check_log_append_only.py`: the content at HEAD must start with the
content at the base ref, byte for byte, after CRLF normalisation. It is
strictly stricter than the deletion count (it also catches a rewrite that keeps
the line count), and it is covered by 33 tests.

PR #1's branch inserted entries between the log header and the first
`2026-10-21` entry, so prefix mode cannot pass until the log is reordered, and
reordering is itself a rewrite of an append-only file. `--mode boundary` is a
documented, temporary exception (see above); `prefix` remains the default and
the follow-up PR switches `verify.ps1` back.

SonarCloud findings on the PR: 19 open bugs/vulnerabilities. All were triaged
before any code was changed.

| Rule | Count | Where | Verdict | Action |
| --- | --- | --- | --- | --- |
| `pythonsecurity:S8706` | 1 | `storage/database.py:198` | REAL: a path is not a connection string; a leading `file:` or a `?`/`#` changes how URI mode opens it | resolve and encode with `Path.as_uri()`, open with `uri=True`; tests for space, `#`, `%` and the escaping of `?` |
| `python:S6663` | 15 | `storage/history.py:434-443`, `storage/app_registry.py:172-176` | FALSE POSITIVE: the rows are `sqlite3.Row`, indexable by column name | mapped with `dict(row)` so the read is explicit; same behaviour |
| `pythonbugs:S2583` | 1 | `integrations/recorder.py:590` | REAL dead code: `_file_signer_windows()` is a stub returning `None`, so `if signer:` never ran | removed the branch and the two unused stubs; `executable_signer` stays `None` |
| `pythonsecurity:S8707` | 1 | `scripts/capture_ui_shots.py:38` | REAL: the screenshot folder came straight from `sys.argv` | `resolve_output_dir()` accepts only `shots/` or the temp folder; 6 tests |
| `pythonsecurity:S8705` | 1 | `scripts/check_log_append_only.py:179` | REAL: the base ref and path reached a git argument vector | object spec now goes to `git cat-file --batch` on stdin; ref/path validation kept as defence in depth |

After the fixes SonarCloud reported no open bug or vulnerability on the PR, and
both ratings on new code returned to A.

A separate intermittent failure in `tests/test_review_ui.py` was fixed in the
same PR: `qtbot.waitSignal()` does not block unless it is used as a context
manager, so the test polled the repository while `git merge --ff-only` was still
replacing `extractor.py`.

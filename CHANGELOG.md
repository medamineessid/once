# Changelog

All notable changes to Once. Dates are the day the work landed on this branch.

## 2026-11-18

### Design — one system on every screen

- Navy sidebar with the lemon Anton wordmark, a lemon active pill, and Phosphor
  24px icons at a 14px gap.
- Every page opens with a colour band: a real-count micro label, an Anton 72px
  title cropped by the band edge, and one guiding line.
- Home: clipped uppercase hero, a 128px lemon Record circle, an outlined Build
  button, three stat blocks with real numbers, and the real recent-runs list.
- My automations: each row owns Run / Open / Delete, shows a saved date and last
  status pill; unnamed drafts get a title derived from their first meaningful
  step; "Clear unnamed drafts" confirms first.
- Activity: compact band, one empty state with a 48px icon, and rows that carry
  duration and the first failure reason.
- Settings: section cards instead of group boxes.
- One button system (lemon fill, navy fill, outlined secondary, outlined red
  destructive); motion is 260ms per page transition and 220ms per dialog, and
  instant when Windows animations are off.
- Fixed while verifying: painted buttons repainted themselves inside
  `paintEvent` (Qt printed recursive-repaint errors), a band clipped its own
  guiding line, the sidebar focus ring looked like a second selected item, and
  clearing the automations list reported a stale "workflow not found".

### Reliability — the things that actually blocked a first run

- **Ctrl+Alt+Q now fires.** pynput's hotkey parser only matched keys it could
  name as characters, so on a layout without a `q` character it never triggered
  and a live probe recorded `triggered: false`. The switch tracks ctrl, alt and
  the Q virtual key itself.
- **A visible Stop button** in the footer while a run is live, cancelling
  whichever run is active (editor, home demo, or an automation row).
- **Close works on Windows 11 Notepad.** Notepad is a single-instance packaged
  app: the window belongs to a process the run did not start, and typing through
  the value pattern cannot be undone, so the close hit the app's own save prompt
  and timed out with the window still open. Close now owns a window by "new since
  launch + same image file name", answers a save prompt with "don't save" (never
  writing a file), and treats a window that vanished mid-close as closed.
- **Readable click failures:** "Could not find the 'Save' button in Notepad."
  instead of naming an internal element, and a retried step now waits 0.4s
  between attempts instead of repeating the same miss.
- **Run history** shows duration and the first failure reason, and each run can
  be repeated ("Run again") through the same approval gate as a normal run.
- **Run-time values:** `{name}` in a step is asked for at Run and substituted
  before approval; never saved.
- **Recorded drafts read as tasks:** window title changes no longer become
  steps, and launch/close steps are named "Open Notepad" / "Close Notepad".
- **Python 3.12 stays supported:** the formatter was targeting 3.14 and rewrote
  `except (A, B):` into 3.14-only syntax. Ruff now targets 3.12 and every
  affected clause is parenthesised again.

### Verification added

- `tests/test_design_v4.py` — 22 design-contract tests.
- `tests/test_run_controls.py` — Stop button and Run again routing.
- `tests/test_parameters.py` — `{name}` substitution and the asking dialog.
- `tests/test_app_starts.py` — the app opens and every page can be shown, plus
  an opt-in real-desktop Notepad test (`ONCE_REAL_DESKTOP=1`).
- `scripts/prove_notepad_flow.py` — real desktop: record → approve → run the
  Notepad task twice, with `Get-Process`-style evidence and leftover-window
  counts written to `shots/after/notepad-flow.json`.
- `scripts/shot_activity_runs.py` — Activity with real seeded runs.

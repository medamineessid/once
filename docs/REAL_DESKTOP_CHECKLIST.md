# Real desktop checklist — a person runs this, never the AI

Status: current
Last verified: 2026-11-26 · `main 603a326` — never run; this is the template, not a result
Owner: lane C (proof and delivery)

Nothing on this page has a `real desktop` evidence level until a person has run
it and written the result down. An AI agent may prepare this file and read the
code behind each step; it may not tick a box.

## Before you start

- Use your own Windows 11 PC, signed in as yourself, with a normal desktop.
- Build the app from an up-to-date `main`: `python app.py` in the project venv.
- Close every Notepad window, and leave no other app in front of Once.
- **Do not touch the mouse or keyboard while a run is going.** If a run goes
  wrong, press `Ctrl+Alt+Q` (the kill switch, `integrations/kill_switch.py:28`)
  and write down what you saw. That is a result, not a failure.
- Record every step in `docs/evidence/TEMPLATE.md`: date, machine, Windows
  build, display scaling, what you did, what happened, and the run id shown in
  **Activity**.

## 1. Record a task once — pattern path

1. **Home → Start with a recording → Start recording.**
2. Open Notepad, type `Hello Once`, leave the window open two seconds, then
   close it *without saving*, and press **Stop recording**.
3. **Expected:** the review screen names the application once and shows
   replayable launch, type and close steps; nothing is saved until you approve
   it. Write the count of replayable and observation-only steps.

## 2. Approve once, then run

1. Click **Approve to open it with Once (one-time)**, then **Approve draft and
   edit**.
2. In the editor press **Run** and approve the desktop action gate.
3. **Expected:** Notepad opens, the text appears, the window closes; Activity
   shows the run as **Succeeded** with per-step evidence. A save prompt is
   declined, never answered with a file write.

## 3. Forced mouse-centre fallback

Use a control that exposes no UI Automation `Invoke` pattern (a Windows 11
Settings toggle is the usual example), or record a click on a control whose
pattern is missing. Once then re-resolves the element, checks it is still there,
and clicks its bounding-box centre through `mouse_click`
(`integrations/windows_desktop.py:826`).

- **Expected:** the click lands on the control you recorded, not on a stale
  screen coordinate. If the element moved or vanished, the step fails with a
  plain message instead of clicking something else.
- **Also expected:** the click never goes to a different window that happens to
  be under that point.

## 4. Alt-Tab focus guard

Start a run that types into Notepad, then press **Alt-Tab** to another app while
it runs.

- **Expected:** Once refuses to type into a window that is not in front and
  reports a plain failure for that step; it does not type into the other app.
- This is a behaviour to confirm, not a promised one: the guard's exact wording
  comes from the run, so quote it verbatim in the evidence file.

## 5. 150% display scaling

Set **Settings → System → Display → Scale = 150%**, sign out and back in, and
repeat steps 1–3.

- **Expected:** icons stay sharp (the icon loader uses the device pixel ratio,
  `ui/components/phosphor_icons/__init__.py:5`), no label is clipped, the click
  still lands on the intended control, and the run still reports **Succeeded**.

## 6. Kill switch

Start a run and press `Ctrl+Alt+Q` without touching the Once window.

- **Expected:** the run stops with **Cancelled** in Activity, the footer **Stop**
  control disappears, and nothing is left half-done without a message.
- Then run it once more and let it finish: the hotkey must not fire when no run
  is live.

## 7. Nothing left behind

- **Expected:** no Notepad window is left open by Once, no file was written by a
  run that only typed, and `%LOCALAPPDATA%\Once\logs\once.log` exists with no
  traceback.

## Where the result goes

Fill `docs/evidence/TEMPLATE.md` (created by TASK-015). One file per run, one
sentence per step, plus the path of any capture. Then set the capability's
evidence level in `docs/STATE.md` to `real desktop` — only if every step above
was actually run.

## What this does not prove

- It does not prove the Chrome/browser path (A5) or the coding-agent loop.
- It does not prove smart replay: the flag is not wired into the app path yet
  (`ONCE_SMART_REPLAY` is read only in `engine/smart_replay.py`, grep
  2026-11-26), so a replay here uses the recorded steps as they are.

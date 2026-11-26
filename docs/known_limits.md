# Known limits

Status: current
Last verified: 2026-11-26 · `main f2e6ca3`
Owner: lane A (replay core)

Once only claims what a step can prove. This page lists what it cannot do today;
`docs/STATE.md` records what it can, with an evidence level.

## Platform

- **Windows 10/11 x64 only.** The desktop adapter is Windows UI Automation
  (`integrations/uia_adapter.py`, `integrations/windows_desktop.py`); nothing
  else exists.
- **The kill switch only works while a run is live.** `Ctrl+Alt+Q` is armed
  during a run (`integrations/kill_switch.py:28`) and does nothing otherwise.

## Typing and clicking

- **Typing becomes `TYPE_TEXT` only when the step names a window and a
  non-password text control.** Anything else — a password field, a control with
  no usable text pattern, free-form keystrokes — stays an observation in a
  recorded draft and is reported, never performed.
- **Clicks need one unique, enabled element.** Ambiguous matches are refused.
  When the control exposes no UI Automation pattern, the adapter re-resolves the
  element, re-checks it is still there, and clicks its bounding-box centre
  (`integrations/windows_desktop.py:826`); if it moved or vanished, the step
  fails instead of clicking the old coordinates. A coordinate-only click, with
  no element to verify, is not implemented.
- **Password fields are not automatable**, and neither is anything on the secure
  desktop (UAC prompts).

## Fragile surfaces

- **The Start menu and the taskbar are fragile.** Their windows belong to shell
  processes, their identity changes between sessions, and a recorded click can
  resolve to the wrong surface. Recording them is possible; replaying them is not
  reliable, and a failed step is the expected outcome.
- **Applications with poor accessibility information** (custom-drawn controls,
  DirectUI panels, some Electron apps) expose no stable element identity. Once
  refuses those steps rather than falling back to raw coordinates.
- **Windows 11 Store / single-instance apps** may hand a window to a broker
  process and exit the launcher, so `CLOSE_APPLICATION` can only close a window
  it can prove it owns; otherwise it leaves it open and says so.

## Smart replay

- The resolver, its policy layer and the UI Automation adapter are implemented
  and tested, but **the app path does not use them yet**: `ONCE_SMART_REPLAY` is
  read only in `engine/smart_replay.py` (grep, 2026-11-26). Recordings replay as
  recorded.
- No real-desktop run of the adapter's ask-or-stop behaviour has been recorded
  yet; `docs/REAL_DESKTOP_CHECKLIST.md` is the checklist that would produce one.

## Browser

- Isolated Chrome via DevTools only: Once launches its own profile, drives one
  page, and refuses when more than one page is open. Your ordinary browser
  session is never attached to.
- No downloads, uploads, alerts or dialogs, no free-form JavaScript, and the
  tab-selection case (A5) is not built.

## Files and history

- No permanent deletion and no silent overwrite anywhere in the app.
- Run history and approvals live in `%LOCALAPPDATA%\Once`; deleting that folder
  loses them, and nothing is synced.

## Evidence

- The only real-desktop proof in the repository is the Notepad launch/close flow
  and the kill switch (`shots/after/*.json`). Everything else is **tests only**
  or **not verified**.

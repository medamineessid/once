# Demo checklist

Status: current
Last verified: 2026-11-26 · `main f2e6ca3`
Owner: lane C (proof and delivery)

The finish line from `docs/PLAN.md`: **record once; change the screen (more tabs,
the wanted result lower in the list); replay finds the right thing or asks, and
never clicks wrong.** Rehearse the fallback too, because the smart-replay half is
not wired into the app path yet (`ONCE_SMART_REPLAY` is read only in
`engine/smart_replay.py`, grep 2026-11-26).

## Before you start

```powershell
.\.venv\Scripts\python.exe app.py
```

Close every Notepad window. Have a second browser window ready for the "change
the screen" beat. Do not touch the mouse or keyboard while a run is going; if it
goes wrong, press `Ctrl+Alt+Q`.

## The five-beat demo (about 6 minutes)

1. **Record once.** Home → **Record** → open Notepad, type `Hello Once`, open a
   menu, close *without saving* → **Stop recording**.
   *Say:* "Once captured the window, the control it typed into and the close, not
   screen coordinates."

2. **Review.** Point at the step list: replayable steps, observation-only steps,
   and the one-time application approval (path + SHA-256).
   *Say:* "Nothing runs until I approve this application and these actions."

3. **Change the screen.** Open two more Notepad windows, or move the window and
   resize it, so the target is no longer where it was recorded.

4. **Replay.** **Run** → approve the gate.
   *Say:* "It re-resolves the target instead of replaying a position." Watch for
   the honest outcome in Activity: `Succeeded`, `Partly performed`, or a failure
   whose first line is a plain reason.

5. **Never a wrong click.** If the target moved somewhere ambiguous, show that
   Once stops or asks rather than clicking the nearest thing — read the reason
   aloud from Activity.

Then show **Stop** and `Ctrl+Alt+Q` on a second run, and the persisted row in
Activity after a restart.

## Fallback script — smart replay not ready

If step 4 does not re-resolve (today's app path), do not fake it. Say what is
true and show the parts that do work:

1. Record and approve as in beats 1–2.
2. Run it with the window in place: **Succeeded**, evidence shows the control it
   typed into.
3. Then prove the honesty half: rename or close the target window first, run
   again, and show the step failing with "Could not find the … button in
   Notepad." — Once reports a miss instead of clicking something else.
4. Close with: "The resolver that turns this miss into a question is implemented
   and tested, and is not wired into the app yet; `docs/STATE.md` records it as
   tests only."

Never claim the smart-replay beat as demonstrated. If asked when, the answer is
A1 in `docs/PLAN.md`.

## What to have open

- Home, then My automations, then Activity.
- `docs/STATE.md` for the evidence levels, and `docs/UI_DEFECTS.md` if a UI
  defect is visible: name it as a known defect instead of apologising for it.

## After the demo

Write the run ids and any failure text into `docs/evidence/TEMPLATE.md`, and tell
the owner which claims are now **real desktop** instead of **tests only**.

# Once MVP Demo Checklist

Core framing: **"Once replays what it can verify and tells you honestly about the rest."**

## Pre-Demo Launch Command

From `C:\Users\DELL\once` in PowerShell:

```powershell
.\.venv\Scripts\python.exe app.py --shell
```

## 8-Step Live Demo Sequence

1. **Start a Recording**
   - On the **Home** page, click **Start with a recording** (or open **Create automation** and click **Record task**).
   - Once begins recording local window and input observations.
   - Open a classic Win32 desktop utility (recommended: `C:\Windows\System32\charmap.exe` — Character Map), wait 2 seconds so its top-level window is visible, then close it.
   - Click **Stop recording**.

2. **Review the Proposed Draft & Step Labels**
   - Once automatically transitions to **Review automation draft**.
   - Point out the application summary: `This task opens: charmap — C:\Windows\System32\charmap.exe`.
   - Point out the step list:
     - `LAUNCH_APPLICATION` and `CLOSE_APPLICATION` are labeled **`[Replayable: Once can replay this step.]`**.
     - Any mouse clicks, window switches, or key presses are labeled **`[Observation only: Recorded observation only — nothing is performed on replay.]`** with an info banner explaining that observation-only steps are shown but not performed.

3. **Approve the Application Once**
   - Try clicking or note that **Approve draft and edit** stays hidden until the application is approved.
   - Click **Approve to open it with Once (one-time)**.
   - Once records the executable path and its SHA-256 content hash in SQLite (`%LOCALAPPDATA%\Once\once.db`).

4. **Approve Draft & Save in the Visual Editor**
   - Click **Approve draft and edit**.
   - Once saves the approved workflow and opens it in the visual **Editor** canvas (`Start -> Launch -> Close -> Finish`).
   - Optionally click a step node on the canvas to inspect or edit its name/message in the right-hand inspector, or click **Save** to persist changes.

5. **Run the Automation Live**
   - Click **Run** in the Editor (and confirm desktop execution when prompted).
   - Watch `charmap.exe` actually launch on screen and then close automatically by its launched PID.

6. **Inspect Honest Run Outcomes**
   - If the workflow had only `LAUNCH_APPLICATION` and `CLOSE_APPLICATION`, the run finishes as **`Succeeded`**.
   - If the recording also included mouse clicks or focus switches (`REPORT` steps) alongside the launch/close steps, the run finishes as **`Partly performed`** (`Partly performed: 2 step(s) performed, N step(s) observation only`).
   - Open the **Activity** page from the left sidebar to show the persisted run record, timestamp, status chip, and per-step evidence (`process_id=...`, `sha256=...`, `windows_closed=1`, `exited=true`).

7. **Verify Unapproved / Modified App Refusal**
   - Run the CLI probe or attempt to run a workflow whose executable has not been approved:
     ```powershell
     .\.venv\Scripts\python.exe scripts\live_registry_probe.py --exe C:\Windows\System32\charmap.exe --db $env:TEMP\once-probe.db
     ```
   - Point out step `[1/4]` (`approval_needed=true`, `approval_reason=not_recorded`) and step `[4/4]` (`approval_reason=hash_mismatch`).

8. **Verify Persistence Across Restart**
   - Close the Once window and relaunch `.\.venv\Scripts\python.exe app.py --shell`.
   - Open **My Automations** and **Activity** to show that saved automations, one-time application approvals, and run history persist in SQLite across restarts.

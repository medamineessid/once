# Known Limits (MVP)

Once is designed around a strict honesty contract: **every step in a workflow is either deterministically replayable with postcondition verification, or explicitly labeled `Observation only` so a run never claims a success it did not perform.**

## What Recording + Replay Supports End-to-End Today

- **Opening an application (`WINDOW_OPEN` -> `LAUNCH_APPLICATION`):**
  - Captures the exact executable path (`executable_path`) and SHA-256 hash (`executable_sha256`) from the live Windows process.
  - Requires a one-time user approval stored in SQLite (`app_approvals` / `approved_applications`).
  - Launches directly with `subprocess.Popen(argv, shell=False)` after verifying the file exists and its SHA-256 matches the approved hash.
- **Closing an application launched in the same run (`WINDOW_CLOSE` -> `CLOSE_APPLICATION`):**
  - Emitted when the recording also captured opening that application.
  - Polls for visible, unowned top-level windows belonging to the exact PID launched by the current run and closes only those windows.
  - Reports `SUCCEEDED` only when the launched PID exits or has zero visible top-level windows remaining. Never touches pre-existing user windows.
- **Read-only path & file verification (`INSPECT_PATH`, `VERIFY_PATH_EXISTS`, `VERIFY_FILE_TEXT`):**
  - Verifies files inside an user-authorized folder and records `VERIFIED` with size/match evidence.

## What Stays Observation-Only in Recording Drafts

The following recorded events are captured in the recording timeline and converted into `REPORT` steps labeled **`Observation only`**:

- **Coordinate mouse clicks (`MOUSE_CLICK`):** Screen coordinates break when windows move or resize, so coordinate clicks are never replayed blindly.
- **Free-form typing (`TEXT_INPUT`) and raw key presses (`KEY_PRESS`):** Captured in the event log (with password fields redacted), converted to `REPORT` observations in recorded drafts.
- **Window focus switches (`WINDOW_FOCUS`) without a new process launch:** Recorded as `REPORT` observations.
- **Closing an application that the workflow did not launch:** Kept as a `REPORT` observation (`"Observed closing ..., which this workflow does not launch"`).
- **Observation-only save guard:** A workflow containing zero replayable steps cannot be saved as an executable automation (`WorkflowValidationError: This task has no steps Once can perform`).

## Run Status Honesty (`docs/contracts/run-outcomes.md`)

- **`SUCCEEDED` ("Succeeded"):** At least one step performed/verified real work, zero steps failed, and zero steps were `OBSERVED`.
- **`PARTIALLY_PERFORMED` ("Partly performed"):** At least one step performed/verified real work, at least one step was `OBSERVED` (`REPORT`), and zero steps failed.
- **`OBSERVATION_ONLY` ("Observation only — nothing was performed"):** Zero steps failed and no step performed or verified real work.
- **`FAILED` ("Failed"):** One or more steps failed or were refused (for example, missing approval or SHA-256 mismatch).

## Windows 11 Store / Single-Instance Apps

- Classic Win32 executables that own their top-level window (such as `C:\Windows\System32\charmap.exe`) work reliably with PID-tracked launch and close.
- Modern Windows 11 packaged/Store apps (such as `calc.exe` or multi-tab Windows 11 `notepad.exe`) may hand off window ownership to an existing broker process and exit the launcher PID immediately, or spawn replacement windows (such as Chrome). Where PID-owned window close cannot be verified, `CLOSE_APPLICATION` fails closed rather than claiming a false success.

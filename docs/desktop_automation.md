# Desktop Automation Engine

Implemented (2026-10-25) on branch `desktop-automation-engine`. This document
describes exactly what exists in code today; anything not listed here is not
implemented.

## Purpose and stance

Once can now run a small, closed set of Windows desktop interactions through
the same workflow engine, policy layer, and approval gates as every other
capability. Desktop actions are never reachable from a raw workflow file: a
workflow that mutates the desktop becomes runnable only through the explicit
approval gate described below. Inspection remains read-only.

## What exists where

| Layer | File | Role |
|---|---|---|
| Contracts | `engine/workflow.py` | New `StepKind` values, target validation, timeout bounds, `DesktopActions` adapter contract, `VERIFY_FILE_TEXT` reading |
| Policy | `engine/replay.py` | `READ_ONLY_POLICY`, `DESKTOP_INTERACTION_POLICY`, `MUTATING_DESKTOP_KINDS` |
| Approval | `engine/desktop.py` | `DesktopApproval`, `approve_desktop_workflow` — the only producer of approvals |
| Provider | `integrations/windows_desktop.py` | Real Windows actions via pywinauto UI Automation |
| Targeting | `integrations/uia_targeting.py` | Shared window/element matching (inspector and provider use the same code) |
| Controller | `controller/service.py` | `preview_desktop_replay`, `run_desktop_approved` (history persisted) |
| Live demo | `scripts/notepad_demo.py` | Real end-to-end Notepad scenario (manual run) |

## Step kinds

### Read-only (runnable without the desktop approval gate)

- `INSPECT_WINDOW`, `INSPECT_UI_ELEMENT` — pre-existing identity-based inspection, unchanged.
- `INSPECT_PATH`, `VERIFY_PATH_EXISTS` — pre-existing file inspection.
- `WAIT_WINDOW` — polls for exactly one matching top-level window within the
  step timeout; refuses ambiguous matches instead of choosing one.
- `VERIFY_FILE_TEXT` — new. Target JSON `{"path": ..., "contains": ...}` where
  `path` must be absolute, ≤ 260 chars, without `..`, resolve inside the
  authorized root of the run. Reads at most 65,536 bytes, refuses symlinks,
  and returns `VERIFIED` with `match=true` evidence or a structured `FAILED`
  with `match=false`. Postconditions are rejected on this kind (its own
  existence/content check suffices).

### Mutating (require a `DesktopApproval`)

- `LAUNCH_APPLICATION` — target JSON with exactly one of `application`
  (name from the registry; `notepad` currently) or `executable`
  (absolute `.exe` path, ≤ 260 chars, no `..`), plus optional bounded
  `arguments` (list of ≤ 16 non-empty strings, each ≤ 200 chars).
  Launching always passes an exact argv list with `shell=False`; a missing
  executable produces a structured failure without calling `Popen`.
- `CLICK_UI_ELEMENT` — invokes/toggles on one unique, enabled element via its
  UI Automation pattern. `interaction` is optional (`invoke` default) and must
  be one of `invoke`, `toggle`, `select`. Unsupported control-type/pattern
  combinations are refused rather than falling back to coordinates.
- `TYPE_TEXT` — sets text on one unique, enabled `Edit`/`Document` control
  through the Value pattern (no keyboard injection). Refuses password fields
  and non-text controls. Confirms success by reading the control back;
  mismatch is `FAILED` with `readback_confirmed=false`. Text ≤ 500 chars.
- `PRESS_SHORTCUT` — sends one allow-listed combination
  (`ctrl+s`, `ctrl+a`, `ctrl+c`, `ctrl+v`, `ctrl+x`, `ctrl+z`, `ctrl+y`,
  `enter`, `escape`, `tab`) to exactly one identified window. No free-form
  keyboard injection exists.

## Field evolution

`WorkflowStep.timeout_seconds` was added (default 30.0, bounds 0.5–60.0,
validated and persisted). Workflow storage schema is version 3; versions 1
and 2 still load and are upgraded on load.

## Target specification

Windows (identity object; at least one required):

- `title` (exact string), `process_id` (int ≥ 1), `class_name`, `automation_id`
  — all optional now, but an empty target set is invalid. When several
  top-level windows match, every action is refused with "ambiguous".

Elements (inside the resolved window):

- `automation_id` or `class_name` (at least one non-empty),
  `control_type` optional, no unknown fields. The launcher/inspector resolves
  descendants and refuses: not found, ambiguous, disabled, or a state that
  cannot be inspected. Notepad's editor has an empty `automation_id` and a
  stable `class_name` (`RichEditD2DPT`), which is why class_name is accepted.

Coordinate-based clicking is NOT implemented (no fallback exists to silently
click elsewhere).

## Permissions and approval flow

1. Build the `Workflow` (validated: known kinds, bounded fields, absolute
   paths, no `..`').
2. `ReplayExecutor().preview(workflow)` — the default (read-only) policy
   refuses all mutating desktop kinds; `preview_desktop_replay` previews under
   the desktop policy.
3. `approve_desktop_workflow(workflow)` — full validation + policy check;
   returns a frozen `DesktopApproval`.
4. `WorkflowService.run_desktop_approved(approval, allowed_root=...)` — raises
   immediately for anything that is not a real `DesktopApproval` or fails
   re-validation; only then runs steps, recording the run in the history
   database.

The approval type is constructible only in `engine.desktop`, and the runtime
re-checks the policy, so a hand-built look-alike fails closed.

## Failure behavior

Every expected refusal is a structured `StepResult` (`FAILED` or
`INCONCLUSIVE`) with plain-language messages and bounded evidence (target
identity, interaction, char counts, match flags). Unexpected provider
exceptions become `FAILED` — they are never swallowed. A failing step stops
the workflow deterministically; following steps are `SKIPPED` with the reason.
Cancellation between steps produces `CANCELLED` runs.

## Security restrictions

- No shell execution: launches use `Popen(argv, shell=False)` with an exact list.
- No keyboard or mouse injection without an identified target window/element.
- Password fields and OOB security dialogs (UAC/secure desktop) are not
  automatable; Value pattern + per-window targeting cannot reach them.
- Only the four mutating kinds above exist; there is no generic "do anything"
  action, no coordinate clicks, no window-move/close, no clipboard scraping.
- Concurrent timeouts: `timeout_seconds` bounds waits and launches indirectly
  (both stop within the workflow's step budget).

## Tests

Deterministic unit tests (fake provider, fake pywinauto surface; run
anywhere the suite runs):

- `tests/test_desktop_engine.py` — validation, policy, timeout bounds,
  text/face verification, cancellation, approval gate.
- `tests/test_windows_desktop.py` — provider behavior against a fake desktop.
- `tests/test_desktop_controller.py` — approval gating and history persistence.

Run: `C:\Users\DELL\once\.venv\Scripts\python.exe -m pytest tests\test_desktop_engine.py tests\test_windows_desktop.py tests\test_desktop_controller.py -q`

## Live Notepad demonstration (real desktop, run manually)

`scripts/notepad_demo.py` performs: launch Notepad on a fresh temp file
(validated step) → read-only discovery of the unique window (title contains
the demo file name) and the unique `Document` control → wait → type the demo
text with read-back confirmation → `Ctrl+S` to that window only (targeted by
process + class because the title changes when unsaved) → `VERIFY_FILE_TEXT`
reads the file and compares content exactly → closes only the demo window.

Last verified 2026-10-25 on the build machine: `RESULT: PASS - live desktop
round trip verified.` (launch SUCCEEDED, type `readback_confirmed=true`,
file content byte-exact, run SUCCEEDED).

## Windows-specific requirements

- pywinauto 0.6.9 with the UIA backend (already a project dependency).
- Modern (WinUI) Notepad: the editor is `class_name=RichEditD2DPT`,
  `control_type=Document`, no AutomationId; launched Notepad may be hosted in
  a shared process, so identity should not rely on the launcher's PID alone.

## Known limitations / not implemented

- No coordinate clicking at all; elements must be uniquely identifiable.
- Chrome tab/content automation is NOT implemented. The target format can be
  extended later (window identity + element identity already cover "Chrome
  window via class + tab by AutomationId/name"), but no browser dependency was
  added because Chrome's web content is often only partially exposed through
  UIA. Any Chrome work must reuse this interface, not add raw injection.
- Elevated/system windows and controls without UIA patterns fail closed with
  "does not support the ... pattern" rather than degrading to unsafe input.
- Workflow persistence of desktop workflows uses schema v3; the redesigned UI
  (other agent's scope) can call `preview_desktop_replay` /
  `approve_desktop_workflow` / `run_desktop_approved` — no UI code was changed.
- AI-generated proposals are still untrusted: they must pass the same
  validator and the same approval gate, unchanged from the safety invariants.

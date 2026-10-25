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
| Contracts | `engine/workflow.py` | New `StepKind` values, target validation, timeout bounds, `DesktopActions`/`BrowserActions` adapter contracts, `VERIFY_FILE_TEXT` reading |
| Policy | `engine/replay.py` | `READ_ONLY_POLICY`, `DESKTOP_INTERACTION_POLICY`, `MUTATING_DESKTOP_KINDS`, `BROWSER_READ_KINDS` |
| Approval | `engine/desktop.py` | `DesktopApproval`, `approve_desktop_workflow` — the only producer of approvals (covers browser mutations too) |
| Desktop provider | `integrations/windows_desktop.py` | Real Windows actions via pywinauto UI Automation |
| Targeting | `integrations/uia_targeting.py` | Shared window/element matching (inspector and provider use the same code) |
| Browser provider | `integrations/chrome_devtools.py` | Isolated-Chrome automation via the Chrome DevTools Protocol |
| WebSocket client | `integrations/devtools_ws.py` | Minimal stdlib RFC 6455 client for `ws://127.0.0.1` DevTools connections |
| Controller | `controller/service.py` | `preview_desktop_replay`, `run_desktop_approved` (history persisted; accepts `browser_actions`) |
| Live demo (desktop) | `scripts/notepad_demo.py` | Real end-to-end Notepad scenario (manual run) |
| Live demo (browser) | `scripts/chrome_demo.py` | Real end-to-end isolated-Chrome scenario (manual run) |

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
- `LAUNCH_BROWSER`, `NAVIGATE_BROWSER`, `INTERACT_PAGE_ELEMENT` (see the next
  section).

### Browser (isolated Chrome via the DevTools Protocol)

The browser surface automates only a Chrome instance that the engine itself
launched with an isolated temporary profile. It never attaches to the user's
ordinary session; targets are `{"browser": {"cdp_port": <int 1024–65535>}}`
and any port not registered by a previous `LAUNCH_BROWSER` step in the same
run is refused.

Mutating kinds (require a `DesktopApproval`):

- `LAUNCH_BROWSER` — target JSON with exactly one of `application`
  (`chrome` from the registry) or `executable` (absolute `chrome.exe` path,
  no `..`), plus optional `headed` (bool, default false = `--headless=new`).
  Chrome is started with `--remote-debugging-port=0 --user-data-dir=<isolated
  temp profile> --no-first-run --no-default-browser-check shell=False; the
  engine reads the `DevTools listening on ws://127.0.0.1:PORT` line from
  stderr, verifies `/json/version` reports `Chrome`, waits for the first
  page, and removes the process + profile again if any of that fails.
  Evidence records `cdp_port`, `process_id`, browser version — never pages,
  cookies, or profile contents.
- `NAVIGATE_BROWSER` — target `{"browser", "url"}`. The URL must be `http` or
  `https`, ≤ 2048 chars, whitespace-/control-free, with a host and without
  `user[:password]` userinfo. Navigation uses `Page.navigate`, waits bounded
  for `readyState == "complete"`, and reports the final URL as evidence.
- `INTERACT_PAGE_ELEMENT` — target `{"browser", "selector", "interaction"}` with
  `interaction` `click` or `type` (+ `text` ≤ 500 chars for `type`). The
  selector must match exactly one element (0 or >1 is a structured refusal).
  `click` dispatches a single `.click()` on the element. `type` writes the
  value through the element's native property setter, fires `input`/`change`,
  and confirms by reading the value back (`readback_confirmed`). Password
  fields and non-editable elements are refused; the typed text is never
  written to evidence, only its character count.

Read-only kinds (allowed under `BROWSER_READ_KINDS`, no mutation approval, but
still subject to policy validation):

- `INSPECT_PAGE` — target `{"browser", "include_text"?}`. Records the current
  title and URL; with `include_text` it reads `document.body.innerText`
  bounded at 20,000 chars and records length, truncation flag, and a 200-char
  prefix as evidence.
- `FIND_PAGE_ELEMENT` — target `{"browser", "selector"}`. Returns the unique
  match's tag, disabled flag, and bounded text; ambiguity and absence fail.
  Selectors are ≤ 256 chars and must not embed a `javascript:`/`data:`/
  `file:`/`vbscript:` scheme.
- `WAIT_PAGE` — target `{"browser", "conditions"}` with at least one of
  `title` (exact), `url` (`http(s)` or `about:blank`), `text` (substring of
  bounded page text). The step polls until all conditions hold or its
  `timeout_seconds` elapses, and reports the first unmet condition as the
  failure reason. (`selector` is accepted by the schema today but reported as
  unsupported by the provider rather than silently ignored.)

Engineering constraints:

- No arbitrary JavaScript execution: every in-page command is a fixed,
  engine-owned expression; workflow data enters only as JSON-string-literal
  arguments to those expressions.
- All DevTools communication is over `ws://127.0.0.1:<port>` and
  `http://127.0.0.1:<port>` only; the WebSocket client is a minimal stdlib
  RFC 6455 implementation (`integrations/devtools_ws.py`) with a 10 MiB
  frame-size bound and refusal of server-masked or non-text frames. It
  answers server ping frames with a pong carrying the same payload
  (RFC 6455 section 5.5.2).
- Exactly one page at a time: more than one open page in the isolated browser
  refuses ("More than one page is open ... refused instead of choosing a
  tab"), so tab switching can never happen silently.
- Postconditions are rejected on all browser kinds (and `VERIFY_FILE_TEXT`).
- Lifetime: through `WorkflowService.run_desktop_approved`, every
  engine-launched browser is closed and its temporary profile removed when the
  run finishes, fails, or is cancelled (`keep_browsers_after_run=True` may
  preserve a launch-only run's browser for the one later run that consumes
  its DevTools port; that run closes it when it finishes). Normal app exit is
  covered by an exit hook on the service's browser provider. A hard app crash
  leaves the browser and its `once-chrome-profile-*` temp profile behind
  until Windows cleans the temp area — intentionally not yet implemented.

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

Browser deterministic tests (fake DevTools surface; no Chrome involved):

- `tests/test_browser_engine.py` — URL/port/selector/conditions validation,
  provider dispatch, missing provider = INCONCLUSIVE, failure stops the run,
  read-only vs mutating policy, approval gate covers browser mutations,
  cancellation before a pending browser step, postcondition refusal, no
  typed text in results.
- `tests/test_chrome_devtools.py` — provider behavior against fake HTTP/WS:
  navigate load state + errorText refusal + timeouts, bounded inspect text,
  ambiguity/uniqueness for find/interact, password refusal, readback
  confirmation, wait conditions + timeout reasons, unknown port, dead
  browser, ambiguous/missing pages, non-Chrome endpoint refusal, launch
  success/fail-closed, shutdown cleanup.

Run: `C:\Users\DELL\once\.venv\Scripts\python.exe -m pytest tests\test_browser_engine.py tests\test_chrome_devtools.py -q`

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

## Live isolated-Chrome demonstration (real Chrome, run manually)

`scripts/chrome_demo.py` performs: serve a static demo page from a temp
directory on 127.0.0.1 (random port) → `LAUNCH_BROWSER` (application=chrome)
through `approve_desktop_workflow` → `NAVIGATE_BROWSER` to the local page →
`WAIT_PAGE` for the title → `INSPECT_PAGE` (bounded text) →
`FIND_PAGE_ELEMENT` for `#demo-button` → `INTERACT_PAGE_ELEMENT` click and
type → `WAIT_PAGE` for the click effect text → `FIND_PAGE_ELEMENT` verify of
the status element → the provider's `shutdown()` closes the browser and
removes the temp profile.

The user's Chrome profile is never used; the page is localhost-only. Run:

    C:\Users\DELL\once\.venv\Scripts\python.exe scripts\chrome_demo.py

Last verified 2026-10-25: `RESULT: PASS - live isolated-browser round trip
verified.` (all eight steps SUCCEEDED; Chrome/155.0.8059.86, isolated
profile; navigate reported `readyState=complete`, type `readback_confirmed=true`,
status element text `button was clicked`).

## Windows-specific requirements

- pywinauto 0.6.9 with the UIA backend (already a project dependency).
- Modern (WinUI) Notepad: the editor is `class_name=RichEditD2DPT`,
  `control_type=Document`, no AutomationId; launched Notepad may be hosted in
  a shared process, so identity should not rely on the launcher's PID alone.

## Known limitations / not implemented

- No coordinate clicking at all; elements must be uniquely identifiable.
- Browser automation covers Chrome only, launched isolated by Once. The
  user's ordinary Chrome profile/session, Edge, Firefox, and other browsers
  are out of scope; attaching to an already-running browser is deliberately
  impossible (targets must reference a `cdp_port` registered by
  `LAUNCH_BROWSER` in the same run).
- DevTools supports headless Chrome well; the `headed` option is validated
  but untested against the visible UI — treat headless as the supported mode.
- No downloads/uploads, no dialogs/alerts automation, no cookie/storage
  access, no JavaScript execution beyond the fixed engine expressions, no
  cross-origin iframes beyond the top frame.
- DevTools browser sessions do not survive a finished/failed/cancelled
  approved run through the controller; a workflow cannot drive a browser step
  in one run against a browser launched by an earlier service run unless the
  launch run explicitly kept it open.
- Elevated/system windows and controls without UIA patterns fail closed with
  "does not support the ... pattern" rather than degrading to unsafe input.
- Workflow persistence of desktop workflows uses schema v3; the redesigned UI
  (other agent's scope) can call `preview_desktop_replay` /
  `approve_desktop_workflow` / `run_desktop_approved` — no UI code was changed.
- AI-generated proposals are still untrusted: they must pass the same
  validator and the same approval gate, unchanged from the safety invariants.

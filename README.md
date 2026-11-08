# Once — Local-First Supervised Desktop Automation & Orchestration

**Show Once a task once—or build it visually—review every step in plain English, approve what touches your desktop, and let a deterministic engine handle the rest.**

Once is a local-first Windows desktop application built with Python and **PySide6 (Qt Widgets)** for recording, building, verifying, and replaying bounded desktop, browser, and file-verification workflows. Instead of fragile coordinate clicking or opaque AI scripts, Once pairs **semantic Windows UI Automation (UIA)** with a strict, human-approved execution engine. Every action is inspectable, every application launch is bound to its cryptographic SHA-256 identity, and nothing mutates your machine without your explicit permission.

---

## What Works Today (Current Capabilities)

Once brings together a high-contrast, Linear/Raycast-inspired native desktop interface (`ui/`, documented in [`DESIGN.md`](DESIGN.md)) and a rock-solid, policy-gated execution engine (`engine/`, `controller/`, `integrations/`):

### 1. Semantic Task Recording & AI-Assisted Drafts (`Start with a recording`)
- **Beyond `(x, y)` Coordinates:** Captures window launches, window closes, UIA control clicks (`Button`, `MenuItem`, `CheckBox`, `RadioButton`, `ListItem`, `TabItem`, `Hyperlink`), text entry (`Edit`, `Document`, `ComboBox`), and keyboard shortcuts locally while automatically redacting password fields.
- **Deterministic Offline + Optional Gemini Cloud Analysis:** Turns your recorded task into a structured workflow draft (`LAUNCH_APPLICATION`, `CLICK_UI_ELEMENT`, `TYPE_TEXT`, `PRESS_SHORTCUT`, `CLOSE_APPLICATION`). Works 100% offline out of the box, and seamlessly upgrades to cloud Gemini analysis when a `GEMINI_API_KEY` or Windows Credential Manager entry is configured—automatically keeping whichever draft produces more replayable steps.
- **Transparent Review Screen:** Labels every proposed step as **`Replayable`** or **`Observation only`** with a clear explanation, and requires a one-time application identity approval (executable path + SHA-256 hash) before saving.

### 2. Visual Workflow Editor (`Build it yourself`)
- **Interactive Node Canvas & Minimap:** Visualizes your workflow chain (`Start -> Steps -> Finish`) with semantic status badges (`RUNNING`, `SUCCEEDED`, `VERIFIED`, `OBSERVED`, `FAILED`), zoom/pan controls, and persistent node layouts in SQLite.
- **Synchronized Step List & Guided Inspector:** Click any step on the canvas or in the step list to edit its `Kind`, `Name`, `Message`, `Target`, `Attempts`, `Timeout`, or `Postcondition`. Changing a step's `Kind` automatically populates a valid target template so you never have to guess JSON syntax.
- **Full Undo / Redo & Live Execution:** Edit with confidence (`Ctrl+Z` / `Ctrl+Y` / `Ctrl+S`), delete steps, and run saved automations directly from the editor with real-time per-node progress and evidence inspection.

### 3. Resilient Windows 11 Desktop & Browser Replay
- **Cryptographic Application Registry (`once.db`):** Launches only executables you have explicitly approved and verifies their SHA-256 digest before every run. `CLOSE_APPLICATION` closes only the process ID (PID) started by that specific run, never touching your other open windows.
- **Real-World Windows 11 UIA Tolerance:** Automatically waits up to 5 seconds for newly launched windows to appear, tolerates dirty-indicator title prefixes (such as `*Untitled - Notepad`), and falls back to focused keyboard entry when modern WinUI/DirectUI controls do not expose `ValuePattern`.
- **Isolated Chrome DevTools Automation:** Supports bounded browser steps (`LAUNCH_BROWSER`, `NAVIGATE_BROWSER`, `INSPECT_PAGE`, `FIND_PAGE_ELEMENT`, `INTERACT_PAGE_ELEMENT`, `WAIT_PAGE`) inside disposable temporary profiles that clean up automatically when the run finishes.

### 4. Supervised Test-and-Fix Orchestrator & Verifier
- **Allowlisted Headless Verifier:** Runs synthetic invoice acceptance cases against allowlisted local commands, compares per-field JSON outputs, and packages redacted evidence bundles (`engine/verifier.py`).
- **Isolated Git Worktree Verification:** Reviews coding-agent proposals on separate branches, verifies exact commit tips inside disposable Git worktrees (`verify_proposal_pre_merge`), and requires explicit human approval before fast-forwarding.

---

## Honest Run Outcomes

Every run reports an accurate, plain-language outcome (`docs/contracts/run-outcomes.md`) persisted to SQLite (`Activity` & `Home`):

- **`Succeeded` (`SUCCEEDED`):** Every step performed or verified real work.
- **`Partly performed` (`PARTIALLY_PERFORMED`):** At least one step performed real work and at least one step was `Observation only` (`REPORT`).
- **`Observation only — nothing was performed` (`OBSERVATION_ONLY`):** The workflow contained only observation notes.
- **`Failed` (`FAILED`):** A step failed, timed out, or was refused by a safety gate (such as an unapproved executable or SHA-256 mismatch).
- **`Cancelled` (`CANCELLED`):** Cooperatively stopped by the user before completion.

---

## Quick Start

### Requirements
- Windows 10 or 11 (x64)
- Python 3.14 (verified on Python 3.14.3)

### Setup

From the repository root (`c:\Users\DELL\once`) in PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

### Launch Once

 Both commands below launch the modern **Once desktop shell** (`ui/shell.py`):

```powershell
.\.venv\Scripts\python.exe app.py
# or explicitly:
.\.venv\Scripts\python.exe app.py --shell
```

*(Need the legacy diagnostic window? Run `.\.venv\Scripts\python.exe app.py --legacy`.)*

---

## Try It Out: Recommended Scenarios

1. **Record & Replay a Live Desktop Task:**
   - Open Once, click **Start with a recording** on the Home screen, and click **Start recording**.
   - Launch a desktop app, click buttons or type into an input field, close the app, and click **Stop recording**.
   - On the **Review recorded draft** screen, click **Approve to open it with Once (one-time)**, then **Approve draft and edit**.
   - Inspect your generated steps on the visual canvas, click **Run automation**, approve the desktop action gate, and watch Once replay the task end-to-end.
2. **Build a Custom Automation Visually:**
   - Click **Build an automation** on Home.
   - Click **Add step**, select the step on the canvas or list, choose a `Kind` in the right-hand Inspector (e.g., `LAUNCH_APPLICATION`, `TYPE_TEXT`, `VERIFY_PATH_EXISTS`), customize the target, click **Apply changes**, **Save automation**, and **Run automation**.
3. **Run the Supervised Test-and-Fix Demo (`scripts/run_demo.py`):**
   ```powershell
   echo approve | .\.venv\Scripts\python.exe scripts\run_demo.py
   ```
4. **Probe the Live SQLite Application Registry:**
   ```powershell
   .\.venv\Scripts\python.exe scripts\live_registry_probe.py --exe C:\Windows\System32\notepad.exe --db $env:TEMP\once-probe.db
   ```

---

## Verification, Testing & Packaging

### Run the Test Suite & Linter

```powershell
.\.venv\Scripts\ruff.exe format .
.\.venv\Scripts\ruff.exe check .
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m pytest -q
```

### Headless UI Smoke Test

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe app.py --smoke-test
$LASTEXITCODE   # expect 0
```

### Package a Standalone Windows Build (`dist\Once\Once.exe`)

```powershell
.\.venv\Scripts\python.exe -m PyInstaller once.spec --noconfirm --clean
.\dist\Once\Once.exe --smoke-test   # expect exit code 0
```

All user data (SQLite history, approved application hashes, saved workflows, recordings, and rotating logs) lives cleanly under `%LOCALAPPDATA%\Once` and is never written next to the executable.

---

## Documentation Map

- [`DESIGN.md`](DESIGN.md) — Native Qt design system, color tokens, typography scale, and canvas/inspector anatomy.
- [`AGENTS.md`](AGENTS.md) — Architecture boundaries, non-negotiable safety invariants (`S1–S12`, `O1–O8`), and engineering rules.
- [`docs/demo_checklist.md`](docs/demo_checklist.md) — Step-by-step MVP walkthrough checklist.
- [`docs/known_limits.md`](docs/known_limits.md) — Honest scope boundaries and safety constraints.
- [`docs/decisions.md`](docs/decisions.md) — Architectural and dependency decision records (`PySide6 6.12.0`, `send2trash 2.1.0`, `pytest 9.1.1`, `Ruff 0.17.1`).
- [`docs/ai_engineering_log.md`](docs/ai_engineering_log.md) — Chronological engineering and verification log.

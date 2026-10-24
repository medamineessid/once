# Once

Once is a local Windows desktop application for building and running bounded,
observable workflows. It will eventually coordinate file operations, desktop
applications, browser interfaces, logs, tests, and coding tools through
explicit integrations. The deterministic engine controls execution; no
unrestricted scripts or opaque AI actions are used.

**Current status: supervised orchestration foundation, persistence, history,
headless verifier with redacted evidence, pre-merge verification in disposable
Git worktrees, local recording with AI-assisted draft review, offline proposal
review, explicit approval, and read-only Windows inspection.**
The application can validate and save/reopen versioned declarative workflows,
run bounded local steps with success, failure, skipped-step, cancellation, and
authorized path-verification states, and record real controller-triggered runs
and evidence in SQLite. It can also record local observations, redact
password-field input, review recordings, run deterministic offline analysis,
preview a proposal, and require explicit approval before saving and executing
it. Live Gemini analysis and input replay remain opt-in or unimplemented.

## Requirements

- Windows 10 or 11, x64
- Python 3.14 (verified: 3.14.3)

## Setup

From the repository root in PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## Run the application

```powershell
.\.venv\Scripts\python.exe app.py
```

## Smoke-test the application

The smoke test builds the real `QApplication` and `MainWindow`, processes
pending Qt events and exits with status 0 without waiting for a window to be
closed. It works headlessly:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe app.py --smoke-test
$LASTEXITCODE   # expect 0
```

## Package a Windows build

`once.spec` bundles the application into `dist\Once\Once.exe` (a one-folder
build; user data stays in `%LOCALAPPDATA%\Once` and is never written next to
the exe):

```powershell
.\.venv\Scripts\python.exe -m PyInstaller once.spec --noconfirm --clean
.\dist\Once\Once.exe --smoke-test   # expect exit code 0
```

The spec lists `pynput`, `mss`, `pywinauto`, `win32api`, and `win32cred` as
hidden imports because those modules are imported lazily. A packaged app logs
to `%LOCALAPPDATA%\Once\logs\once.log`; a corrupted `verifier.json` keeps the
app startable (the reviewer tab explains the problem), and an unusable data
folder is reported with a plain-language dialog.

## Install, first run, upgrade, and uninstall (packaged app)

A user without this repository only needs the built folder: copy the whole
`dist\Once` folder (the exe plus its runtime files) to any writable location,
for example `C:\Tools\Once`, and double-click `Once.exe`. No Python is needed.
All user data lives under `%LOCALAPPDATA%\Once` (database, workflows, configs,
recordings, logs) and is never written next to the exe.

First run: the Workflows tab starts with a demo workflow, and the Agent
proposals panel has a "Configure acceptance checks" button to create
`verifier.json`. Acceptance checks run entirely offline with programs the user
explicitly allowlists. Two capabilities need named authorization by design:
cloud analysis of a recording (Gemini, opt-in, requires a credential the user
enters) and a coding-agent run (the agent itself is an external tool Once
launches only on the user's explicit request). Everything else, including
verification, evidence redaction, and proposal review, works offline.

Upgrade: quit Once, replace the old `Once` folder with a newly built one, and
start it again. Old databases open with additive column defaults; existing
workflows, history, recordings, and configuration are preserved. If the
replace is done while Once runs, changed runtime files may be in use — quit
the app first.

Uninstall: delete the `Once` application folder. Once never deletes
`%LOCALAPPDATA%\Once` by itself: workflows, history, recordings, and
configuration survive an uninstall unless the user deliberately deletes that
data folder as a separate step (consider backing it up first).

## Tests and linting

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
```

Tests use only pytest's `tmp_path`; they never read or modify real user folders.
The Qt tests run offscreen (`QT_QPA_PLATFORM=offscreen`).

## Architecture

```
app.py                 entry point: builds QApplication and MainWindow
ui/                    PySide6 widgets only; no file-system mutation
controller/            Qt-free services connecting UI to engine
engine/                Qt-free workflow orchestration and integrations
storage/               local SQLite/JSON persistence (later milestone)
tests/                 pytest tests, including architecture guards
docs/                  decisions and AI engineering log
```

Dependency direction: `ui -> controller -> (engine, storage)`. The architecture
tests enforce:

- `engine/` never imports PySide6, `ui/`, `controller/` or `storage/`.
- `ui/` never calls file-system mutation functions such as `os.rename`,
  `shutil.move` or `Path.unlink`.

## Dependency pins

Runtime (`requirements.txt`): PySide6 6.12.0, send2trash 2.1.0.

Development (`requirements-dev.txt`): pytest 9.1.1, pytest-cov 7.1.0,
pytest-qt 4.5.0, Ruff 0.17.1, PyInstaller 6.22.3.

Version and compatibility evidence is recorded in `docs/decisions.md`.

## Reproducible demonstration

`scripts/run_demo.py` walks the complete supervised journey end to end inside
one throwaway directory: a miniature invoice-extractor repo with a seeded
defect, synthetic inputs with recorded ground truth (INV-1 total 105.0), an
allowlisted verifier that proves the defect, a deterministic rule-based fix
generator standing in for a coding agent, the exact proposed diff, isolated
worktree verification, an explicit type-to-approve gate, the apply, a passing
post-merge rerun, and a restart that shows the persisted APPROVED decision,
both verification phases, and every recorded verification run.

```powershell
echo approve | .\.venv\Scripts\python.exe scripts\run_demo.py   # approve path
echo no      | .\.venv\Scripts\python.exe scripts\run_demo.py   # cancel path
```

No network, no cloud providers, no real invoices; the printed fix is applied
only after you type `approve`.

## Further documentation

- `AGENTS.md` — authoritative specification, safety invariants and decisions.
- `docs/decisions.md` — evidence-backed decision log.
- `docs/ai_engineering_log.md` — append-only implementation log.

## Local recording and proposal demo

Run the application, click **Record**, perform a short task, and click **Stop
recording**. Select the saved recording, inspect its event timeline, then click
**Analyze selected recording (offline)**. Answer the bounded question, review
the proposed workflow, and click **Approve and save proposal**. The saved
workflow can then be selected and run through the normal deterministic engine.

The offline demo does not send recording data over the network. Gemini remains
disabled unless a caller explicitly enables it and supplies a credential.

Replay currently supports read-only path checks and exact-identity Windows UI
Automation window inspection. Window targets include a title and may include a
process ID, class name, or automation ID. Ambiguous or missing windows fail
closed; Once never falls back to the active window and does not replay clicks,
keystrokes, or text input.

It also supports read-only UI element inspection when a target contains both
an exact parent-window identity and a stable `AutomationId` plus `ControlType`.
The element must be unique within that window. Inspection records only
non-sensitive metadata such as control type, class name, and enabled state; it
does not read control text.

The product direction is now a supervised test-and-fix orchestrator. See
[docs/product_vision.md](docs/product_vision.md) for the six-step flow and the
Hotix invoice-extractor target. The first verifier uses synthetic acceptance
cases; it does not call a coding agent, mutate desktop applications, or claim
invoice accuracy without ground truth.

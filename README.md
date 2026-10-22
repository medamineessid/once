# Once

Once is a local Windows desktop application for building and running bounded,
observable workflows. It will eventually coordinate file operations, desktop
applications, browser interfaces, logs, tests, and coding tools through
explicit integrations. The deterministic engine controls execution; no
unrestricted scripts or opaque AI actions are used.

**Current status: workflow foundation, persistence, history, GUI, local
recording, offline proposal review, and explicit approval milestones.**
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

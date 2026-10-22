# Once

Once is a local Windows desktop application that will let non-technical users
automate repetitive file-management tasks (bulk rename, organise, copy, move)
with a preview-and-approve workflow. The deterministic Python engine — never an
AI model — performs every file operation. Once works offline and sends no
telemetry.

**Current status: Step 1 skeleton only.** The application opens a placeholder
window. Scanning, planning, execution, history and undo are not implemented
yet. Do not use this build to manage real files.

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
controller/            Qt-free application services (added in later steps)
engine/                Qt-free domain logic; only executor/recovery may mutate files
storage/               local SQLite/JSON persistence (later steps)
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
pytest-qt 4.5.0, Ruff 0.17.1. PyInstaller is deferred to the packaging step.

Version and compatibility evidence is recorded in `docs/decisions.md`.

## Further documentation

- `AGENTS.md` — authoritative specification, safety invariants and decisions.
- `docs/decisions.md` — evidence-backed decision log.
- `docs/ai_engineering_log.md` — append-only implementation log.

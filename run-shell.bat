@echo off
rem Launch the redesigned Once application shell (the new UI).
rem Double-click this file, or run it from PowerShell 5.1 with: .\run-shell.bat
cd /d "%~dp0"
".venv\Scripts\python.exe" app.py --shell
if errorlevel 1 (
  echo.
  echo Once could not start. If the ".venv" folder is missing, install the
  echo dependencies first:
  echo     .venv\Scripts\python.exe -m pip install -r requirements.txt
  echo.
  pause
)

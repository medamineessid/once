# Capture shell screenshots at three window sizes (session prompt P1.6).
#
# Runs the real shell through scripts/capture_shell_pages.py (same construction
# path app.py uses for --shell) with QT_QPA_PLATFORM=offscreen, captures every
# reachable page at 1280x800, 1366x768 and 1920x1080 into docs/screenshots/latest/
# with stable file names, verifies every file is non-empty and that no two files
# are identical (md5), then prints the paths.
#
# Compatible with Windows PowerShell 5.1.

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)

$venvPython = ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) { throw "virtual environment not found: $venvPython" }
$outDir = "docs\screenshots\latest"

$env:QT_QPA_PLATFORM = "offscreen"
& $venvPython "scripts\capture_shell_pages.py" $outDir
if ($LASTEXITCODE -ne 0) { throw "capture driver failed with exit code $LASTEXITCODE" }

$files = Get-ChildItem -LiteralPath $outDir -Filter "*.png" |
    Where-Object { $_.Name -match '^(1280x800|1366x768|1920x1080)-' }

if ($files.Count -ne 18) { throw "expected 18 captures (6 pages x 3 sizes), found $($files.Count)" }

foreach ($file in $files) {
    if ($file.Length -le 0) { throw "empty capture: $($file.FullName)" }
}

$hashGroups = ($files | ForEach-Object { (Get-FileHash -LiteralPath $_.FullName -Algorithm MD5).Hash }) |
    Group-Object | Where-Object { $_.Count -gt 1 }
foreach ($group in $hashGroups) { throw "identical capture found ($($group.Count) files share md5 $($group.Name))" }

Write-Output "Captures (all distinct, non-empty):"
foreach ($file in $files) { Write-Output $file.FullName }

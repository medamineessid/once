# Local verification for the Once project.
# Real PowerShell (compatible with Windows PowerShell 5.1). ASCII output only.
# Run from anywhere: it relocates itself to the repository root.

$ErrorActionPreference = 'Continue'

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location -LiteralPath $root

$Python   = Join-Path $root '.venv\Scripts\python.exe'
$RuffExe  = Join-Path $root '.venv\Scripts\ruff.exe'

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Output "FAIL: Virtual environment not found at $Python"
    Write-Output "Create it first (py -3.14 -m venv .venv), then: pip install -r requirements-dev.txt"
    exit 1
}
if (-not (Test-Path -LiteralPath $RuffExe)) {
    Write-Output "FAIL: ruff.exe not found at $RuffExe"
    Write-Output "Install the dev requirements: pip install -r requirements-dev.txt"
    exit 1
}

$env:QT_QPA_PLATFORM = 'offscreen'

$script:Results = @()
$script:RealChecksFailed = $false

function Invoke-Check {
    param(
        [string]$Name,
        [scriptblock]$Command,
        [switch]$Informational
    )
    Write-Output "=== $Name ==="
    & $Command
    $code = $LASTEXITCODE
    if ($code -eq 0) {
        Write-Output "PASS: $Name"
    } else {
        Write-Output "FAIL: $Name (exit code $code)"
        if (-not $Informational) {
            $script:RealChecksFailed = $true
        }
    }
    $row = [ordered]@{
        Check      = $Name
        ExitCode   = $code
        Result     = ''
        Severity   = ''
    }
    if ($code -eq 0) {
        $row.Result = 'PASS'
    } else {
        $row.Result = 'FAIL'
    }
    if ($Informational) {
        $row.Severity = 'informational'
    } else {
        $row.Severity = 'required'
    }
    $script:Results += [pscustomobject]$row
}

Invoke-Check -Name 'git branch --show-current' -Informational -Command { git branch --show-current }
Invoke-Check -Name 'git status --short'        -Informational -Command { git status --short }
Invoke-Check -Name 'pytest -q'                 -Command { & $Python -m pytest -q }
Invoke-Check -Name 'ruff check .'              -Command { & $RuffExe check . }
Invoke-Check -Name 'ruff format --check .'     -Command { & $RuffExe format --check . }
Invoke-Check -Name 'app.py --smoke-test'       -Command { & $Python app.py --smoke-test }
Invoke-Check -Name 'app.py --smoke-test --shell' -Command { & $Python app.py --smoke-test --shell }
Invoke-Check -Name 'git log -1 --numstat'      -Informational -Command { git log -1 --numstat }

Write-Output ''
Write-Output '=== SUMMARY ==='
$script:Results | ForEach-Object {
    '{0,-32} exit={1,-4} {2,-5} ({3})' -f $_.Check, $_.ExitCode, $_.Result, $_.Severity
}
if ($script:RealChecksFailed) {
    Write-Output 'SOME CHECKS FAILED'
    exit 1
}
Write-Output 'ALL CHECKS PASSED'
exit 0

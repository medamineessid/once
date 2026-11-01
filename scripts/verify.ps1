# Local verification for the Once project.
# Real PowerShell (compatible with Windows PowerShell 5.1). ASCII output only.
# Run from anywhere: it relocates itself to the repository root.

$ErrorActionPreference = 'Continue'

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location -LiteralPath $root

$defaultVenvPython = Join-Path $root '.venv\Scripts\python.exe'
$defaultVenvRuff   = Join-Path $root '.venv\Scripts\ruff.exe'

$Python = $null
if (Test-Path -LiteralPath $defaultVenvPython) {
    $Python = $defaultVenvPython
} elseif ($env:VIRTUAL_ENV -and (Test-Path -LiteralPath (Join-Path $env:VIRTUAL_ENV 'Scripts\python.exe'))) {
    $Python = Join-Path $env:VIRTUAL_ENV 'Scripts\python.exe'
} elseif (Get-Command python.exe -ErrorAction SilentlyContinue) {
    $Python = (Get-Command python.exe).Source
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $Python = (Get-Command python).Source
}

if (-not $Python) {
    Write-Output "FAIL: Virtual environment or Python executable not found"
    Write-Output "Create it first (py -3.14 -m venv .venv), then: pip install -r requirements-dev.txt"
    exit 1
}

$RuffExe = $null
$UseRuffModule = $false
if (Test-Path -LiteralPath $defaultVenvRuff) {
    $RuffExe = $defaultVenvRuff
} elseif ($env:VIRTUAL_ENV -and (Test-Path -LiteralPath (Join-Path $env:VIRTUAL_ENV 'Scripts\ruff.exe'))) {
    $RuffExe = Join-Path $env:VIRTUAL_ENV 'Scripts\ruff.exe'
} elseif (Get-Command ruff.exe -ErrorAction SilentlyContinue) {
    $RuffExe = (Get-Command ruff.exe).Source
} elseif (Get-Command ruff -ErrorAction SilentlyContinue) {
    $RuffExe = (Get-Command ruff).Source
} else {
    & $Python -m ruff --version >$null 2>&1
    if ($LASTEXITCODE -eq 0) {
        $UseRuffModule = $true
    }
}

if ((-not $RuffExe) -and (-not $UseRuffModule)) {
    Write-Output "FAIL: ruff.exe not found at $defaultVenvRuff and 'ruff' module not available in $Python"
    Write-Output "Install the dev requirements: pip install -r requirements-dev.txt"
    exit 1
}

$env:QT_QPA_PLATFORM = 'offscreen'

$script:Results = @()
$script:RealChecksFailed = $false

function Invoke-Check {
    # $ForcedExitCode lets a check decide its own result (used by the log
    # check, which needs logic rather than a command exit code). A block must
    # never call exit: that would terminate the whole script.
    param(
        [string]$Name,
        [scriptblock]$Command,
        [switch]$Informational,
        [int]$ForcedExitCode = -1
    )
    Write-Output "=== $Name ==="
    try {
        & $Command
        if ($ForcedExitCode -ge 0) {
            $code = $ForcedExitCode
        } else {
            $code = $LASTEXITCODE
        }
    } catch {
        Write-Output "ERROR: Check '$Name' threw an exception: $_"
        $code = 1
    }
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

# --- the engineering log must stay append-only -------------------------------
# Rule 7 of the working agreement: git diff --numstat origin/main...HEAD --
# docs/ai_engineering_log.md must show 0 deletions.
$targetRef = 'origin/main'
& git rev-parse --verify origin/main >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    & git rev-parse --verify main >$null 2>&1
    if ($LASTEXITCODE -eq 0) {
        $targetRef = 'main'
    }
}
$logNumstat = git diff --numstat "$targetRef...HEAD" -- docs/ai_engineering_log.md 2>&1
$logCommandFailed = ($LASTEXITCODE -ne 0)
$logDeleted = 0
$logChanged = $false
if ($logNumstat) {
    foreach ($line in $logNumstat) {
        $parts = $line -split "`t"
        if ($parts.Length -ge 2) {
            $logChanged = $true
            $logDeleted += [int]$parts[1]
        }
    }
}
if ($logCommandFailed) {
    $logCode = 2
} elseif ($logDeleted -gt 0) {
    $logCode = 1
} else {
    $logCode = 0
}
$logNote = "git diff --numstat $targetRef...HEAD -- docs/ai_engineering_log.md"
if ($logCommandFailed) {
    $logNote = "git diff failed; cannot judge the log against $targetRef"
} elseif (-not $logChanged) {
    $logNote = 'no change to the engineering log in this range'
} else {
    $logNote = "changed, deleted lines = $logDeleted"
}

Invoke-Check -Name 'git branch --show-current' -Informational -Command { git branch --show-current }
Invoke-Check -Name 'git status --short'        -Informational -Command { git status --short }
Invoke-Check -Name 'pytest -q'                 -Command { & $Python -m pytest -q }
if ($UseRuffModule) {
    Invoke-Check -Name 'ruff check .'          -Command { & $Python -m ruff check . }
    Invoke-Check -Name 'ruff format --check .' -Command { & $Python -m ruff format --check . }
} else {
    Invoke-Check -Name 'ruff check .'          -Command { & $RuffExe check . }
    Invoke-Check -Name 'ruff format --check .' -Command { & $RuffExe format --check . }
}
Invoke-Check -Name 'app.py --smoke-test'       -Command { & $Python app.py --smoke-test }
Invoke-Check -Name 'app.py --shell --smoke-test' -Command { & $Python app.py --shell --smoke-test }
Invoke-Check -Name 'engineering log append-only' -ForcedExitCode $logCode -Command {
    Write-Output $logNote
    if ($logNumstat) { foreach ($line in $logNumstat) { Write-Output $line } }
}
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

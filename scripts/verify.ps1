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
# Rule 7 of the working agreement: earlier entries may never be edited or
# removed. scripts/check_log_append_only.py compares the file at the base ref
# with the file at HEAD and requires the new content to start with the old
# content byte for byte. The previous `git diff --numstat` deletion count was
# replaced because it reported a deletion when the base copy merely lacked a
# trailing newline.
$targetRef = 'origin/main'
& git rev-parse --verify origin/main >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    & git rev-parse --verify main >$null 2>&1
    if ($LASTEXITCODE -eq 0) {
        $targetRef = 'main'
    }
}
& git merge-base $targetRef HEAD >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    $shallowRoot = (git rev-list --max-parents=0 HEAD | Select-Object -First 1)
    if ($shallowRoot) {
        $targetRef = $shallowRoot.Trim()
    }
}
$logScript = Join-Path $root 'scripts\check_log_append_only.py'
$logOutput = & $Python $logScript $targetRef 'docs/ai_engineering_log.md' 2>&1
$logCode = $LASTEXITCODE
$logNote = "check_log_append_only.py $targetRef docs/ai_engineering_log.md"

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
    if ($logOutput) { foreach ($line in $logOutput) { Write-Output $line } }
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

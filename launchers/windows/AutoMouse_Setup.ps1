# Windows setup for Möuseley Kräs. Mirrors AutoMouse_Setup.command's steps
# exactly (same order, same reconciliation-to-lock-file logic); macOS-only
# parts (AppleScript, chflags, Homebrew/Framework R paths) are omitted, since
# they don't apply here and Rscript.exe discovery is already handled
# cross-platform by config.py's own R-executable-discovery logic.
#
# IMPLEMENTED BUT NOT VERIFIED: this script has not been executed on a real
# Windows machine or in CI (no PowerShell interpreter was available to test
# it from this session). Treat it as Phase 3 (implementation), not Phase 4
# (verification) — see docs/MACOS_EXECUTABLE_PLAN.md and the portability
# progress log.

param(
    [switch]$Reset
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot | Split-Path -Parent
Set-Location $ProjectDir

function Pause-IfInteractive {
    if ([Environment]::UserInteractive -and -not ([Console]::IsInputRedirected)) {
        Write-Host "Press any key to close..."
        [void][System.Console]::ReadKey($true)
    }
}

Write-Host "Möuseley Kräs Windows setup"
Write-Host "Project: $ProjectDir"

if (-not (Test-Path "pyproject.toml") -or -not (Test-Path "src\automouse")) {
    Write-Host "This does not appear to be the Möuseley Kräs project directory."
    Pause-IfInteractive
    exit 1
}

$PythonBin = $null
foreach ($candidate in @("py -3.14", "py -3.13", "py -3.12", "py -3.11", "py", "python")) {
    $parts = $candidate -split " "
    $exe = $parts[0]
    if ($parts.Length -gt 1) { $exeArgs = $parts[1..($parts.Length - 1)] } else { $exeArgs = @() }
    if (Get-Command $exe -ErrorAction SilentlyContinue) {
        $checkArgs = $exeArgs + @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)")
        & $exe @checkArgs 2>$null
        if ($LASTEXITCODE -eq 0) {
            $PythonBin = $exe
            $PythonArgs = $exeArgs
            break
        }
    }
}

if (-not $PythonBin) {
    Write-Host ""
    Write-Host "Python 3.11 or newer is required."
    Write-Host "Install it from https://www.python.org/downloads/windows/ and run setup again."
    Pause-IfInteractive
    exit 1
}

if (-not (Get-Command Rscript.exe -ErrorAction SilentlyContinue) -and -not (Test-Path "C:\Program Files\R")) {
    Write-Host ""
    Write-Host "Rscript was not found. Install R from https://cran.r-project.org/bin/windows/base/"
    Pause-IfInteractive
    exit 1
}

if ($Reset -and (Test-Path ".venv")) {
    $LegacyDir = Join-Path $ProjectDir "AutoMouse_legacy_environments"
    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $LegacyTarget = Join-Path $LegacyDir ".venv_$Timestamp"
    New-Item -ItemType Directory -Force -Path $LegacyDir | Out-Null
    Move-Item ".venv" $LegacyTarget
    Write-Host "Moved the old recoverable environment to: $LegacyTarget"
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $PythonBin @PythonArgs -m venv .venv
}

$VenvPython = ".venv\Scripts\python.exe"

# Reconcile to requirements.lock.txt on EVERY run (not just when a required
# library is missing) so an existing environment converges to the pinned
# versions instead of silently keeping whatever was already installed.
$CoreImportCheck = "import yaml, openpyxl, pandas, flask"
if (Test-Path "requirements.lock.txt") {
    & $VenvPython -m pip install -r requirements.lock.txt
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Installed/verified exact, pinned dependency versions from requirements.lock.txt."
    } else {
        Write-Host ""
        Write-Host "WARNING: could not install from requirements.lock.txt (offline and not cached?)."
        & $VenvPython -c $CoreImportCheck 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Continuing with the versions already installed in this venv - they are NOT"
            Write-Host "guaranteed to match requirements.lock.txt. Run this script again once online"
            Write-Host "to reconcile to the pinned versions."
        } else {
            Write-Host "Falling back to installing required libraries by version range (not pinned)..."
            & $VenvPython -m pip install "PyYAML>=6.0" "openpyxl>=3.1" "pandas>=2.2" "Flask>=3.0"
        }
        Write-Host ""
    }
} else {
    & $VenvPython -c $CoreImportCheck 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing required Python libraries (no requirements.lock.txt found; using version ranges)..."
        & $VenvPython -m pip install "PyYAML>=6.0" "openpyxl>=3.1" "pandas>=2.2" "Flask>=3.0"
    } else {
        Write-Host "Required Python libraries are already installed; using them offline."
    }
}

# Register the automouse package + its "automouse" console-script entry
# point in this venv, so it can be run directly
# (.venv\Scripts\automouse.exe --help) without setting PYTHONPATH by hand.
& $VenvPython -c "import setuptools" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $VenvPython -m pip install --no-deps "setuptools>=68" | Out-Null
}
& $VenvPython -m pip install --no-deps --no-build-isolation -e . | Out-Null

# The Google Sheet DOB/Wean_By overlay needs these libraries only if it is
# enabled; skip quietly (with a warning at run time, not a setup failure)
# if offline.
& $VenvPython -c "import googleapiclient, google.oauth2.service_account" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing optional Google Sheets overlay libraries..."
    & $VenvPython -m pip install "google-api-python-client>=2.100" "google-auth>=2.23"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Could not install the Sheets overlay libraries; the batch will warn and continue without them."
    }
} else {
    Write-Host "Google Sheets overlay libraries are already installed; using them offline."
}

$RscriptBin = (Get-Command Rscript.exe -ErrorAction SilentlyContinue).Source
if (-not $RscriptBin) {
    $Found = Get-ChildItem "C:\Program Files\R" -Filter "Rscript.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($Found) { $RscriptBin = $Found.FullName }
}
if (-not $RscriptBin) {
    Write-Host "Rscript.exe could not be located to verify R packages."
    Pause-IfInteractive
    exit 1
}
& $RscriptBin -e 'missing <- setdiff(c("dplyr", "purrr"), rownames(installed.packages())); if (length(missing)) stop(paste("Missing R packages:", paste(missing, collapse=", ")))'
if ($LASTEXITCODE -ne 0) {
    Pause-IfInteractive
    exit 1
}

# Unlike macOS, there is no known Windows equivalent of the hidden-.pth-file
# issue this project hit under Python 3.14 on macOS (see
# scripts/fix_hidden_venv.sh) - that repair is intentionally NOT run here.

Write-Host "Checking Möuseley Kräs directly from this project..."
& $VenvPython -c "import automouse; print('Möuseley Kräs', automouse.__version__, 'from', automouse.__file__)"
& ".venv\Scripts\automouse.exe" --help | Out-Null
Write-Host "Direct command works: .venv\Scripts\automouse.exe (no PYTHONPATH needed)"
$env:PYTHONPATH = Join-Path $ProjectDir "src"
& $VenvPython -m automouse --help | Out-Null
& $VenvPython -m unittest discover -s tests -v
Remove-Item Env:\PYTHONPATH

Write-Host ""
Write-Host "Setup, source-path smoke tests, and workflow tests completed successfully."
Write-Host "Next: run launchers\windows\AutoMouse_Run.ps1 with one or more raw CSV files."
Pause-IfInteractive

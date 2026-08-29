# Windows equivalent of XolPotsXol_Setup.command. Same steps, minus the
# macOS-only hidden-.pth-file repair (no known Windows equivalent of that
# issue).
#
# IMPLEMENTED BUT NOT VERIFIED: this script has not been executed on a real
# Windows machine or in CI (no PowerShell interpreter was available to test
# it from this session).

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot | Split-Path -Parent
$XpxDir = Join-Path $ProjectDir "xol-pots-xol"
Set-Location $XpxDir

function Pause-IfInteractive {
    if ([Environment]::UserInteractive -and -not ([Console]::IsInputRedirected)) {
        Write-Host "Press any key to close..."
        [void][System.Console]::ReadKey($true)
    }
}

# $ErrorActionPreference = "Stop" only turns PowerShell-native errors into
# terminating ones - it does NOT catch a nonzero exit code from an external
# native command like python.exe, pip, or a console-script .exe. Every
# command whose failure must actually stop this script goes through this
# helper instead of a bare `&` call, so "completed successfully" at the end
# of this script is never printed after a step that silently failed.
function Invoke-RequiredCommand {
    param(
        [Parameter(Mandatory)][scriptblock]$Command,
        [Parameter(Mandatory)][string]$Description
    )
    & $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "FAILED: $Description (exit code $LASTEXITCODE)."
        Pause-IfInteractive
        exit 1
    }
}

Write-Host "Xol-Pots-Xol Windows setup"
Write-Host "Project: $XpxDir"

if (-not (Test-Path "pyproject.toml") -or -not (Test-Path "src\xolpotsxol")) {
    Write-Host "This does not appear to be the Xol-Pots-Xol project directory."
    Pause-IfInteractive
    exit 1
}

# Xol-Pots-Xol is a standalone sibling project (see CLAUDE.md) - it gets its
# own venv, independent of Möuseley Kräs's root .venv.
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

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Invoke-RequiredCommand -Description "creating the virtual environment" -Command {
        & $PythonBin @PythonArgs -m venv .venv
    }
}

$VenvPython = ".venv\Scripts\python.exe"

# Reconcile to requirements.lock.txt on EVERY run, not just when a required
# library is missing, so an existing environment converges to the pinned
# versions instead of silently keeping whatever was already installed.
if (Test-Path "requirements.lock.txt") {
    & $VenvPython -m pip install -r requirements.lock.txt
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Installed/verified exact, pinned dependency versions from requirements.lock.txt."
    } else {
        Write-Host ""
        Write-Host "WARNING: could not install from requirements.lock.txt (offline and not cached?)."
        & $VenvPython -c "import openpyxl, flask" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Continuing with the versions already installed in this venv - they are NOT"
            Write-Host "guaranteed to match requirements.lock.txt. Run this script again once online"
            Write-Host "to reconcile to the pinned versions."
        } else {
            Write-Host "Falling back to installing required libraries by version range (not pinned)..."
            & $VenvPython -m pip install "openpyxl>=3.1" "Flask>=3.0"
        }
        Write-Host ""
    }
} else {
    & $VenvPython -c "import openpyxl, flask" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing required Python libraries (no requirements.lock.txt found; using version ranges)..."
        & $VenvPython -m pip install "openpyxl>=3.1" "Flask>=3.0"
    } else {
        Write-Host "Required Python libraries are already installed; using them offline."
    }
}

& $VenvPython -c "import setuptools" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $VenvPython -m pip install --no-deps "setuptools>=68" | Out-Null
}
Invoke-RequiredCommand -Description "installing xolpotsxol as an editable package" -Command {
    & $VenvPython -m pip install --no-deps --no-build-isolation -e . | Out-Null
}

Write-Host "Checking Xol-Pots-Xol directly from this project..."
Invoke-RequiredCommand -Description "importing xolpotsxol from the installed venv" -Command {
    & $VenvPython -c "import xolpotsxol; print('Xol-Pots-Xol from', xolpotsxol.__file__)"
}
Invoke-RequiredCommand -Description ".venv\Scripts\xolpotsxol.exe --help" -Command {
    & ".venv\Scripts\xolpotsxol.exe" --help | Out-Null
}
Write-Host "Direct commands work: xol-pots-xol\.venv\Scripts\xolpotsxol.exe, xolpotsxol-serve.exe"
Invoke-RequiredCommand -Description "the xolpotsxol test suite" -Command {
    & $VenvPython -m unittest discover -s tests -v
}

Write-Host ""
Write-Host "Setup and workflow tests completed successfully."
Write-Host "Next: run launchers\windows\XolPotsXol_WebApp.ps1 to start the web app."
Pause-IfInteractive

# Windows equivalent of XolPotsXol_WebApp.command.
#
# IMPLEMENTED BUT NOT VERIFIED: this script has not been executed on a real
# Windows machine or in CI (no PowerShell interpreter was available to test
# it from this session).

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot | Split-Path -Parent
Set-Location $ProjectDir

function Pause-IfInteractive {
    if ([Environment]::UserInteractive -and -not ([Console]::IsInputRedirected)) {
        Write-Host "Press any key to close..."
        [void][System.Console]::ReadKey($true)
    }
}

$XpxVenvPython = Join-Path $ProjectDir "xol-pots-xol\.venv\Scripts\python.exe"
$XpxVenvServe = Join-Path $ProjectDir "xol-pots-xol\.venv\Scripts\xolpotsxol-serve.exe"

if (-not (Test-Path $XpxVenvPython)) {
    Write-Host "Xol-Pots-Xol's own environment is not set up. Run launchers\windows\XolPotsXol_Setup.ps1 first."
    Pause-IfInteractive
    exit 1
}
& $XpxVenvPython -c "import xolpotsxol, flask, openpyxl" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Xol-Pots-Xol's environment is missing a required package. Run"
    Write-Host "launchers\windows\XolPotsXol_Setup.ps1 to repair it, then try again."
    Pause-IfInteractive
    exit 1
}

Write-Host "Starting the Xol-Pots-Xol web app..."
Write-Host "A browser tab will open automatically. Leave this window open while you use it;"
Write-Host "closing this window or pressing Control-C here stops the web app."
Write-Host ""

$RuntimeRoot = Join-Path $ProjectDir "xol-pots-xol\runtime"
& $XpxVenvServe --runtime-root $RuntimeRoot
$Status = $LASTEXITCODE
if ($Status -ne 0) {
    Write-Host ""
    Write-Host "Xol-Pots-Xol web app stopped with an error. Review the message above."
    Pause-IfInteractive
    exit $Status
}

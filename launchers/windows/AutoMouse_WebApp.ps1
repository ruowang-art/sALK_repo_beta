# Windows equivalent of AutoMouse_WebApp.command.
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

$VenvPython = ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Möuseley Kräs is not set up. Run launchers\windows\AutoMouse_Setup.ps1 first."
    Pause-IfInteractive
    exit 1
}
$env:PYTHONPATH = Join-Path $ProjectDir "src"
& $VenvPython -c "import automouse, flask" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "The Möuseley Kräs web app is not available yet."
    Write-Host "Run launchers\windows\AutoMouse_Setup.ps1 to install its remaining requirement (Flask), then try again."
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
    Pause-IfInteractive
    exit 1
}

Write-Host "Starting the Möuseley Kräs web app..."
Write-Host "A browser tab will open automatically. Leave this window open while you use it;"
Write-Host "closing this window or pressing Control-C here stops the web app."
Write-Host ""

& $VenvPython -m automouse --config config\pipeline_run.yaml serve
$Status = $LASTEXITCODE
Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
if ($Status -ne 0) {
    Write-Host ""
    Write-Host "Möuseley Kräs web app stopped with an error. Review the message above."
    Pause-IfInteractive
    exit $Status
}

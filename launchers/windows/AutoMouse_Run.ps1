# Windows equivalent of AutoMouse_Run.command. Same batch-processing logic
# and same duplicate-input confirmation flow; the macOS AppleScript file
# picker is replaced with a native Windows.Forms.OpenFileDialog multi-select
# dialog when no file paths are given on the command line.
#
# IMPLEMENTED BUT NOT VERIFIED: this script has not been executed on a real
# Windows machine or in CI (no PowerShell interpreter was available to test
# it from this session). Treat it as Phase 3 (implementation), not Phase 4
# (verification).

param(
    [string[]]$InputFiles
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

$VenvPython = ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Möuseley Kräs is not set up. Run launchers\windows\AutoMouse_Setup.ps1 first."
    Pause-IfInteractive
    exit 1
}
$env:PYTHONPATH = Join-Path $ProjectDir "src"
& $VenvPython -c "import automouse" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "The Möuseley Kräs source package is unreadable."
    Write-Host "Re-run launchers\windows\AutoMouse_Setup.ps1 -Reset to rebuild it safely."
    Pause-IfInteractive
    exit 1
}

$RawInputs = @()
if ($InputFiles -and $InputFiles.Count -gt 0) {
    $RawInputs = $InputFiles
} else {
    Add-Type -AssemblyName System.Windows.Forms
    $Dialog = New-Object System.Windows.Forms.OpenFileDialog
    $Dialog.InitialDirectory = $ProjectDir
    $Dialog.Filter = "CSV files (*.csv)|*.csv"
    $Dialog.Multiselect = $true
    $Dialog.Title = "Choose one or more raw Transnetyx CSV files"
    $Result = $Dialog.ShowDialog()
    if ($Result -ne [System.Windows.Forms.DialogResult]::OK -or $Dialog.FileNames.Count -eq 0) {
        Write-Host "Selection cancelled; no files were processed."
        exit 0
    }
    $RawInputs = $Dialog.FileNames
}

$ValidatedInputs = @()
foreach ($inputPath in $RawInputs) {
    if ([string]::IsNullOrWhiteSpace($inputPath)) { continue }
    if (-not (Test-Path $inputPath -PathType Leaf)) {
        Write-Host "Selected input does not exist: $inputPath"
        Pause-IfInteractive
        exit 1
    }
    if ([System.IO.Path]::GetExtension($inputPath).ToLowerInvariant() -ne ".csv") {
        Write-Host "Selected input is not a CSV file: $inputPath"
        Pause-IfInteractive
        exit 1
    }
    $ValidatedInputs += $inputPath
}

if ($ValidatedInputs.Count -eq 0) {
    Write-Host "No CSV files were selected."
    Pause-IfInteractive
    exit 1
}

Write-Host "Möuseley Kräs will process $($ValidatedInputs.Count) file(s) as one batch:"
for ($i = 0; $i -lt $ValidatedInputs.Count; $i++) {
    Write-Host "  $($i + 1). $($ValidatedInputs[$i])"
}

# Exit code 3 means Möuseley Kräs blocked the run because one or more
# selected files were already archived in an earlier run (see cli.py) -
# handled separately below instead of treating it as a generic failure.
$DuplicateInputExitCode = 3

& $VenvPython -m automouse --config config\pipeline_run.yaml run --verbose @ValidatedInputs
$Status = $LASTEXITCODE

if ($Status -eq $DuplicateInputExitCode) {
    Write-Host ""
    Write-Host "One or more selected files were already processed in an earlier run."
    Write-Host "Only choose to re-run if this is an intentional retry (for example, a"
    Write-Host "corrected re-download); Möuseley Kräs will reprocess the file as new data."
    $Reply = "n"
    if ([Environment]::UserInteractive -and -not ([Console]::IsInputRedirected)) {
        $Reply = Read-Host "Re-run anyway? [y/N]"
    }
    if ($Reply -match "^[Yy]$") {
        Write-Host "Re-running with duplicate input allowed..."
        & $VenvPython -m automouse --config config\pipeline_run.yaml run --verbose --allow-duplicate-input @ValidatedInputs
        $Status = $LASTEXITCODE
    } else {
        Write-Host "Not re-running. No files were processed."
    }
}

Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue

if ($Status -ne 0) {
    Pause-IfInteractive
    exit $Status
}

Write-Host ""
Write-Host "Batch completed. Review the exception report and Live Label workbook in:"
Write-Host (Join-Path $ProjectDir "outputs\019fb5fc-cfb6-7a51-9423-58940a90cde9\automouse_runtime")
Pause-IfInteractive


# Script to run pre-flight checks (linting + tests) locally
$ErrorActionPreference = "Stop"

Write-Host "Starting Pre-flight Checks..." -ForegroundColor Cyan

# Create DebugInfo directory structure if it doesn't exist
$DebugInfoDir = Join-Path $PSScriptRoot "..\DebugInfo"
$LogDir = Join-Path $DebugInfoDir "PreFlight"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

$LogFile = Join-Path $LogDir "pre_flight.log"
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

# Function to log messages
function Write-Log {
    param([string]$Message)
    $LogEntry = "[$Timestamp] $Message"
    Add-Content -Path $LogFile -Value $LogEntry
    Write-Host $Message
}

Write-Log "Starting Pre-flight Sequence..."

# 1. Run Linting
Write-Log "Step 1: Running Linting..."
try {
    # Call the run_lint.ps1 script located in the same directory
    $LintScript = Join-Path $PSScriptRoot "run_lint.ps1"
    if (Test-Path $LintScript) {
        # Execute run_lint.ps1 and capture its output to log
        # We need to run it in a way that we can capture exit code
        $LintProcess = Start-Process -FilePath "powershell" -ArgumentList "-File `"$LintScript`"" -PassThru -Wait -NoNewWindow
        
        if ($LintProcess.ExitCode -eq 0) {
            Write-Log "Linting Passed."
        }
        else {
            throw "Linting Failed with exit code $($LintProcess.ExitCode)."
        }
    }
    else {
        throw "run_lint.ps1 script not found!"
    }
}
catch {
    Write-Log "Pre-flight Check Failed at Linting Step."
    Write-Log $_
    Write-Host "Pre-flight Failed during Linting! Check $LogFile for details." -ForegroundColor Red
    exit 1
}

# 2. Run Unit Tests (via Pipeline, skipping build)
Write-Log "Step 2: Running Unit Tests..."
try {
    # run_pipeline.ps1 is now at the repository root (parent of scripts folder)
    $TestScript = Join-Path $PSScriptRoot "..\run_pipeline.ps1"
    if (Test-Path $TestScript) {
        # Call pipeline with -SkipBuild to only run tests
        $TestProcess = Start-Process -FilePath "powershell" -ArgumentList "-File `"$TestScript`" -SkipBuild" -PassThru -Wait -NoNewWindow
         
        if ($TestProcess.ExitCode -eq 0) {
            Write-Log "Unit Tests Passed."
        }
        else {
            throw "Unit Tests Failed with exit code $($TestProcess.ExitCode)."
        }
    }
    else {
        throw "run_pipeline.ps1 script not found!"
    }
}
catch {
    Write-Log "Pre-flight Check Failed at Unit Test Step."
    Write-Log $_
    Write-Host "Pre-flight Failed during Unit Tests! Check $LogFile for details." -ForegroundColor Red
    exit 1
}

Write-Log "All Pre-flight Checks Passed Successfully!"
Write-Host "Pre-flight Checks Passed!" -ForegroundColor Green

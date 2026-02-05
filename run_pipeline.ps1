param(
    [switch]$SkipBuild = $false
)

# Script to run the full pipeline (Tests + Build)
$ErrorActionPreference = "Stop"

Write-Host "Starting Cerebrus Pipeline..." -ForegroundColor Cyan

# Create DebugInfo directory structure if it doesn't exist
$DebugInfoDir = Join-Path $PSScriptRoot "DebugInfo"
$LogDir = Join-Path $DebugInfoDir "Pipeline"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

$LogFile = Join-Path $LogDir "pipeline.log"
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

# Function to log messages
function Write-Log {
    param([string]$Message)
    $LogEntry = "[$Timestamp] $Message"
    Add-Content -Path $LogFile -Value $LogEntry
    Write-Host $Message
}

Write-Log "=== Pipeline Started ==="

# Activate venv if needed (assuming standard location)
$VenvPath = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $VenvPath) {
    Write-Log "Activating virtual environment..."
    . $VenvPath
}
else {
    Write-Log "Warning: Virtual environment not found at $VenvPath. Running with system python."
}

# 0. Run Pre-flight Checks (Linting mainly, as pytest is run in step 1)
Write-Log "Step 0: Running Linting (Pre-flight)..."
try {
    $LintScript = Join-Path $PSScriptRoot "scripts\run_lint.ps1"
    if (Test-Path $LintScript) {
        Write-Log "Executing run_lint.ps1..."
        $LintProcess = Start-Process -FilePath "powershell" -ArgumentList "-File `"$LintScript`"" -PassThru -Wait -NoNewWindow
        
        if ($LintProcess.ExitCode -eq 0) {
            Write-Log "Linting Passed."
            Write-Host "Linting Passed!" -ForegroundColor Green
        }
        else {
            throw "Linting failed with exit code $($LintProcess.ExitCode)."
        }
    }
    else {
        throw "run_lint.ps1 script not found at $LintScript"
    }
}
catch {
    Write-Log "Pipeline Failed at Linting Step."
    Write-Log $_
    Write-Host "Linting Failed! Check $LogFile for details." -ForegroundColor Red
    exit 1
}

# 1. Run Unit Tests
Write-Log "Step 1: Running Unit Tests..."
try {
    # Using python -m pytest to avoid path issues
    $TestOutput = python -m pytest tests 2>&1 | Out-String
    Write-Log $TestOutput
    if ($LASTEXITCODE -ne 0) { throw "Pytest failed with exit code $LASTEXITCODE" }
    Write-Log "Unit Tests Passed."
    Write-Host "Unit Tests Passed!" -ForegroundColor Green
}
catch {
    Write-Log "Pipeline Failed at Unit Tests."
    Write-Log $_
    Write-Host "Unit Tests Failed! Check $LogFile for details." -ForegroundColor Red
    exit 1
}

# 2. Build Distributable (if not skipped)
if (-not $SkipBuild) {
    Write-Log "Step 2: Building Distributable..."
    try {
        $BuildScript = Join-Path $PSScriptRoot "scripts\build_pyinstaller.ps1"
        if (Test-Path $BuildScript) {
            Write-Log "Executing build_pyinstaller.ps1..."
            # Execute build script
            $BuildProcess = Start-Process -FilePath "powershell" -ArgumentList "-File `"$BuildScript`"" -PassThru -Wait -NoNewWindow
            
            if ($BuildProcess.ExitCode -eq 0) {
                Write-Log "Build Successful."
                Write-Host "Build Successful!" -ForegroundColor Green
            }
            else {
                throw "Build script failed with exit code $($BuildProcess.ExitCode)."
            }
        }
        else {
            throw "build_pyinstaller.ps1 script not found!"
        }
    }
    catch {
        Write-Log "Pipeline Failed at Build Step."
        Write-Log $_
        Write-Host "Build Failed! Check $LogFile for details." -ForegroundColor Red
        exit 1
    }
}
else {
    Write-Log "Build Step Skipped by user request."
    Write-Host "Build Step Skipped." -ForegroundColor Yellow
}

Write-Log "=== Pipeline Finished Successfully ==="
Write-Host "Pipeline Complete!" -ForegroundColor Green

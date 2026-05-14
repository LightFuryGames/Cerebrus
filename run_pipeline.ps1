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
    $TestScript = Join-Path $PSScriptRoot "scripts\run_unittests.ps1"
    if (Test-Path $TestScript) {
        Write-Log "Executing run_unittests.ps1..."
        
        # Execute the test script and capture output
        $TestProcess = Start-Process -FilePath "powershell" -ArgumentList "-File `"$TestScript`"" -PassThru -Wait -NoNewWindow
        
        if ($TestProcess.ExitCode -eq 0) {
            Write-Log "Unit Tests Passed."
            Write-Host "Unit Tests Passed!" -ForegroundColor Green
        }
        else {
            throw "Unit Tests failed with exit code $($TestProcess.ExitCode)."
        }
    }
    else {
        throw "run_unittests.ps1 script not found at $TestScript"
    }
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

# 2.5 Analytics pipeline smoke test - end-to-end sanity check on TestData JSONs
Write-Log "Step 2.5: Running Analytics Pipeline Smoke Test..."
try {
    $PythonExe = "python"
    if (Test-Path ".venv\Scripts\python.exe") {
        $PythonExe = ".venv\Scripts\python.exe"
    }
    $SmokeArgs = @(
        "-c",
        @"
from pathlib import Path
from cerebrus.plugins.analytics.core.html_report_parser import PerformanceHTMLReportParser
from cerebrus.plugins.analytics.core.csv_report_parser import PerformanceCSVReportParser
from cerebrus.plugins.analytics.core.normalizer import build_analytics_document
root = Path('TestData/Profiling')
ini = root / 'BaseDeviceProfiles.ini'
htmls = {p.stem: p for p in root.rglob('HTML/*.html')}
checked = 0
for csv_file in root.rglob('CSV/*.csv'):
    stem = csv_file.stem
    html_path = htmls.get(stem)
    if html_path is None:
        raw = PerformanceCSVReportParser(csv_file).parse()
        doc = build_analytics_document(source_path=csv_file, source_type='profiling_csv', raw_values=raw, device_profile_config_path=ini)
    else:
        parser = PerformanceHTMLReportParser(html_path)
        raw_csv = parser.extract_embedded_raw_csv()
        embedded = parser.embedded_profile_name()
        logical = html_path.with_name(f'{embedded}.csv') if embedded else html_path
        raw = PerformanceCSVReportParser(logical, csv_text=raw_csv).parse()
        doc = build_analytics_document(source_path=html_path, source_type='profiling_html_raw_csv', raw_values=raw, device_profile_config_path=ini)
    assert doc['schema_version'] == 2, f'{stem}: schema_version={doc[\"schema_version\"]}'
    assert 1 <= doc['report_value'] <= 100, f'{stem}: report_value out of range'
    assert doc['report_fingerprint'], f'{stem}: empty fingerprint'
    assert doc['data_quality_has_corruption'] in (0, 1), f'{stem}: bad corruption flag'
    checked += 1
print(f'Analytics smoke OK ({checked} samples)')
"@
    )
    & $PythonExe @SmokeArgs
    if ($LASTEXITCODE -ne 0) { throw "Analytics smoke test failed with exit code $LASTEXITCODE." }
    Write-Log "Analytics smoke test passed."
    Write-Host "Analytics Smoke Passed!" -ForegroundColor Green
}
catch {
    Write-Log "Pipeline Failed at Analytics Smoke Test."
    Write-Log $_
    Write-Host "Analytics Smoke Failed! Check $LogFile for details." -ForegroundColor Red
    exit 1
}

Write-Log "=== Pipeline Finished Successfully ==="
Write-Host "Pipeline Complete!" -ForegroundColor Green

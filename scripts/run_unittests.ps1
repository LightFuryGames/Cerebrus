$ErrorActionPreference = "Stop"

# Use virtual environment python if available
if (Test-Path ".venv\Scripts\python.exe") {
    $PythonExe = ".venv\Scripts\python.exe"
}
else {
    $PythonExe = "python"
}

Write-Host "Running Unit Tests with coverage..." -ForegroundColor Cyan

# Detect pytest-cov; if absent, run tests without coverage instead of failing.
$HasCov = $true
try {
    & $PythonExe -c "import pytest_cov" 2>$null
    if ($LASTEXITCODE -ne 0) { $HasCov = $false }
}
catch { $HasCov = $false }

# Ensure pipeline log dir exists for the junit report.
$null = New-Item -ItemType Directory -Path "DebugInfo/Pipeline" -Force -ErrorAction SilentlyContinue

if ($HasCov) {
    & $PythonExe -m pytest tests `
        --cov=cerebrus `
        --cov-report=term-missing:skip-covered `
        --cov-report=xml `
        --junitxml=DebugInfo/Pipeline/test-results.xml
}
else {
    Write-Host "pytest-cov not installed; running without coverage." -ForegroundColor Yellow
    & $PythonExe -m pytest tests `
        --junitxml=DebugInfo/Pipeline/test-results.xml
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "Tests Failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Tests Passed!" -ForegroundColor Green
exit 0

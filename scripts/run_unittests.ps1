$ErrorActionPreference = "Stop"

# Use virtual environment python if available
if (Test-Path ".venv\Scripts\python.exe") {
    $PythonExe = ".venv\Scripts\python.exe"
}
else {
    $PythonExe = "python"
}

Write-Host "Running Unit Tests..." -ForegroundColor Cyan
& $PythonExe -m pytest tests

if ($LASTEXITCODE -ne 0) {
    Write-Host "Tests Failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Tests Passed!" -ForegroundColor Green
exit 0

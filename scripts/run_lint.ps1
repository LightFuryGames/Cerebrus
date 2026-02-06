# Run all linters and save output
# Ensure output directory exists
# Ensure output directory exists
$DebugInfoDir = Join-Path $PSScriptRoot "..\DebugInfo"
$logDir = Join-Path $DebugInfoDir "Linting"
if (-not (Test-Path -Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

# Ensure UTF-8 for console output
$env:PYTHONIOENCODING = "utf-8"

Write-Host "=== Running Black ===" -ForegroundColor Cyan
python -m black --check --target-version py312 . 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath "$logDir\lint_black.log"
$blackExit = $LASTEXITCODE

Write-Host "`n=== Running isort ===" -ForegroundColor Cyan
python -m isort --check-only --py 312 . 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath "$logDir\lint_isort.log"
$isortExit = $LASTEXITCODE

Write-Host "`n=== Running mypy ===" -ForegroundColor Cyan
python -m mypy --python-version 3.12 cerebrus 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath "$logDir\lint_mypy.log"
$mypyExit = $LASTEXITCODE

Write-Host "`n=== Summary ===" -ForegroundColor Yellow
Write-Host "Black exit code: $blackExit"
Write-Host "isort exit code: $isortExit"
Write-Host "mypy exit code: $mypyExit"

if ($blackExit -eq 0 -and $isortExit -eq 0 -and $mypyExit -eq 0) {
    Write-Host "`nAll linters passed!" -ForegroundColor Green
    exit 0
}
else {
    Write-Host "`nSome linters failed!" -ForegroundColor Red
    exit 1
}

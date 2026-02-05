# Run all linters and save output
Write-Host "=== Running Black ===" -ForegroundColor Cyan
python -m black --check . 2>&1 | Tee-Object -FilePath lint_black.log
$blackExit = $LASTEXITCODE

Write-Host "`n=== Running isort ===" -ForegroundColor Cyan
python -m isort --check-only . 2>&1 | Tee-Object -FilePath lint_isort.log
$isortExit = $LASTEXITCODE

Write-Host "`n=== Running mypy ===" -ForegroundColor Cyan
python -m mypy cerebrus 2>&1 | Tee-Object -FilePath lint_mypy.log
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

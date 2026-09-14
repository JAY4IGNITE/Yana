# ==============================================================================
# YANA - Multi-Layer Test Runner
# Executes test suites across Agent (pytest), Frontend (vitest), and Rust (cargo)
# ==============================================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Running YANA Test Suites" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$hasError = $false

# 1. Run Python Agent Tests
Write-Host "`n[1/3] Running Python Agent Tests (pytest)..." -ForegroundColor Yellow
Push-Location "$PSScriptRoot\..\apps\agent"
uv run pytest -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Python agent tests failed!" -ForegroundColor Red
    $hasError = $true
} else {
    Write-Host "[PASS] Python agent tests passed!" -ForegroundColor Green
}
Pop-Location

# 2. Run Frontend Vitest Tests
Write-Host "`n[2/3] Running Frontend Tests (vitest)..." -ForegroundColor Yellow
Push-Location "$PSScriptRoot\..\apps\desktop"
npm run test
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Frontend tests failed!" -ForegroundColor Red
    $hasError = $true
} else {
    Write-Host "[PASS] Frontend tests passed!" -ForegroundColor Green
}
Pop-Location

# 3. Run Rust Tests if Cargo is available
Write-Host "`n[3/3] Running Rust Core Tests (cargo test)..." -ForegroundColor Yellow
$cargoPath = "$HOME\.cargo\bin\cargo.exe"
if (Test-Path $cargoPath) {
    $env:PATH = "$HOME\.cargo\bin;$env:PATH"
    Push-Location "$PSScriptRoot\..\apps\desktop\src-tauri"
    & $cargoPath test
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] Cargo tests failed!" -ForegroundColor Red
        $hasError = $true
    } else {
        Write-Host "[PASS] Cargo tests passed!" -ForegroundColor Green
    }
    Pop-Location
} else {
    Write-Host "[SKIP] Cargo not found in $HOME\.cargo\bin. Skipping Rust tests." -ForegroundColor DarkYellow
}

Write-Host "`n========================================" -ForegroundColor Cyan
if ($hasError) {
    Write-Host "  Some test suites failed!" -ForegroundColor Red
    exit 1
} else {
    Write-Host "  All test suites completed successfully!" -ForegroundColor Green
    exit 0
}

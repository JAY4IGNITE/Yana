# ==============================================================================
# YANA - Multi-Layer Linter & Type Checker
# Executes formatters, linters, and type checkers across Python, TypeScript, and Rust
# ==============================================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Running YANA Linters & Type Checkers" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$hasError = $false

# 1. Python Ruff & Mypy
Write-Host "`n[1/3] Checking Python Agent (Ruff & Mypy)..." -ForegroundColor Yellow
Push-Location "$PSScriptRoot\..\apps\agent"
Write-Host "  - Running ruff check..."
uv run ruff check .
if ($LASTEXITCODE -ne 0) { $hasError = $true }

Write-Host "  - Running ruff format check..."
uv run ruff format --check .
if ($LASTEXITCODE -ne 0) { $hasError = $true }

Write-Host "  - Running mypy..."
uv run mypy .
if ($LASTEXITCODE -ne 0) { $hasError = $true }
Pop-Location

# 2. TypeScript Type Check
Write-Host "`n[2/3] Checking TypeScript Packages & Apps..." -ForegroundColor Yellow
Push-Location "$PSScriptRoot\.."
npm run typecheck
if ($LASTEXITCODE -ne 0) { $hasError = $true }
Pop-Location

# 3. Rust Check
Write-Host "`n[3/3] Checking Rust Layer..." -ForegroundColor Yellow
$cargoPath = "$HOME\.cargo\bin\cargo.exe"
if (Test-Path $cargoPath) {
    $env:PATH = "$HOME\.cargo\bin;$env:PATH"
    Push-Location "$PSScriptRoot\..\apps\desktop\src-tauri"
    & $cargoPath check
    if ($LASTEXITCODE -ne 0) { $hasError = $true }
    Pop-Location
}

Write-Host "`n========================================" -ForegroundColor Cyan
if ($hasError) {
    Write-Host "  Linting or type check errors detected!" -ForegroundColor Red
    exit 1
} else {
    Write-Host "  All linters and type checkers passed!" -ForegroundColor Green
    exit 0
}

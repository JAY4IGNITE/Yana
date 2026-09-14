# ==============================================================================
# YANA - Multi-Layer Production Build Runner
# Builds TypeScript packages, Vite frontend, and Rust Desktop application
# ==============================================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Building YANA Production Artifacts" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$hasError = $false

# 1. Typecheck & Build TypeScript Packages and Vite Frontend
Write-Host "`n[1/2] Building Frontend & TypeScript Workspaces..." -ForegroundColor Yellow
Push-Location "$PSScriptRoot\.."
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Frontend build failed!" -ForegroundColor Red
    $hasError = $true
} else {
    Write-Host "[PASS] Frontend build succeeded!" -ForegroundColor Green
}
Pop-Location

# 2. Check Rust compilation
Write-Host "`n[2/2] Checking Rust Core Build..." -ForegroundColor Yellow
$cargoPath = "$HOME\.cargo\bin\cargo.exe"
if (Test-Path $cargoPath) {
    Push-Location "$PSScriptRoot\..\apps\desktop\src-tauri"
    & $cargoPath check
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] Rust check failed!" -ForegroundColor Red
        $hasError = $true
    } else {
        Write-Host "[PASS] Rust core check succeeded!" -ForegroundColor Green
    }
    Pop-Location
} else {
    Write-Host "[SKIP] Cargo not found in $HOME\.cargo\bin." -ForegroundColor DarkYellow
}

Write-Host "`n========================================" -ForegroundColor Cyan
if ($hasError) {
    Write-Host "  Build process failed!" -ForegroundColor Red
    exit 1
} else {
    Write-Host "  All builds completed successfully!" -ForegroundColor Green
    exit 0
}

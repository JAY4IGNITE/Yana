param(
    [switch]$Production,
    [switch]$Installer,
    [switch]$Verify
)

# ==============================================================================
# YANA - Multi-Layer Production Build Runner
# Builds TypeScript packages, Vite frontend, and Rust Desktop application
# ==============================================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Building YANA Production Artifacts" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$hasError = $false

# 0. Pre-Flight Security & Invariants Verification
if ($Verify -or $Production) {
    Write-Host "`n[0/3] Running Pre-Flight Security Verifier..." -ForegroundColor Yellow
    Push-Location "$PSScriptRoot\..\apps\agent"
    uv run python "$PSScriptRoot\verify_production.py"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] Pre-flight security verification failed!" -ForegroundColor Red
        Pop-Location
        exit 1
    } else {
        Write-Host "[PASS] Pre-flight security verification passed!" -ForegroundColor Green
    }
    Pop-Location
}

# 1. Typecheck & Build TypeScript Packages and Vite Frontend
Write-Host "`n[1/3] Building Frontend & TypeScript Workspaces..." -ForegroundColor Yellow
Push-Location "$PSScriptRoot\.."
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Frontend build failed!" -ForegroundColor Red
    $hasError = $true
} else {
    Write-Host "[PASS] Frontend build succeeded!" -ForegroundColor Green
}
Pop-Location

# 2. Check Rust Core / Release Build
Write-Host "`n[2/3] Checking Rust Core Build..." -ForegroundColor Yellow
$cargoPath = "$HOME\.cargo\bin\cargo.exe"
if (Test-Path $cargoPath) {
    $env:PATH = "$HOME\.cargo\bin;$env:PATH"
    Push-Location "$PSScriptRoot\..\apps\desktop\src-tauri"
    if ($Production -or $Installer) {
        Write-Host "  Building Rust release binary..."
        & $cargoPath build --release
    } else {
        & $cargoPath check
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] Rust build failed!" -ForegroundColor Red
        $hasError = $true
    } else {
        Write-Host "[PASS] Rust core build succeeded!" -ForegroundColor Green
    }
    Pop-Location
} else {
    Write-Host "[SKIP] Cargo not found in $HOME\.cargo\bin." -ForegroundColor DarkYellow
}

# 3. Windows NSIS Installer Packaging
if ($Installer -and (-not $hasError)) {
    Write-Host "`n[3/3] Packaging Windows NSIS Installer..." -ForegroundColor Yellow
    Push-Location "$PSScriptRoot\..\apps\desktop"
    $env:PATH = "$HOME\.cargo\bin;$env:PATH"
    npx tauri build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] Tauri installer build failed!" -ForegroundColor Red
        $hasError = $true
    } else {
        Write-Host "[PASS] Windows NSIS installer packaged successfully!" -ForegroundColor Green
    }
    Pop-Location
}

Write-Host "`n========================================" -ForegroundColor Cyan
if ($hasError) {
    Write-Host "  Build process failed!" -ForegroundColor Red
    exit 1
} else {
    Write-Host "  All builds completed successfully!" -ForegroundColor Green
    exit 0
}

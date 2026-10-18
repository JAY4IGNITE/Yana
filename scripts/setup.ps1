$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
    npm install
    if ($LASTEXITCODE -ne 0) { throw 'Node dependency installation failed.' }
    Push-Location 'apps/agent'
    try {
        uv sync --extra dev
        if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
        & '.\.venv\Scripts\python.exe' -m playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw 'Browser installation failed.' }
    } finally { Pop-Location }
    Write-Host 'Setup complete. Configure .env, then run npm run dev:tauri.'
} finally { Pop-Location }

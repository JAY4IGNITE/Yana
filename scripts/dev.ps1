# ==============================================================================
# YANA - Development Environment Launcher
# Launches both the Python AI Agent and the Desktop Frontend in parallel.
# ==============================================================================

Write-Host "[YANA] Starting YANA Development Services..." -ForegroundColor Cyan

# 1. Start Python Agent in background job
$agentJob = Start-Job -ScriptBlock {
    Set-Location "$using:PSScriptRoot\..\apps\agent"
    uv run uvicorn app.main:app --port 8765 --reload
}

Write-Host "[YANA] Agent started on http://127.0.0.1:8765 (Job ID: $($agentJob.Id))" -ForegroundColor Green

# 2. Start Desktop Frontend
Set-Location "$PSScriptRoot\..\apps\desktop"
Write-Host "[YANA] Starting Desktop UI..." -ForegroundColor Cyan
npm run dev

# Cleanup background agent job on exit
Stop-Job $agentJob
Remove-Job $agentJob
Write-Host "[YANA] Services stopped." -ForegroundColor Yellow

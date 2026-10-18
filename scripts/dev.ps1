param([switch]$Browser)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    if (-not $Browser) {
        # The native supervisor starts and owns Python automatically.
        npm run dev:tauri
        exit $LASTEXITCODE
    }
    $agentPath = Join-Path $repoRoot 'apps/agent'
    $agentJob = Start-Job -ArgumentList $agentPath -ScriptBlock {
        param($agentPath)
        Set-Location $agentPath
        & '.\.venv\Scripts\python.exe' -m app.main
    }
    try {
        npm run dev:desktop
    } finally {
        Stop-Job $agentJob
        Receive-Job $agentJob
        Remove-Job $agentJob
    }
} finally { Pop-Location }

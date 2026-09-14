# YANA AI Agent Service

Backend core service for YANA desktop companion.

## Architecture

The YANA Agent implements the critical architectural pipeline:
```
USER -> YANA UI -> DESKTOP IPC -> AGENT -> PLANNER -> TOOL REGISTRY
-> PERMISSION MANAGER -> EXECUTOR -> OPERATING SYSTEM -> VERIFIER -> AGENT -> YANA UI
```

## Running

```powershell
uv run uvicorn app.main:app --port 8765 --reload
```

## Testing

```powershell
uv run pytest
```

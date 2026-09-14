# Agent Architecture (Python + FastAPI + asyncio)

The YANA Agent is the core cognitive service responsible for natural language reasoning, task planning, tool discovery, permission evaluation, safe execution, and outcome verification.

## Module Boundaries

```
apps/agent/app/
├── api/             # FastAPI REST & WebSocket routers (health, tasks, tools, permissions)
├── core/
│   ├── planner/     # Multi-step planning interface & rule/LLM planners
│   ├── executor/    # Pipeline enforcing the critical architectural principle
│   ├── verifier/    # Post-execution verification verifying real-world success
│   ├── context/     # Rolling conversation and session context manager
│   └── task_manager # Multi-step task tracking and cancellation engine
├── tools/
│   ├── base.py      # BaseTool abstract class with RiskLevel and schemas
│   ├── registry.py  # ToolRegistry managing discovery and argument validation
│   ├── system/      # Windows system tools (app launching, window control)
│   ├── computer/    # Computer automation stubs
│   ├── filesystem/  # Safe file I/O with path traversal protection
│   ├── terminal/    # Controlled shell/PowerShell runner
│   ├── browser/     # Browser automation stubs
│   └── voice/       # Speech tool stubs
├── permissions/     # PermissionManager gating operations by risk level
├── memory/          # SQLite database connection & task repository
├── ai/              # LLM provider abstractions (OpenAI, Anthropic, Local)
├── protocol/        # Pydantic v2 IPC protocol models (mirroring TypeScript contracts)
├── config.py        # Safe configuration loading with secret redaction
├── logger.py        # Structured JSON logger with credential masking
└── errors.py        # Standardized ErrorCode and YanaBaseError hierarchy
```

## Tool Risk Levels & Permission Gates

Every tool registered in `ToolRegistry` declares an explicit `RiskLevel`:

- **LOW**: Read-only operations without side effects (e.g. reading a non-sensitive file in the allowed directory, checking status). Auto-permitted.
- **MEDIUM**: Benign state changes (e.g. launching a known application like Notepad). In strict mode, requires user prompt.
- **HIGH**: Mutating filesystem operations, executing terminal commands, modifying configuration. Always requires user authorization via desktop UI dialog.
- **CRITICAL**: System modification, credential access, external network downloads. Strictly gated and highlighted with red alert in UI.

## Execution Pipeline

The execution flow in `app/core/executor/pipeline.py`:
1. **Validation**: Looks up tool in `ToolRegistry` and validates parameter types.
2. **Permission Check**: Calls `PermissionManager.enforce_permission()`. If permission was not explicitly granted, raises `PermissionError` (returns `PERMISSION_ERROR` error message).
3. **Execution**: Awaits `tool.execute(arguments)`.
4. **Verification**: Calls `Verifier.verify()`. Checks whether output exists and meets success criteria.
5. **Safe Packaging**: Returns structured `ToolResult` and `VerificationResult`.

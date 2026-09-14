# Communication Protocol Specification

The YANA IPC Protocol defines the strongly-typed message contract between the Desktop UI (React), the Desktop Shell (Tauri 2 / Rust), and the Agent (Python).

**Protocol Version**: `1.0.0`

## Message Envelope

Every message exchanged across layers adheres to the base envelope:

```json
{
  "version": "1.0.0",
  "id": "urn:uuid:6c9b02a2-3b2d-4bf5-8854-3e9a0f7d5498",
  "timestamp": "2026-09-14T07:15:00.000Z",
  "type": "<message_type>"
}
```

## Supported Message Types

| Type | Direction | Purpose |
| :--- | :--- | :--- |
| `user_message` | UI → Agent | Natural language command or query from the user. |
| `assistant_message` | Agent → UI | Conversational response from the assistant. |
| `task_started` | Agent → UI | Notification that a multi-step task has been initiated. |
| `task_status` | Agent → UI | Real-time status update (running, waiting_permission, etc.) |
| `tool_call` | Agent → Executor | Formal invocation of a registered tool with parameters. |
| `tool_result` | Executor → Agent | Execution output or safe error payload. |
| `verification_result` | Verifier → Agent | Post-execution verification confirming real-world success. |
| `permission_request` | Agent → UI | Request for user confirmation before executing a risky tool. |
| `permission_result` | UI → Agent | User decision (granted: true/false). |
| `error` | Any → UI | Safe error message conforming to standard error codes. |
| `task_completed` | Agent → UI | Notification of task completion with summary. |
| `task_cancelled` | UI/Agent → All | Notification of task cancellation with reason. |

## Standard Error Codes

Errors are standardized across TypeScript, Rust, and Python:

```typescript
export enum ErrorCode {
  VALIDATION_ERROR = "VALIDATION_ERROR",
  CONFIGURATION_ERROR = "CONFIGURATION_ERROR",
  AI_ERROR = "AI_ERROR",
  TOOL_ERROR = "TOOL_ERROR",
  PERMISSION_ERROR = "PERMISSION_ERROR",
  TIMEOUT_ERROR = "TIMEOUT_ERROR",
  NETWORK_ERROR = "NETWORK_ERROR",
  SYSTEM_ERROR = "SYSTEM_ERROR",
}
```

## Safe Error Payload Format

```json
{
  "code": "PERMISSION_ERROR",
  "message": "Permission denied for 'terminal.run_command' (Risk: HIGH): User explicitly denied permission.",
  "retryable": false,
  "taskId": "task-102",
  "toolId": "terminal.run_command"
}
```
*Note: Stack traces, internal file system paths, and raw credentials are never included in safe error payloads.*

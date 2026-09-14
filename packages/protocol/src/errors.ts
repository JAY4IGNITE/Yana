/**
 * Standardized Error Codes for YANA.
 * These error codes are unified across Desktop (Tauri/Rust), Frontend (React/TypeScript),
 * and Agent (Python/FastAPI).
 */
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

/**
 * Structured error payload that is safe to expose to the UI.
 * Stack traces and sensitive credentials must never be in user_message.
 */
export interface SafeErrorPayload {
  code: ErrorCode;
  message: string;
  details?: Record<string, unknown>;
  retryable?: boolean;
  taskId?: string;
  toolId?: string;
}

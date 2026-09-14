import { SafeErrorPayload } from "./errors.js";

/**
 * Protocol specification version.
 */
export const PROTOCOL_VERSION = "1.0.0";

/**
 * Discriminator types for all protocol messages.
 */
export type MessageType =
  | "user_message"
  | "assistant_message"
  | "task_started"
  | "task_status"
  | "tool_call"
  | "tool_result"
  | "verification_result"
  | "permission_request"
  | "permission_result"
  | "error"
  | "task_completed"
  | "task_cancelled"
  | "task_paused"
  | "task_resumed"
  | "stream_token"
  | "cancel_generation";

export type RiskLevel = "SAFE" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface BaseMessage {
  version: string;
  id: string;
  timestamp: string; // ISO-8601
}

export interface UserMessage extends BaseMessage {
  type: "user_message";
  content: string;
  attachments?: string[];
}

export interface AssistantMessage extends BaseMessage {
  type: "assistant_message";
  content: string;
  taskId?: string;
}

export interface TaskStarted extends BaseMessage {
  type: "task_started";
  taskId: string;
  description: string;
}

export type TaskStatusType =
  | "pending"
  | "planning"
  | "waiting_confirmation"
  | "waiting_permission"
  | "executing"
  | "running"
  | "verifying"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled";

export interface TaskStatus extends BaseMessage {
  type: "task_status";
  taskId: string;
  status: TaskStatusType;
  message: string;
  progress?: number; // 0.0 to 1.0
  currentStep?: number;
  totalSteps?: number;
}

export interface TaskStepPayload extends BaseMessage {
  type: "task_step";
  taskId: string;
  stepId: string;
  stepNumber: number;
  toolName: string;
  description: string;
  status: TaskStatusType;
  arguments?: Record<string, unknown>;
  output?: unknown;
  error?: SafeErrorPayload;
  verified?: boolean;
}

export interface ToolCall extends BaseMessage {
  type: "tool_call";
  taskId: string;
  tool: string;
  riskLevel: RiskLevel;
  arguments: Record<string, unknown>;
}

export interface ToolResult extends BaseMessage {
  type: "tool_result";
  taskId: string;
  toolCallId: string;
  success: boolean;
  output: unknown;
  error?: SafeErrorPayload;
}

export interface VerificationResult extends BaseMessage {
  type: "verification_result";
  taskId: string;
  toolCallId: string;
  verified: boolean;
  notes: string;
}

export interface PermissionRequest extends BaseMessage {
  type: "permission_request";
  taskId: string;
  toolCallId: string;
  tool: string;
  riskLevel: RiskLevel;
  description: string;
  arguments: Record<string, unknown>;
}

export interface PermissionResult extends BaseMessage {
  type: "permission_result";
  taskId: string;
  toolCallId: string;
  granted: boolean;
  reason?: string;
}

export interface ErrorMessage extends BaseMessage {
  type: "error";
  payload: SafeErrorPayload;
}

export interface TaskCompleted extends BaseMessage {
  type: "task_completed";
  taskId: string;
  summary: string;
}

export interface TaskCancelled extends BaseMessage {
  type: "task_cancelled";
  taskId: string;
  reason: string;
}

export interface StreamToken extends BaseMessage {
  type: "stream_token";
  sessionId: string;
  token: string;
  isComplete: boolean;
  messageId?: string;
}

export interface CancelGeneration extends BaseMessage {
  type: "cancel_generation";
  sessionId: string;
  reason?: string;
}

export interface TaskPaused extends BaseMessage {
  type: "task_paused";
  taskId: string;
  reason?: string;
  stepNumber?: number;
}

export interface TaskResumed extends BaseMessage {
  type: "task_resumed";
  taskId: string;
  stepNumber?: number;
}

export type ProtocolMessage =
  | UserMessage
  | AssistantMessage
  | TaskStarted
  | TaskStatus
  | ToolCall
  | ToolResult
  | VerificationResult
  | PermissionRequest
  | PermissionResult
  | ErrorMessage
  | TaskCompleted
  | TaskCancelled
  | TaskPaused
  | TaskResumed
  | StreamToken
  | CancelGeneration;

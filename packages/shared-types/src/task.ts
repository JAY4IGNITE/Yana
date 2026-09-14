export type TaskStatusType =
  | "pending"
  | "planning"
  | "waiting_confirmation"
  | "waiting_permission"
  | "executing"
  | "running"
  | "verifying"
  | "completed"
  | "failed"
  | "cancelled";

export interface TaskStep {
  id: string;
  taskId?: string;
  stepNumber: number;
  toolName: string;
  description: string;
  status: TaskStatusType;
  arguments?: Record<string, unknown>;
  output?: unknown;
  error?: string;
  verified?: boolean;
  retryCount?: number;
  toolCallId?: string;
  startedAt?: string;
  completedAt?: string;
}

export interface TaskItem {
  id: string;
  goal: string;
  title?: string;
  description?: string;
  status: TaskStatusType;
  steps: TaskStep[];
  currentStepIndex?: number;
  createdAt: string;
  updatedAt: string;
  summary?: string;
  error?: string;
}

export type Task = TaskItem;

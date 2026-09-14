export type TaskStatusType =
  | "pending"
  | "running"
  | "waiting_permission"
  | "verifying"
  | "completed"
  | "failed"
  | "cancelled";

export interface TaskStep {
  id: string;
  description: string;
  status: TaskStatusType;
  toolCallId?: string;
  output?: unknown;
  error?: string;
  startedAt?: string;
  completedAt?: string;
}

export interface TaskItem {
  id: string;
  title: string;
  description: string;
  status: TaskStatusType;
  steps: TaskStep[];
  createdAt: string;
  updatedAt: string;
}

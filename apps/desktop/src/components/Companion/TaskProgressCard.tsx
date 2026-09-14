import React from "react";
import { TaskStatusType } from "@yana/shared-types";
import { TaskStepPayload } from "@yana/protocol";
import {
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Ban,
  ShieldCheck,
  Terminal,
  AlertTriangle,
  Play,
  Pause,
} from "lucide-react";

export interface ActiveTaskState {
  id: string;
  goal: string;
  status: TaskStatusType;
  progress: number; // 0 to 1
  currentStep?: number;
  totalSteps?: number;
  stepDescription?: string;
  steps: TaskStepPayload[];
  error?: string;
}

export interface TaskProgressCardProps {
  task: ActiveTaskState;
  onPause?: () => void;
  onResume?: () => void;
  onCancel?: () => void;
  onDismiss?: () => void;
}

export const TaskProgressCard: React.FC<TaskProgressCardProps> = ({
  task,
  onPause,
  onResume,
  onCancel,
  onDismiss,
}) => {
  const isTerminal = ["completed", "failed", "cancelled"].includes(task.status);
  const percent = Math.min(Math.max(Math.round(task.progress * 100), 0), 100);

  const getStatusBadge = () => {
    switch (task.status) {
      case "planning":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-cyan-950/80 text-cyan-300 border border-cyan-800/60 shadow-sm">
            <Loader2 className="w-3 h-3 animate-spin text-cyan-400" />
            Planning
          </span>
        );
      case "executing":
      case "running":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-950/80 text-amber-300 border border-amber-800/60 shadow-sm">
            <Loader2 className="w-3 h-3 animate-spin text-amber-400" />
            Executing
          </span>
        );
      case "verifying":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-purple-950/80 text-purple-300 border border-purple-800/60 shadow-sm">
            <ShieldCheck className="w-3 h-3 text-purple-400 animate-pulse" />
            Verifying
          </span>
        );
      case "paused":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-950/80 text-amber-400 border border-amber-800/60 shadow-sm">
            <Pause className="w-3 h-3 text-amber-400" />
            Paused
          </span>
        );
      case "waiting_confirmation":
      case "waiting_permission":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-orange-950/80 text-orange-300 border border-orange-800/60 shadow-sm">
            <AlertTriangle className="w-3 h-3 text-orange-400" />
            Confirmation Needed
          </span>
        );
      case "completed":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-950/80 text-emerald-300 border border-emerald-800/60 shadow-sm">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            Completed
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-rose-950/80 text-rose-300 border border-rose-800/60 shadow-sm">
            <XCircle className="w-3 h-3 text-rose-400" />
            Failed
          </span>
        );
      case "cancelled":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-800 text-slate-400 border border-slate-700/60 shadow-sm">
            <Ban className="w-3 h-3 text-slate-400" />
            Cancelled
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-800 text-slate-300 border border-slate-700">
            <Clock className="w-3 h-3 text-slate-400" />
            Pending
          </span>
        );
    }
  };

  const getProgressBarColor = () => {
    switch (task.status) {
      case "completed":
        return "bg-gradient-to-r from-teal-500 to-emerald-400";
      case "failed":
        return "bg-gradient-to-r from-orange-500 to-rose-500";
      case "cancelled":
        return "bg-slate-600";
      case "paused":
        return "bg-gradient-to-r from-amber-500 to-yellow-400";
      case "verifying":
        return "bg-gradient-to-r from-cyan-500 to-purple-500";
      default:
        return "bg-gradient-to-r from-sky-500 to-cyan-400";
    }
  };

  return (
    <div
      data-testid="task-progress-card"
      className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800/90 backdrop-blur-md shadow-lg flex flex-col gap-3 my-2 text-slate-200 transition-all duration-200"
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-0.5 flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span
              data-testid="current-task-label"
              className="text-[10px] font-mono uppercase tracking-wider text-cyan-400 font-semibold"
            >
              Current task
            </span>
            {task.currentStep && task.totalSteps && (
              <span className="text-[10px] text-slate-400 font-mono">
                ({task.currentStep}/{task.totalSteps})
              </span>
            )}
          </div>
          <h4
            className="text-xs font-semibold text-slate-100 truncate"
            title={task.goal}
          >
            {task.goal}
          </h4>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {getStatusBadge()}

          {/* Pause / Resume Controls */}
          {!isTerminal && task.status === "paused" && onResume && (
            <button
              data-testid="resume-task-button"
              onClick={onResume}
              className="p-1 rounded-md text-emerald-400 hover:text-emerald-300 hover:bg-emerald-950/50 transition-colors"
              title="Resume task"
              aria-label="Resume task"
            >
              <Play className="w-3.5 h-3.5" />
            </button>
          )}

          {!isTerminal && task.status !== "paused" && onPause && (
            <button
              data-testid="pause-task-button"
              onClick={onPause}
              className="p-1 rounded-md text-amber-400 hover:text-amber-300 hover:bg-amber-950/50 transition-colors"
              title="Pause task"
              aria-label="Pause task"
            >
              <Pause className="w-3.5 h-3.5" />
            </button>
          )}

          {!isTerminal && onCancel && (
            <button
              data-testid="cancel-task-button"
              onClick={onCancel}
              className="p-1 rounded-md text-slate-400 hover:text-rose-400 hover:bg-slate-800/80 transition-colors"
              title="Cancel task"
              aria-label="Cancel task"
            >
              <Ban className="w-3.5 h-3.5" />
            </button>
          )}

          {isTerminal && onDismiss && (
            <button
              onClick={onDismiss}
              className="text-[10px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
            >
              Dismiss
            </button>
          )}
        </div>
      </div>

      {/* Progress Bar & Percentage */}
      <div className="flex flex-col gap-1.5">
        <div className="flex justify-between text-[11px] text-slate-400 font-mono">
          <span className="truncate">
            {task.stepDescription || (isTerminal ? "Execution finished" : "In progress...")}
          </span>
          <span className="font-semibold text-slate-300">{percent}%</span>
        </div>
        <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
          <div
            data-testid="task-progress-fill"
            className={`h-full transition-all duration-300 ease-out rounded-full ${getProgressBarColor()}`}
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>

      {/* Step Breakdown */}
      {task.steps.length > 0 && (
        <div className="flex flex-col gap-1.5 pt-2 border-t border-slate-800/60 max-h-48 overflow-y-auto pr-1">
          {task.steps.map((step, idx) => {
            const isStepCompleted = step.status === "completed";
            const isStepFailed = step.status === "failed";
            const isStepActive =
              step.status === "executing" ||
              step.status === "running" ||
              step.status === "verifying" ||
              step.status === "paused";
            const stepId = step.stepId || (step as any).step_id || `step-${idx}`;
            const stepNumber = step.stepNumber ?? (step as any).step_number ?? (idx + 1);
            const toolName = step.toolName || (step as any).tool_name || "";

            return (
              <div
                key={stepId}
                data-testid={`step-row-${stepNumber}`}
                className="flex items-center justify-between text-[11px] py-1 px-1.5 rounded bg-slate-950/40 border border-slate-800/40"
              >
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  {/* Phase 11 Step Status Markers: ✓, ●, ○, ✗ */}
                  {isStepCompleted ? (
                    <span
                      data-testid={`step-marker-${stepNumber}`}
                      className="text-emerald-400 font-bold font-mono text-[13px] flex-shrink-0 w-3.5 text-center leading-none"
                    >
                      ✓
                    </span>
                  ) : isStepActive ? (
                    <span
                      data-testid={`step-marker-${stepNumber}`}
                      className="text-amber-400 font-bold font-mono text-[13px] flex-shrink-0 w-3.5 text-center leading-none animate-pulse"
                    >
                      ●
                    </span>
                  ) : isStepFailed ? (
                    <span
                      data-testid={`step-marker-${stepNumber}`}
                      className="text-rose-400 font-bold font-mono text-[13px] flex-shrink-0 w-3.5 text-center leading-none"
                    >
                      ✗
                    </span>
                  ) : (
                    <span
                      data-testid={`step-marker-${stepNumber}`}
                      className="text-slate-500 font-bold font-mono text-[13px] flex-shrink-0 w-3.5 text-center leading-none"
                    >
                      ○
                    </span>
                  )}

                  <span className="font-mono text-[10px] text-slate-400 flex-shrink-0">
                    Step {stepNumber}
                  </span>

                  <span className="truncate text-slate-300">
                    {step.description || toolName}
                  </span>
                </div>

                <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-400 ml-2">
                  <Terminal className="w-3 h-3 text-slate-500" />
                  <span className="truncate max-w-[100px] text-slate-400">
                    {toolName}
                  </span>
                  {step.verified && (
                    <span className="text-emerald-400 text-[10px]" title="Output verified">
                      ✓
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Error Message Display */}
      {task.error && (
        <div className="p-2 rounded-lg bg-rose-950/50 border border-rose-900/60 text-[11px] text-rose-300 flex items-start gap-2">
          <AlertTriangle className="w-3.5 h-3.5 text-rose-400 flex-shrink-0 mt-0.5" />
          <span className="break-words">{task.error}</span>
        </div>
      )}
    </div>
  );
};

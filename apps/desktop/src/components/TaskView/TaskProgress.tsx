import React from "react";
import { TaskStatus } from "@yana/protocol";
import { Loader2, CheckCircle, AlertCircle, ShieldAlert, Cpu } from "lucide-react";

interface TaskProgressProps {
  currentStatus: TaskStatus | null;
  activeToolName?: string | null;
  onCancel?: (taskId: string) => void;
}

export const TaskProgress: React.FC<TaskProgressProps> = ({
  currentStatus,
  activeToolName,
  onCancel,
}) => {
  if (!currentStatus) return null;

  const getStatusIcon = () => {
    switch (currentStatus.status) {
      case "running":
        return <Loader2 className="w-4 h-4 text-amber-400 animate-spin" />;
      case "waiting_permission":
        return <ShieldAlert className="w-4 h-4 text-rose-400 animate-pulse" />;
      case "verifying":
        return <Cpu className="w-4 h-4 text-purple-400 animate-spin" />;
      case "completed":
        return <CheckCircle className="w-4 h-4 text-emerald-400" />;
      case "failed":
      case "cancelled":
        return <AlertCircle className="w-4 h-4 text-rose-400" />;
      default:
        return <Loader2 className="w-4 h-4 text-sky-400 animate-spin" />;
    }
  };

  return (
    <div
      data-testid="task-progress"
      className="p-3 bg-slate-900/90 border border-slate-800 rounded-xl space-y-2 text-xs shadow-lg"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          {getStatusIcon()}
          <span className="font-semibold text-slate-200 capitalize">
            Task: {currentStatus.status.replace("_", " ")}
          </span>
        </div>
        {onCancel && currentStatus.status === "running" && (
          <button
            onClick={() => onCancel(currentStatus.taskId)}
            className="text-[10px] text-rose-400 hover:text-rose-300 font-medium hover:underline"
          >
            Cancel
          </button>
        )}
      </div>

      <p className="text-slate-300 text-[11px] leading-snug">{currentStatus.message}</p>

      {activeToolName && (
        <div className="flex items-center space-x-1.5 text-[11px] text-sky-400 font-mono bg-sky-950/40 px-2 py-1 rounded border border-sky-800/40">
          <span>Tool:</span>
          <span className="font-semibold">{activeToolName}</span>
        </div>
      )}

      {currentStatus.progress !== undefined && currentStatus.progress !== null && (
        <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
          <div
            className="bg-sky-500 h-full transition-all duration-300 rounded-full"
            style={{ width: `${Math.min(Math.max(currentStatus.progress * 100, 5), 100)}%` }}
          />
        </div>
      )}
    </div>
  );
};

import React from "react";
import { PermissionRequest, RiskLevel } from "@yana/protocol";
import { ShieldAlert, AlertTriangle, ShieldCheck, XCircle, CheckCircle2 } from "lucide-react";

interface PermissionModalProps {
  request: PermissionRequest | null;
  onGrant: (toolCallId: string) => void;
  onDeny: (toolCallId: string, reason: string) => void;
}

export const PermissionModal: React.FC<PermissionModalProps> = ({
  request,
  onGrant,
  onDeny,
}) => {
  if (!request) return null;

  const getRiskBadge = (level: RiskLevel) => {
    switch (level) {
      case "CRITICAL":
        return {
          bg: "bg-red-500/20 text-red-400 border-red-500/40",
          icon: <ShieldAlert className="w-4 h-4 text-red-400" />,
        };
      case "HIGH":
        return {
          bg: "bg-rose-500/20 text-rose-400 border-rose-500/40",
          icon: <AlertTriangle className="w-4 h-4 text-rose-400" />,
        };
      case "MEDIUM":
        return {
          bg: "bg-amber-500/20 text-amber-400 border-amber-500/40",
          icon: <AlertTriangle className="w-4 h-4 text-amber-400" />,
        };
      case "LOW":
      default:
        return {
          bg: "bg-emerald-500/20 text-emerald-400 border-emerald-500/40",
          icon: <ShieldCheck className="w-4 h-4 text-emerald-400" />,
        };
    }
  };

  const badge = getRiskBadge(request.riskLevel);

  return (
    <div
      data-testid="permission-modal"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200"
    >
      <div className="w-full max-w-md bg-slate-900 border border-slate-700/80 rounded-2xl p-6 shadow-2xl space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center space-x-2">
            <span className="p-2 rounded-xl bg-slate-800/80">{badge.icon}</span>
            <h3 className="text-base font-semibold text-white">Permission Required</h3>
          </div>
          <span
            className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${badge.bg}`}
          >
            {request.riskLevel} RISK
          </span>
        </div>

        {/* Content */}
        <div className="space-y-3">
          <div>
            <p className="text-xs uppercase tracking-wider text-slate-400 font-medium">
              Requested Tool
            </p>
            <p className="text-sm font-mono font-semibold text-sky-300 mt-0.5">
              {request.tool}
            </p>
          </div>

          <div>
            <p className="text-xs uppercase tracking-wider text-slate-400 font-medium">
              Action Description
            </p>
            <p className="text-sm text-slate-200 mt-0.5">{request.description}</p>
          </div>

          {/* Arguments preview */}
          {request.arguments && Object.keys(request.arguments).length > 0 && (
            <div>
              <p className="text-xs uppercase tracking-wider text-slate-400 font-medium mb-1">
                Parameters
              </p>
              <pre className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 overflow-x-auto max-h-32">
                {JSON.stringify(request.arguments, null, 2)}
              </pre>
            </div>
          )}

          <p className="text-xs text-slate-400 italic">
            YANA enforces that the AI never directly controls the operating system.
            Authorize only if you trust this action.
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end space-x-3 pt-2">
          <button
            onClick={() => onDeny(request.toolCallId, "User rejected permission")}
            className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium transition"
          >
            <XCircle className="w-4 h-4" />
            <span>Deny</span>
          </button>
          <button
            onClick={() => onGrant(request.toolCallId)}
            className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 text-sm font-semibold shadow-lg shadow-sky-500/20 transition"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>Authorize & Execute</span>
          </button>
        </div>
      </div>
    </div>
  );
};

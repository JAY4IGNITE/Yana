import React, { useState, useEffect } from "react";
import {
  Brain,
  Cpu,
  CheckCircle2,
  AlertCircle,
  DownloadCloud,
  PowerOff,
  Eye,
  Zap,
  Activity,
  HardDrive,
} from "lucide-react";
import {
  agentClient,
  DecisionStatusPayload,
  DecisionSetupResponse,
} from "../../services/agentClient";

interface LocalDecisionsSettingsProps {
  agentConnected: boolean;
}

export const LocalDecisionsSettings: React.FC<LocalDecisionsSettingsProps> = ({
  agentConnected,
}) => {
  const [status, setStatus] = useState<DecisionStatusPayload | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [settingMode, setSettingMode] = useState<boolean>(false);
  const [settingUpModel, setSettingUpModel] = useState<boolean>(false);
  const [setupResult, setSetupResult] = useState<DecisionSetupResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchStatus = async () => {
    if (!agentConnected) {
      setLoading(false);
      return;
    }
    try {
      const data = await agentClient.getDecisionStatus();
      setStatus(data);
      setErrorMessage(null);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to load decision status");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, [agentConnected]);

  const handleModeChange = async (newMode: "off" | "shadow" | "active") => {
    setSettingMode(true);
    setErrorMessage(null);
    try {
      await agentClient.setDecisionMode(newMode);
      await fetchStatus();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to update decision mode");
    } finally {
      setSettingMode(false);
    }
  };

  const handleSetupModel = async () => {
    setSettingUpModel(true);
    setErrorMessage(null);
    setSetupResult(null);
    try {
      const res = await agentClient.setupDecisionModel();
      setSetupResult(res);
      await fetchStatus();
    } catch (err: any) {
      setErrorMessage(err.message || "Model provisioning failed");
    } finally {
      setSettingUpModel(false);
    }
  };

  if (!agentConnected) {
    return (
      <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-xs text-slate-400">
        Connect to YANA Agent to configure local decision routing.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-4 text-center text-xs text-slate-400 flex items-center justify-center space-x-2">
        <Activity className="w-4 h-4 animate-spin text-sky-400" />
        <span>Loading local decision engine status...</span>
      </div>
    );
  }

  const currentState = status?.state || "disabled";
  const currentMode = status?.mode || "off";

  return (
    <div className="space-y-3 text-xs" data-testid="local-decisions-settings">
      {/* Status banner */}
      <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Brain className="w-4 h-4 text-sky-400" />
            <span className="text-slate-300 font-medium">Local Decision Layer</span>
          </div>
          <div className="flex items-center space-x-1.5">
            {currentState === "ready" ? (
              <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full bg-emerald-950/80 text-emerald-400 border border-emerald-800/80 font-mono text-[10px]">
                <CheckCircle2 className="w-3 h-3" />
                <span>Ready</span>
              </span>
            ) : currentState === "starting" ? (
              <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full bg-sky-950/80 text-sky-400 border border-sky-800/80 font-mono text-[10px]">
                <Activity className="w-3 h-3 animate-spin" />
                <span>Starting</span>
              </span>
            ) : currentState === "degraded" ? (
              <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full bg-amber-950/80 text-amber-400 border border-amber-800/80 font-mono text-[10px]">
                <AlertCircle className="w-3 h-3" />
                <span>Degraded</span>
              </span>
            ) : currentState === "model_missing" ? (
              <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full bg-amber-950/80 text-amber-400 border border-amber-800/80 font-mono text-[10px]">
                <DownloadCloud className="w-3 h-3" />
                <span>Model Missing</span>
              </span>
            ) : currentState === "not_installed" ? (
              <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700 font-mono text-[10px]">
                <span>Lite (No PyTorch)</span>
              </span>
            ) : (
              <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700 font-mono text-[10px]">
                <PowerOff className="w-3 h-3" />
                <span>Disabled</span>
              </span>
            )}
          </div>
        </div>

        <p className="text-[11px] text-slate-400 leading-relaxed">
          {currentState === "ready" &&
            "Local 421M non-autoregressive decision model is resident in an isolated child process, evaluating complexity without cloud latency."}
          {currentState === "model_missing" &&
            "The optional PyTorch runtime is available, but model weights have not been downloaded. Setup is an explicit action."}
          {currentState === "not_installed" &&
            "Operating in standard Lite mode. PyTorch / Laya dependencies are excluded to maintain a small installation footprint."}
          {currentState === "starting" &&
            "The supervised child worker process is initializing offline weights."}
          {currentState === "degraded" &&
            "Worker encountered a fault or timeout. Safe heuristic fallback is handling requests while the process recovers."}
          {currentState === "disabled" &&
            "Local decision layer is switched off. All requests proceed through deterministic rules and default planning."}
        </p>

        {status?.model_commit && (
          <div className="flex items-center space-x-2 text-[10px] text-slate-500 font-mono">
            <Cpu className="w-3 h-3" />
            <span>Revision: {status.model_commit.slice(0, 12)}</span>
            <span>•</span>
            <span>{status.threads} CPU Threads</span>
          </div>
        )}
      </div>

      {/* Mode selection */}
      <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
        <label className="text-slate-300 font-medium block">Operating Mode</label>
        <div className="grid grid-cols-3 gap-2">
          <button
            onClick={() => handleModeChange("off")}
            disabled={settingMode}
            className={`p-2 rounded-lg border text-left transition ${
              currentMode === "off"
                ? "bg-sky-950/50 border-sky-500/80 text-white"
                : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200"
            }`}
          >
            <div className="flex items-center space-x-1.5 font-medium mb-1">
              <PowerOff className="w-3.5 h-3.5" />
              <span>Off</span>
            </div>
            <div className="text-[10px] text-slate-500 leading-tight">
              Reclaims all child process memory.
            </div>
          </button>

          <button
            onClick={() => handleModeChange("shadow")}
            disabled={settingMode || currentState === "not_installed" || currentState === "model_missing"}
            className={`p-2 rounded-lg border text-left transition ${
              currentMode === "shadow"
                ? "bg-sky-950/50 border-sky-500/80 text-white"
                : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200 disabled:opacity-40"
            }`}
          >
            <div className="flex items-center space-x-1.5 font-medium mb-1">
              <Eye className="w-3.5 h-3.5" />
              <span>Shadow</span>
            </div>
            <div className="text-[10px] text-slate-500 leading-tight">
              Observation only; cannot change plans.
            </div>
          </button>

          <button
            onClick={() => handleModeChange("active")}
            disabled={settingMode || !status?.active_permitted || currentState !== "ready"}
            className={`p-2 rounded-lg border text-left transition ${
              currentMode === "active"
                ? "bg-sky-950/50 border-sky-500/80 text-white"
                : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200 disabled:opacity-40"
            }`}
          >
            <div className="flex items-center space-x-1.5 font-medium mb-1">
              <Zap className="w-3.5 h-3.5" />
              <span>Active</span>
            </div>
            <div className="text-[10px] text-slate-500 leading-tight">
              Recommends provider tier on calibrated gates.
            </div>
          </button>
        </div>
      </div>

      {/* Explicit model setup action */}
      {currentState === "model_missing" && (
        <div className="p-3 rounded-xl bg-slate-950/60 border border-amber-900/40 space-y-2">
          <div className="flex items-center space-x-2 text-amber-400 font-medium">
            <HardDrive className="w-4 h-4" />
            <span>Model Weights Provisioning</span>
          </div>
          <p className="text-[11px] text-slate-400">
            Provisioning downloads the verified ~842 MB checkpoint commit to your local user cache.
            Requires at least 3.0 GB free disk space.
          </p>
          <button
            onClick={handleSetupModel}
            disabled={settingUpModel}
            className="w-full py-1.5 px-3 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-medium flex items-center justify-center space-x-2 transition disabled:opacity-50"
          >
            {settingUpModel ? (
              <>
                <Activity className="w-3.5 h-3.5 animate-spin" />
                <span>Checking disk space and staging checkpoint...</span>
              </>
            ) : (
              <>
                <DownloadCloud className="w-3.5 h-3.5" />
                <span>Setup Local Model Checkpoint</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* Setup result banner */}
      {setupResult && (
        <div className="p-2.5 rounded-lg bg-emerald-950/60 border border-emerald-800/80 text-emerald-300 text-[11px] flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
          <span>
            {setupResult.message} ({setupResult.disk_free_gb} GB free).
          </span>
        </div>
      )}

      {/* Error alert */}
      {errorMessage && (
        <div className="p-2.5 rounded-lg bg-rose-950/60 border border-rose-800/80 text-rose-300 text-[11px] flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Telemetry overview if recorded */}
      {status && status.telemetry_summary && status.telemetry_summary.total_recorded > 0 && (
        <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1 text-[11px]">
          <div className="text-slate-400 font-medium mb-1">Local Telemetry (Sanitized)</div>
          <div className="flex justify-between text-slate-300">
            <span>Decisions Evaluated:</span>
            <span className="font-mono">{status.telemetry_summary.total_recorded}</span>
          </div>
          <div className="flex justify-between text-slate-300">
            <span>Average Latency:</span>
            <span className="font-mono">{status.telemetry_summary.avg_latency_ms} ms</span>
          </div>
        </div>
      )}
    </div>
  );
};

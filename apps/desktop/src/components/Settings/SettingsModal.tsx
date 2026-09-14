import React from "react";
import { X, Server, Shield, Activity, HardDrive } from "lucide-react";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  agentConnected: boolean;
  agentUrl: string;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  agentConnected,
  agentUrl,
}) => {
  if (!isOpen) return null;

  return (
    <div
      data-testid="settings-modal"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200"
    >
      <div className="w-full max-w-sm bg-slate-900 border border-slate-700/80 rounded-2xl p-5 shadow-2xl space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center space-x-2">
            <Server className="w-4 h-4 text-sky-400" />
            <h3 className="text-sm font-semibold text-white">YANA Settings</h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition p-1 rounded-lg hover:bg-slate-800"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-3 text-xs">
          {/* Connection Status */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-slate-950/60 border border-slate-800">
            <div className="flex items-center space-x-2">
              <Activity className="w-4 h-4 text-slate-400" />
              <span className="text-slate-300 font-medium">Agent Service</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  agentConnected ? "bg-emerald-400 animate-pulse" : "bg-rose-500"
                }`}
              />
              <span className={agentConnected ? "text-emerald-400" : "text-rose-400"}>
                {agentConnected ? "Connected" : "Disconnected"}
              </span>
            </div>
          </div>

          {/* Endpoint */}
          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1">
            <span className="text-slate-400 font-medium">IPC Endpoint</span>
            <p className="font-mono text-slate-200 break-all">{agentUrl}</p>
          </div>

          {/* Security Principle */}
          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1">
            <div className="flex items-center space-x-1.5 text-sky-400">
              <Shield className="w-3.5 h-3.5" />
              <span className="font-medium">Security Principle</span>
            </div>
            <p className="text-slate-400 leading-relaxed text-[11px]">
              AI never controls the OS directly. All actions pass through permission gates and
              verification.
            </p>
          </div>

          {/* Database Engine */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-slate-950/60 border border-slate-800">
            <div className="flex items-center space-x-2">
              <HardDrive className="w-4 h-4 text-slate-400" />
              <span className="text-slate-300 font-medium">Storage Engine</span>
            </div>
            <span className="text-slate-400 font-mono">SQLite 3 (Async)</span>
          </div>
        </div>

        <div className="pt-2">
          <button
            onClick={onClose}
            className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

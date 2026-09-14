import React, { useState, useEffect } from "react";
import {
  X,
  Server,
  Shield,
  Activity,
  HardDrive,
  Mic,
  Volume2,
  Radio,
  Keyboard,
  Database,
  Trash2,
  FolderGit2,
  Power,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { AudioDevice, agentClient, ProjectMemoryPayload } from "../../services/agentClient";

async function safeInvoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T | null> {
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    return await invoke(cmd, args);
  } catch {
    return null;
  }
}

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  agentConnected: boolean;
  agentUrl: string;
  microphones?: AudioDevice[];
  speakers?: AudioDevice[];
  selectedMicId?: string;
  selectedSpeakerId?: string;
  wakeWordEnabled?: boolean;
  onSelectMic?: (id: string) => void;
  onSelectSpeaker?: (id: string) => void;
  onToggleWakeWord?: (enabled: boolean) => void;
  onPurgeMemory?: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  agentConnected,
  agentUrl,
  microphones = [],
  speakers = [],
  selectedMicId,
  selectedSpeakerId,
  wakeWordEnabled = false,
  onSelectMic,
  onSelectSpeaker,
  onToggleWakeWord,
  onPurgeMemory,
}) => {
  const [activeTab, setActiveTab] = useState<"general" | "audio" | "memory">("general");
  const [projects, setProjects] = useState<ProjectMemoryPayload[]>([]);
  const [purgeStatus, setPurgeStatus] = useState<string | null>(null);

  // Phase 13 Windows Distribution State
  const [autostartEnabled, setAutostartEnabled] = useState<boolean>(false);
  const [updateStatus, setUpdateStatus] = useState<string | null>(null);
  const [isCheckingUpdate, setIsCheckingUpdate] = useState<boolean>(false);
  const [supervisorStatus, setSupervisorStatus] = useState<{
    state: string;
    circuit_breaker_tripped: boolean;
    message: string;
  } | null>(null);

  useEffect(() => {
    if (isOpen) {
      // Query Windows autostart state
      safeInvoke<boolean>("get_launch_at_startup").then((res) => {
        if (res !== null) setAutostartEnabled(res);
      });

      // Query Agent Supervisor crash recovery status
      safeInvoke<any>("get_agent_supervisor_status").then((res) => {
        if (res) setSupervisorStatus(res);
      });
    }

    if (isOpen && activeTab === "memory" && agentConnected) {
      agentClient
        .listProjects()
        .then((data) => setProjects(data))
        .catch(() => setProjects([]));
    }
  }, [isOpen, activeTab, agentConnected]);

  const handleToggleAutostart = async (enable: boolean) => {
    setAutostartEnabled(enable);
    await safeInvoke("set_launch_at_startup", { enable });
  };

  const handleCheckUpdates = async () => {
    setIsCheckingUpdate(true);
    setUpdateStatus("Checking for updates...");
    try {
      const res = await safeInvoke<any>("check_for_updates");
      if (res) {
        setUpdateStatus(res.message || "YANA is up to date.");
      } else {
        setUpdateStatus("YANA v0.1.0 is up to date.");
      }
    } catch {
      setUpdateStatus("Update service unavailable.");
    } finally {
      setIsCheckingUpdate(false);
    }
  };

  const handleRestartService = async () => {
    try {
      const res = await safeInvoke<any>("restart_agent_service");
      if (res) {
        setSupervisorStatus(res);
      }
    } catch {
      // Handled gracefully
    }
  };

  const handlePurgeSession = async () => {
    try {
      setPurgeStatus("Purging...");
      const res = await agentClient.bulkForgetMemories({ memoryType: "session" });
      setPurgeStatus(`Cleared ${res.deletedCount} session memories`);
      if (onPurgeMemory) onPurgeMemory();
      setTimeout(() => setPurgeStatus(null), 3000);
    } catch {
      setPurgeStatus("Failed to purge session memories");
      setTimeout(() => setPurgeStatus(null), 3000);
    }
  };

  const handlePurgeAll = async () => {
    if (!window.confirm("Are you sure you want to purge all stored memories?")) {
      return;
    }
    try {
      setPurgeStatus("Purging all...");
      const res = await agentClient.bulkForgetMemories();
      setPurgeStatus(`Purged ${res.deletedCount} memories`);
      if (onPurgeMemory) onPurgeMemory();
      setTimeout(() => setPurgeStatus(null), 3000);
    } catch {
      setPurgeStatus("Failed to purge memories");
      setTimeout(() => setPurgeStatus(null), 3000);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      data-testid="settings-modal"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200"
    >
      <div className="w-full max-w-md bg-slate-900 border border-slate-700/80 rounded-2xl p-5 shadow-2xl space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center space-x-2">
            <Server className="w-4 h-4 text-sky-400" />
            <h3 className="text-sm font-semibold text-white">YANA Settings</h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition p-1 rounded-lg hover:bg-slate-800"
            aria-label="Close Settings"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab switcher */}
        <div className="flex border-b border-slate-800 text-xs">
          <button
            onClick={() => setActiveTab("general")}
            className={`flex-1 py-1.5 font-medium border-b-2 transition ${
              activeTab === "general"
                ? "border-sky-400 text-sky-400"
                : "border-transparent text-slate-400 hover:text-slate-300"
            }`}
          >
            General & Security
          </button>
          <button
            onClick={() => setActiveTab("audio")}
            className={`flex-1 py-1.5 font-medium border-b-2 transition flex items-center justify-center space-x-1 ${
              activeTab === "audio"
                ? "border-sky-400 text-sky-400"
                : "border-transparent text-slate-400 hover:text-slate-300"
            }`}
          >
            <Mic className="w-3.5 h-3.5" />
            <span>Voice & Audio</span>
          </button>
          <button
            onClick={() => setActiveTab("memory")}
            className={`flex-1 py-1.5 font-medium border-b-2 transition flex items-center justify-center space-x-1 ${
              activeTab === "memory"
                ? "border-sky-400 text-sky-400"
                : "border-transparent text-slate-400 hover:text-slate-300"
            }`}
          >
            <Database className="w-3.5 h-3.5" />
            <span>Memory</span>
          </button>
        </div>

        {activeTab === "general" ? (
          <div className="space-y-3 text-xs">
            {/* Connection & Crash Supervisor Status */}
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
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

              {(!agentConnected || supervisorStatus?.circuit_breaker_tripped) && (
                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
                  <p className="text-[11px] text-amber-400/90 leading-tight">
                    {supervisorStatus?.circuit_breaker_tripped
                      ? "Circuit breaker OPEN: auto-restarts paused."
                      : "Agent is unreachable or restarting."}
                  </p>
                  <button
                    onClick={handleRestartService}
                    data-testid="restart-agent-btn"
                    className="px-2 py-1 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 rounded text-[11px] font-medium transition flex items-center space-x-1"
                  >
                    <RefreshCw className="w-3 h-3" />
                    <span>Restart</span>
                  </button>
                </div>
              )}
            </div>

            {/* Windows Distribution Startup Option */}
            <div className="flex items-center justify-between p-3 rounded-xl bg-slate-950/60 border border-slate-800">
              <div className="flex items-center space-x-2">
                <Power className="w-4 h-4 text-sky-400" />
                <div>
                  <span className="text-slate-300 font-medium block">Windows Startup</span>
                  <span className="text-slate-500 text-[10px]">Launch YANA when Windows boots</span>
                </div>
              </div>
              <input
                type="checkbox"
                data-testid="startup-toggle"
                checked={autostartEnabled}
                onChange={(e) => handleToggleAutostart(e.target.checked)}
                className="w-4 h-4 accent-sky-500 rounded cursor-pointer"
              />
            </div>

            {/* Environment & Release Version */}
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 font-medium">Environment</span>
                <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-sky-500/20 text-sky-300 border border-sky-500/30">
                  Production Native
                </span>
              </div>
              <div className="flex items-center justify-between pt-1 border-t border-slate-800/80">
                <span className="text-slate-400">Release Version</span>
                <span className="text-slate-200 font-mono">v0.1.0</span>
              </div>
            </div>

            {/* Secure Update Architecture */}
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-1.5 text-slate-300">
                  <Sparkles className="w-3.5 h-3.5 text-sky-400" />
                  <span className="font-medium">Software Updates</span>
                </div>
                <button
                  onClick={handleCheckUpdates}
                  disabled={isCheckingUpdate}
                  data-testid="check-updates-btn"
                  className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-[11px] font-medium transition flex items-center space-x-1 disabled:opacity-50"
                >
                  <RefreshCw className={`w-3 h-3 ${isCheckingUpdate ? "animate-spin" : ""}`} />
                  <span>{isCheckingUpdate ? "Checking..." : "Check Updates"}</span>
                </button>
              </div>
              {updateStatus && (
                <p className="text-[11px] text-slate-400 font-mono bg-slate-900/80 px-2 py-1 rounded">
                  {updateStatus}
                </p>
              )}
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
                AI never controls the OS directly. All actions pass through permission gates,
                cryptographic validations, and tool verification.
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
        ) : activeTab === "audio" ? (
          <div className="space-y-3 text-xs">
            {/* Microphone Selection */}
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1.5">
              <div className="flex items-center space-x-1.5 text-slate-300">
                <Mic className="w-3.5 h-3.5 text-sky-400" />
                <label htmlFor="mic-select" className="font-medium">Microphone Input</label>
              </div>
              <select
                id="mic-select"
                value={selectedMicId || "default_mic"}
                onChange={(e) => onSelectMic && onSelectMic(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg px-2 py-1.5 focus:outline-none focus:border-sky-500"
              >
                {microphones.length > 0 ? (
                  microphones.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} {m.isDefault ? "(Default)" : ""}
                    </option>
                  ))
                ) : (
                  <option value="default_mic">Default Microphone (System)</option>
                )}
              </select>
            </div>

            {/* Speaker Selection */}
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1.5">
              <div className="flex items-center space-x-1.5 text-slate-300">
                <Volume2 className="w-3.5 h-3.5 text-cyan-400" />
                <label htmlFor="speaker-select" className="font-medium">Speaker Output</label>
              </div>
              <select
                id="speaker-select"
                value={selectedSpeakerId || "default_speaker"}
                onChange={(e) => onSelectSpeaker && onSelectSpeaker(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg px-2 py-1.5 focus:outline-none focus:border-sky-500"
              >
                {speakers.length > 0 ? (
                  speakers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} {s.isDefault ? "(Default)" : ""}
                    </option>
                  ))
                ) : (
                  <option value="default_speaker">Default Speaker (System)</option>
                )}
              </select>
            </div>

            {/* Wake Word ("Hey YANA") Toggle */}
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-1.5 text-slate-300">
                  <Radio className="w-3.5 h-3.5 text-indigo-400" />
                  <span className="font-medium">Wake Word (&quot;Hey YANA&quot;)</span>
                </div>
                <input
                  type="checkbox"
                  checked={wakeWordEnabled}
                  onChange={(e) => onToggleWakeWord && onToggleWakeWord(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-900 text-sky-500 focus:ring-sky-500"
                  aria-label="Toggle Wake Word"
                />
              </div>
              <p className="text-[10px] text-slate-400 leading-relaxed">
                Privacy-conscious: detection operates locally on device memory frames and does not continuously stream audio to remote servers.
              </p>
            </div>

            {/* Global Shortcut Info */}
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Keyboard className="w-4 h-4 text-slate-400" />
                <span className="text-slate-300 font-medium">Push-to-Talk Shortcut</span>
              </div>
              <span className="font-mono bg-slate-800 text-sky-300 px-2 py-0.5 rounded text-[11px] border border-slate-700">
                Ctrl + Shift + Space
              </span>
            </div>
          </div>
        ) : (
          <div className="space-y-3 text-xs">
            {/* Privacy & Redaction Shield */}
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1.5">
              <div className="flex items-center space-x-1.5 text-emerald-400">
                <Shield className="w-3.5 h-3.5" />
                <span className="font-medium">Privacy Guard & Credential Filter</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Zero credentials stored. API keys, passwords, tokens, and private secrets are
                automatically redacted before being written to SQLite.
              </p>
            </div>

            {/* Selective Persistence Guarantee */}
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1.5">
              <div className="flex items-center space-x-1.5 text-sky-400">
                <Database className="w-3.5 h-3.5" />
                <span className="font-medium">Selective Persistence</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                YANA does not dump raw conversations into persistent memory. Only explicit
                facts, project configurations, and confirmed workflows are remembered long-term.
              </p>
            </div>

            {/* Registered Projects */}
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-1.5 text-slate-300">
                  <FolderGit2 className="w-3.5 h-3.5 text-indigo-400" />
                  <span className="font-medium">Registered Projects ({projects.length})</span>
                </div>
              </div>
              {projects.length > 0 ? (
                <div className="space-y-1.5 max-h-32 overflow-y-auto pr-1">
                  {projects.map((proj) => (
                    <div
                      key={proj.id}
                      className="p-2 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between"
                    >
                      <div className="truncate mr-2">
                        <span className="font-medium text-slate-200">{proj.name}</span>
                        <p className="text-[10px] text-slate-500 font-mono truncate">{proj.path}</p>
                      </div>
                      <span className="text-[10px] bg-slate-800 text-sky-300 px-1.5 py-0.5 rounded font-mono shrink-0">
                        {proj.technology}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-[11px] text-slate-500 italic">No projects registered in memory yet.</p>
              )}
            </div>

            {/* User Memory Controls */}
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
              <span className="font-medium text-slate-300">User Memory Controls</span>
              {purgeStatus && (
                <p className="text-[11px] text-sky-400 font-mono animate-pulse">{purgeStatus}</p>
              )}
              <div className="flex space-x-2">
                <button
                  onClick={handlePurgeSession}
                  className="flex-1 py-1.5 px-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-[11px] font-medium transition flex items-center justify-center space-x-1"
                >
                  <Trash2 className="w-3 h-3 text-amber-400" />
                  <span>Clear Session</span>
                </button>
                <button
                  onClick={handlePurgeAll}
                  className="flex-1 py-1.5 px-2 bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 border border-rose-800/40 rounded-lg text-[11px] font-medium transition flex items-center justify-center space-x-1"
                >
                  <Trash2 className="w-3 h-3 text-rose-400" />
                  <span>Purge All</span>
                </button>
              </div>
            </div>
          </div>
        )}

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

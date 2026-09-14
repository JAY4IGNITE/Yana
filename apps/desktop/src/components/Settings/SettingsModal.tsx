import React, { useState } from "react";
import { X, Server, Shield, Activity, HardDrive, Mic, Volume2, Radio, Keyboard } from "lucide-react";
import { AudioDevice } from "../../services/agentClient";

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
}) => {
  const [activeTab, setActiveTab] = useState<"general" | "audio">("general");

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
        </div>

        {activeTab === "general" ? (
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
        ) : (
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

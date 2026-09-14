import React, { useState } from "react";
import { PetCompanion } from "./components/Pet/PetCompanion";
import { ChatFeed } from "./components/Chat/ChatFeed";
import { PermissionModal } from "./components/Permissions/PermissionModal";
import { TaskProgress } from "./components/TaskView/TaskProgress";
import { SettingsModal } from "./components/Settings/SettingsModal";
import { useProtocol } from "./hooks/useProtocol";
import { Settings, Sparkles, Wifi, WifiOff } from "lucide-react";

export const App: React.FC = () => {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const {
    petState,
    setPetState,
    petMood,
    messages,
    pendingPermission,
    currentTaskStatus,
    activeToolName,
    agentConnected,
    agentUrl,
    handleSendMessage,
    handleGrantPermission,
    handleDenyPermission,
  } = useProtocol();

  // Cycle pet state on user click for interactive fun
  const handlePetCycle = () => {
    const states = ["idle", "listening", "thinking", "success", "sleeping"] as const;
    const nextIdx = (states.indexOf(petState as any) + 1) % states.length;
    setPetState(states[nextIdx]);
  };

  return (
    <main className="flex flex-col h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden font-sans select-none border border-slate-800/80 rounded-2xl shadow-2xl">
      {/* Native-style Titlebar / Header */}
      <header className="h-11 px-4 flex items-center justify-between bg-slate-900/90 border-b border-slate-800/80 select-none cursor-move">
        <div className="flex items-center space-x-2">
          <div className="w-5 h-5 rounded-lg bg-sky-500/20 border border-sky-400/40 flex items-center justify-center">
            <Sparkles className="w-3 h-3 text-sky-400" />
          </div>
          <span className="text-xs font-bold tracking-wider text-slate-200">YANA</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
            v0.1.0
          </span>
        </div>

        <div className="flex items-center space-x-2">
          {/* Agent connection indicator */}
          <div
            className={`flex items-center space-x-1 text-[11px] px-2 py-0.5 rounded-full border ${
              agentConnected
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                : "bg-slate-800 text-slate-400 border-slate-700"
            }`}
            title={agentConnected ? "Agent Core Connected" : "Agent Core Offline (Mock Mode)"}
          >
            {agentConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            <span className="hidden sm:inline">{agentConnected ? "Online" : "Offline"}</span>
          </div>

          <button
            onClick={() => setSettingsOpen(true)}
            className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
            title="Open Settings"
          >
            <Settings className="w-3.5 h-3.5" />
          </button>
        </div>
      </header>

      {/* Main Companion Body */}
      <div className="flex-1 flex flex-col p-4 overflow-hidden space-y-3">
        {/* Animated Pet Companion Section */}
        <section aria-label="Animated AI Pet" className="flex-shrink-0 flex justify-center">
          <PetCompanion
            state={petState}
            mood={petMood}
            onPetClick={handlePetCycle}
          />
        </section>

        {/* Task Progress (if active) */}
        {currentTaskStatus && (
          <section aria-label="Task Status" className="flex-shrink-0 animate-in fade-in duration-200">
            <TaskProgress
              currentStatus={currentTaskStatus}
              activeToolName={activeToolName}
            />
          </section>
        )}

        {/* Interactive Chat & Command Area */}
        <section aria-label="Command Feed" className="flex-1 flex flex-col min-h-0">
          <ChatFeed
            messages={messages}
            onSendMessage={handleSendMessage}
            disabled={petState === "executing" || petState === "thinking"}
          />
        </section>
      </div>

      {/* Permission Gate Modal */}
      <PermissionModal
        request={pendingPermission}
        onGrant={handleGrantPermission}
        onDeny={handleDenyPermission}
      />

      {/* Settings Modal */}
      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        agentConnected={agentConnected}
        agentUrl={agentUrl}
      />
    </main>
  );
};

export default App;

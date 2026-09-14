import React, { useEffect } from "react";
import { CollapsedPetView } from "./components/Companion/CollapsedPetView";
import { ExpandedAssistantView } from "./components/Companion/ExpandedAssistantView";
import { PermissionModal } from "./components/Permissions/PermissionModal";
import { SettingsModal } from "./components/Settings/SettingsModal";
import { useProtocol } from "./hooks/useProtocol";

export const App: React.FC = () => {
  const {
    petState,
    petMood,
    windowMode,
    scale,
    alwaysOnTop,
    messages,
    isListening,
    isSpeaking,
    pendingPermission,
    agentConnected,
    agentUrl,
    settingsOpen,
    setSettingsOpen,
    expandWindow,
    collapseWindow,
    toggleAlwaysOnTop,
    cycleScale,
    handleSendMessage,
    handleToggleListening,
    handleStop,
    handleGrantPermission,
    handleDenyPermission,
  } = useProtocol();

  // Escape key collapses expanded assistant back to floating pet
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && windowMode === "expanded") {
        collapseWindow();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [windowMode, collapseWindow]);

  return (
    <div className="w-screen h-screen overflow-hidden select-none bg-transparent">
      {/* Dual Mode Rendering */}
      {windowMode === "collapsed" ? (
        <CollapsedPetView
          petState={petState}
          petMood={petMood}
          scale={scale}
          alwaysOnTop={alwaysOnTop}
          onExpand={expandWindow}
          onToggleAlwaysOnTop={toggleAlwaysOnTop}
          onCycleScale={cycleScale}
        />
      ) : (
        <ExpandedAssistantView
          petState={petState}
          petMood={petMood}
          messages={messages}
          isListening={isListening}
          isSpeaking={isSpeaking}
          alwaysOnTop={alwaysOnTop}
          agentConnected={agentConnected}
          onCollapse={collapseWindow}
          onToggleAlwaysOnTop={toggleAlwaysOnTop}
          onSendMessage={handleSendMessage}
          onToggleListening={handleToggleListening}
          onStop={handleStop}
          onOpenSettings={() => setSettingsOpen(true)}
        />
      )}

      {/* Permission Confirmation Dialog */}
      <PermissionModal
        request={pendingPermission}
        onGrant={handleGrantPermission}
        onDeny={handleDenyPermission}
      />

      {/* Settings Modal (Placeholder View as specified) */}
      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        agentConnected={agentConnected}
        agentUrl={agentUrl}
      />
    </div>
  );
};

export default App;

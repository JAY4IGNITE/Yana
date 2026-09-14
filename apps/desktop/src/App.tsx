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
    conversations,
    currentConversationId,
    isListening,
    isSpeaking,
    isGenerating,
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
    handleRetry,
    handleClearConversation,
    handleNewConversation,
    loadConversation,
    handleGrantPermission,
    handleDenyPermission,
    activeTask,
    handleCancelActiveTask,
    handleDismissActiveTask,
    microphones,
    speakers,
    selectedMicId,
    selectedSpeakerId,
    wakeWordEnabled,
    handleSelectMic,
    handleSelectSpeaker,
    handleToggleWakeWord,
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
          conversations={conversations}
          currentConversationId={currentConversationId}
          isListening={isListening}
          isSpeaking={isSpeaking}
          isGenerating={isGenerating}
          alwaysOnTop={alwaysOnTop}
          agentConnected={agentConnected}
          activeTask={activeTask}
          onCancelTask={handleCancelActiveTask}
          onDismissTask={handleDismissActiveTask}
          onCollapse={collapseWindow}
          onToggleAlwaysOnTop={toggleAlwaysOnTop}
          onSendMessage={handleSendMessage}
          onToggleListening={handleToggleListening}
          onStop={handleStop}
          onRetry={handleRetry}
          onClearConversation={handleClearConversation}
          onNewConversation={handleNewConversation}
          onSelectConversation={loadConversation}
          onOpenSettings={() => setSettingsOpen(true)}
        />
      )}

      {/* Permission Confirmation Dialog */}
      <PermissionModal
        request={pendingPermission}
        onGrant={handleGrantPermission}
        onDeny={handleDenyPermission}
      />

      {/* Settings Modal with General & Audio hardware controls */}
      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        agentConnected={agentConnected}
        agentUrl={agentUrl}
        microphones={microphones}
        speakers={speakers}
        selectedMicId={selectedMicId}
        selectedSpeakerId={selectedSpeakerId}
        wakeWordEnabled={wakeWordEnabled}
        onSelectMic={handleSelectMic}
        onSelectSpeaker={handleSelectSpeaker}
        onToggleWakeWord={handleToggleWakeWord}
      />
    </div>
  );
};

export default App;

import React, { useState, useRef, useEffect } from "react";
import { PetCompanion } from "../Pet/PetCompanion";
import { PetState, PetMood, ConversationMessage, ConversationSummary } from "@yana/shared-types";
import {
  Mic,
  MicOff,
  Square,
  Send,
  Minimize2,
  Pin,
  PinOff,
  Settings,
  Bot,
  User,
  AlertCircle,
  RotateCcw,
  Trash2,
  Plus,
  History,
  X,
} from "lucide-react";
import { TaskProgressCard, ActiveTaskState } from "./TaskProgressCard";

interface ExpandedAssistantViewProps {
  petState: PetState;
  petMood?: PetMood;
  messages: ConversationMessage[];
  conversations?: ConversationSummary[];
  currentConversationId?: string;
  isListening: boolean;
  isSpeaking: boolean;
  isGenerating?: boolean;
  alwaysOnTop: boolean;
  agentConnected: boolean;
  activeTask?: ActiveTaskState | null;
  onCancelTask?: () => void;
  onDismissTask?: () => void;
  onCollapse: () => void;
  onToggleAlwaysOnTop: () => void;
  onSendMessage: (text: string) => void;
  /** Launch an autonomous agent task (plan → tool → verify) instead of plain chat. */
  onRunTask?: (goal: string) => void;
  /** Current routing mode; "agent" sends input to onRunTask, "chat" to onSendMessage. */
  agentMode?: "chat" | "agent";
  onAgentModeChange?: (mode: "chat" | "agent") => void;
  onToggleListening: () => void;
  onStop: () => void;
  onRetry?: () => void;
  onClearConversation?: () => void;
  onNewConversation?: () => void;
  onSelectConversation?: (id: string) => void;
  onOpenSettings: () => void;
}

export const ExpandedAssistantView: React.FC<ExpandedAssistantViewProps> = ({
  petState,
  petMood = "happy",
  messages,
  conversations = [],
  currentConversationId,
  isListening,
  isSpeaking,
  isGenerating = false,
  alwaysOnTop,
  agentConnected,
  activeTask,
  onCancelTask,
  onDismissTask,
  onCollapse,
  onToggleAlwaysOnTop,
  onSendMessage,
  onRunTask,
  agentMode = "chat",
  onAgentModeChange,
  onToggleListening,
  onStop,
  onRetry,
  onClearConversation,
  onNewConversation,
  onSelectConversation,
  onOpenSettings,
}) => {
  const [input, setInput] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-focus input when opened
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Auto-scroll conversation on update
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isGenerating) return;
    const text = input.trim();
    // Route by explicit mode: agentic tasks go through the plan→tool→verify loop
    // (which can pause for consent); chat goes straight to the LLM.
    if (agentMode === "agent" && onRunTask) {
      onRunTask(text);
    } else {
      onSendMessage(text);
    }
    setInput("");
  };

  const getStatusText = () => {
    if (!agentConnected) return "Offline (Simulation)";
    if (isListening) return "Listening...";
    if (isGenerating && isSpeaking) return "Streaming Response...";
    if (isGenerating) return "Thinking...";
    if (petState === "executing") return "Executing Tool...";
    if (petState === "error") return "Attention Needed";
    return "Online & Ready";
  };

  return (
    <div
      data-testid="expanded-assistant-view"
      className="w-full h-full flex flex-col glass-card rounded-2xl overflow-hidden select-none border border-slate-700/60 shadow-2xl animate-in fade-in zoom-in-95 duration-200 relative"
    >
      {/* Top Header / Drag Region */}
      <header
        data-tauri-drag-region
        className="h-10 px-3 flex items-center justify-between bg-slate-900/95 border-b border-slate-800/80 cursor-move flex-shrink-0"
      >
        <div className="flex items-center space-x-2">
          <span className="text-xs font-bold tracking-wider text-slate-100">YANA</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 text-sky-400 font-mono border border-slate-700/50">
            v0.2.0
          </span>
        </div>

        <div className="flex items-center space-x-1">
          {/* Conversation History Drawer Button */}
          <button
            onClick={() => setShowHistory((prev) => !prev)}
            className={`p-1 rounded-lg transition ${
              showHistory
                ? "text-sky-400 bg-sky-950/60 border border-sky-800/50"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
            }`}
            title="Chat Sessions"
            aria-label="Toggle Sessions History"
          >
            <History className="w-3.5 h-3.5" />
          </button>

          {/* New Chat Button */}
          {onNewConversation && (
            <button
              onClick={() => {
                setShowHistory(false);
                onNewConversation();
              }}
              className="p-1 rounded-lg text-slate-400 hover:text-sky-400 hover:bg-slate-800 transition"
              title="New Chat Session"
              aria-label="New Chat"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          )}

          {/* Clear Messages */}
          {onClearConversation && messages.length > 0 && (
            <button
              onClick={onClearConversation}
              className="p-1 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition"
              title="Clear Messages"
              aria-label="Clear Messages"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}

          <div className="w-[1px] h-3.5 bg-slate-800 mx-0.5" />

          {/* Always-on-top button */}
          <button
            onClick={onToggleAlwaysOnTop}
            className={`p-1 rounded-lg transition ${
              alwaysOnTop
                ? "text-sky-400 bg-sky-950/60 border border-sky-800/50"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
            }`}
            title={alwaysOnTop ? "Pinned (Always on top)" : "Pin to top"}
            aria-label="Toggle Pin"
          >
            {alwaysOnTop ? <Pin className="w-3.5 h-3.5" /> : <PinOff className="w-3.5 h-3.5" />}
          </button>

          {/* Settings */}
          <button
            onClick={onOpenSettings}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
            title="Settings"
            aria-label="Settings"
          >
            <Settings className="w-3.5 h-3.5" />
          </button>

          {/* Collapse to Pet button */}
          <button
            onClick={onCollapse}
            className="p-1 rounded-lg text-slate-400 hover:text-sky-400 hover:bg-slate-800 transition"
            title="Collapse to floating pet (Esc)"
            aria-label="Collapse Interface"
          >
            <Minimize2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </header>

      {/* History Drawer Overlay */}
      {showHistory && (
        <div className="absolute inset-x-0 top-10 bottom-0 z-30 bg-slate-950/95 backdrop-blur-md border-b border-slate-800 p-3 flex flex-col animate-in fade-in slide-in-from-top-2 duration-150">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800 text-xs">
            <span className="font-semibold text-slate-200">Conversation Sessions</span>
            <button
              onClick={() => setShowHistory(false)}
              className="p-1 rounded text-slate-400 hover:text-white"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto space-y-1.5 py-2">
            {conversations.length === 0 ? (
              <div className="p-4 text-center text-xs text-slate-500">No saved sessions yet.</div>
            ) : (
              conversations.map((c) => {
                const isActive = c.id === currentConversationId;
                return (
                  <button
                    key={c.id}
                    onClick={() => {
                      onSelectConversation?.(c.id);
                      setShowHistory(false);
                    }}
                    className={`w-full text-left p-2 rounded-xl text-xs flex items-center justify-between transition border ${
                      isActive
                        ? "bg-sky-950/50 border-sky-600/50 text-sky-200"
                        : "bg-slate-900/60 border-slate-800/80 text-slate-300 hover:bg-slate-800/70"
                    }`}
                  >
                    <div className="truncate flex-1 pr-2">
                      <p className="font-medium truncate">{c.title}</p>
                      <p className="text-[10px] text-slate-500">
                        {new Date(c.updatedAt).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </p>
                    </div>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono">
                      {c.messageCount}
                    </span>
                  </button>
                );
              })
            )}
          </div>

          {onNewConversation && (
            <button
              onClick={() => {
                onNewConversation();
                setShowHistory(false);
              }}
              className="w-full py-2 px-3 mt-2 rounded-xl bg-sky-500/20 border border-sky-500/40 text-sky-300 text-xs font-medium hover:bg-sky-500/30 transition flex items-center justify-center space-x-1.5"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Start New Conversation</span>
            </button>
          )}
        </div>
      )}

      {/* Pet Header Section */}
      <div className="flex-shrink-0 flex flex-col items-center justify-center pt-2 pb-1 border-b border-slate-800/40 bg-slate-950/20">
        <PetCompanion
          state={petState}
          mood={petMood}
          scale="small"
          showBadge={false}
        />
        {/* Status indicator bar */}
        <div className="mt-1 flex items-center space-x-1.5 text-[11px] font-medium text-slate-400">
          <span
            className={`w-2 h-2 rounded-full ${
              petState === "error"
                ? "bg-rose-500 animate-pulse"
                : petState === "executing"
                ? "bg-amber-400 animate-spin"
                : isListening
                ? "bg-sky-400 animate-ping"
                : isSpeaking || isGenerating
                ? "bg-cyan-400 animate-pulse"
                : "bg-emerald-400"
            }`}
          />
          <span>{getStatusText()}</span>
        </div>
      </div>

      {/* Autonomous Agent Task Card */}
      {activeTask && (
        <div className="px-3 pt-2 flex-shrink-0">
          <TaskProgressCard
            task={activeTask}
            onCancel={onCancelTask}
            onDismiss={onDismissTask}
          />
        </div>
      )}

      {/* Conversation Area */}
      <div
        ref={scrollRef}
        className="flex-1 p-3.5 overflow-y-auto space-y-3 min-h-[140px]"
      >
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-4 text-slate-400">
            <p className="text-sm font-semibold text-slate-200">How can I help you today?</p>
            <p className="text-xs text-slate-500 mt-1">
              Type a prompt or dictate. I can answer questions and assist with your workflow.
            </p>
          </div>
        ) : (
          messages.map((m, idx) => {
            const isUser = m.role === "user";
            const isError = m.role === "error";
            const isLast = idx === messages.length - 1;
            const isStreaming = m.metadata?.isStreaming || (isLast && isGenerating && !isUser);

            return (
              <div
                key={m.id}
                className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
              >
                <div
                  className={`flex items-start space-x-2 max-w-[88%] ${
                    isUser ? "flex-row-reverse space-x-reverse" : ""
                  }`}
                >
                  <div
                    className={`w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 text-xs ${
                      isUser
                        ? "bg-sky-500/20 text-sky-300 border border-sky-500/30"
                        : isError
                        ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                        : "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                    }`}
                  >
                    {isUser ? (
                      <User className="w-3 h-3" />
                    ) : isError ? (
                      <AlertCircle className="w-3 h-3" />
                    ) : (
                      <Bot className="w-3 h-3" />
                    )}
                  </div>

                  <div
                    className={`rounded-2xl px-3 py-2 text-xs leading-relaxed transition ${
                      isUser
                        ? "bg-sky-500 text-slate-950 font-medium rounded-tr-none shadow-md shadow-sky-950/30"
                        : isError
                        ? "bg-rose-950/60 text-rose-200 border border-rose-800/60 rounded-tl-none"
                        : "bg-slate-900/90 border border-slate-800 text-slate-200 rounded-tl-none shadow-sm"
                    }`}
                  >
                    {m.content}
                    {isStreaming && (
                      <span className="inline-block w-1.5 h-3 ml-1 bg-cyan-400 animate-pulse align-middle" />
                    )}
                  </div>
                </div>

                {/* Actions under bubble: retry */}
                {((isError && onRetry) || (!isUser && isLast && !isGenerating && onRetry)) && (
                  <button
                    onClick={onRetry}
                    className="mt-1 ml-8 flex items-center space-x-1 text-[10px] text-slate-500 hover:text-sky-400 transition"
                    title="Retry Response"
                  >
                    <RotateCcw className="w-3 h-3" />
                    <span>Retry</span>
                  </button>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Input & Controls Bottom Bar */}
      <form
        onSubmit={handleSubmit}
        className="p-2.5 bg-slate-900/90 border-t border-slate-800/80 flex items-center space-x-2 flex-shrink-0"
      >
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={isGenerating ? "YANA is responding..." : "Ask YANA..."}
          disabled={isGenerating}
          className="flex-1 bg-slate-950/90 border border-slate-800 focus:border-sky-500/60 focus:outline-none focus:ring-1 focus:ring-sky-500/30 text-slate-200 placeholder-slate-500 text-xs rounded-xl px-3 py-2 transition disabled:opacity-60"
        />

        {/* Microphone Toggle Button */}
        <button
          type="button"
          onClick={onToggleListening}
          disabled={isGenerating}
          className={`p-2 rounded-xl border transition flex items-center justify-center ${
            isListening
              ? "bg-sky-500 text-slate-950 border-sky-400 animate-pulse"
              : "bg-slate-800/80 hover:bg-slate-700 text-slate-300 border-slate-700 disabled:opacity-50"
          }`}
          title={isListening ? "Stop listening" : "Voice command (Dictate)"}
          aria-label="Toggle Microphone"
        >
          {isListening ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
        </button>

        {/* Stop / Cancel Button (Active during generation or voice listening) */}
        {(isGenerating || isSpeaking || isListening || petState === "executing") && (
          <button
            type="button"
            onClick={onStop}
            className="p-2 rounded-xl bg-rose-500/20 hover:bg-rose-500 text-rose-300 hover:text-white border border-rose-500/40 transition flex items-center justify-center animate-pulse"
            title="Stop generation (Esc)"
            aria-label="Stop Action"
          >
            <Square className="w-3.5 h-3.5 fill-current" />
          </button>
        )}

        {/* Send Button */}
        <button
          type="submit"
          disabled={!input.trim() || isGenerating}
          className="p-2 rounded-xl bg-sky-500 hover:bg-sky-400 disabled:opacity-40 disabled:hover:bg-sky-500 text-slate-950 transition flex items-center justify-center font-medium"
          title="Send command"
          aria-label="Send Message"
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </form>
    </div>
  );
};

import React, { useState, useRef, useEffect } from "react";
import { PetCompanion } from "../Pet/PetCompanion";
import { PetState, PetMood, ConversationMessage } from "@yana/shared-types";
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
} from "lucide-react";

interface ExpandedAssistantViewProps {
  petState: PetState;
  petMood?: PetMood;
  messages: ConversationMessage[];
  isListening: boolean;
  isSpeaking: boolean;
  alwaysOnTop: boolean;
  agentConnected: boolean;
  onCollapse: () => void;
  onToggleAlwaysOnTop: () => void;
  onSendMessage: (text: string) => void;
  onToggleListening: () => void;
  onStop: () => void;
  onOpenSettings: () => void;
}

export const ExpandedAssistantView: React.FC<ExpandedAssistantViewProps> = ({
  petState,
  petMood = "happy",
  messages,
  isListening,
  isSpeaking,
  alwaysOnTop,
  agentConnected,
  onCollapse,
  onToggleAlwaysOnTop,
  onSendMessage,
  onToggleListening,
  onStop,
  onOpenSettings,
}) => {
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-focus input when opened
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Auto-scroll conversation
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    onSendMessage(input.trim());
    setInput("");
  };

  const getStatusText = () => {
    if (!agentConnected) return "Offline (Local)";
    if (isListening) return "Listening...";
    if (isSpeaking) return "Speaking...";
    if (petState === "thinking") return "Thinking...";
    if (petState === "executing") return "Executing...";
    return "Ready";
  };

  return (
    <div
      data-testid="expanded-assistant-view"
      className="w-full h-full flex flex-col glass-card rounded-2xl overflow-hidden select-none border border-slate-700/60 shadow-2xl animate-in fade-in zoom-in-95 duration-200"
    >
      {/* Top Header / Drag Region */}
      <header
        data-tauri-drag-region
        className="h-10 px-3 flex items-center justify-between bg-slate-900/90 border-b border-slate-800/80 cursor-move flex-shrink-0"
      >
        <div className="flex items-center space-x-2">
          <span className="text-xs font-bold tracking-wider text-slate-100">YANA</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-400 font-mono">
            Companion
          </span>
        </div>

        <div className="flex items-center space-x-1.5">
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
                : isSpeaking
                ? "bg-cyan-400 animate-pulse"
                : "bg-emerald-400"
            }`}
          />
          <span>{getStatusText()}</span>
        </div>
      </div>

      {/* Conversation Area */}
      <div
        ref={scrollRef}
        className="flex-1 p-3.5 overflow-y-auto space-y-2.5 min-h-[140px]"
      >
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-4 text-slate-400">
            <p className="text-sm font-semibold text-slate-200">How can I help you today?</p>
            <p className="text-xs text-slate-500 mt-1">
              Ask anything or use the microphone to dictate.
            </p>
          </div>
        ) : (
          messages.map((m) => {
            const isUser = m.role === "user";
            const isError = m.role === "error";

            return (
              <div
                key={m.id}
                className={`flex items-start space-x-2 ${isUser ? "flex-row-reverse space-x-reverse" : ""}`}
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
                  {isUser ? <User className="w-3 h-3" /> : isError ? <AlertCircle className="w-3 h-3" /> : <Bot className="w-3 h-3" />}
                </div>

                <div
                  className={`max-w-[82%] rounded-xl px-3 py-1.5 text-xs leading-relaxed ${
                    isUser
                      ? "bg-sky-500 text-slate-950 font-medium"
                      : isError
                      ? "bg-rose-950/60 text-rose-200 border border-rose-800/60"
                      : "bg-slate-900 border border-slate-800 text-slate-200"
                  }`}
                >
                  {m.content}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Input & Controls Bottom Bar */}
      <form
        onSubmit={handleSubmit}
        className="p-2.5 bg-slate-900/80 border-t border-slate-800/80 flex items-center space-x-2 flex-shrink-0"
      >
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask YANA..."
          className="flex-1 bg-slate-950/90 border border-slate-800 focus:border-sky-500/60 focus:outline-none focus:ring-1 focus:ring-sky-500/30 text-slate-200 placeholder-slate-500 text-xs rounded-xl px-3 py-2 transition"
        />

        {/* Microphone Toggle Button */}
        <button
          type="button"
          onClick={onToggleListening}
          className={`p-2 rounded-xl border transition flex items-center justify-center ${
            isListening
              ? "bg-sky-500 text-slate-950 border-sky-400 animate-pulse"
              : "bg-slate-800/80 hover:bg-slate-700 text-slate-300 border-slate-700"
          }`}
          title={isListening ? "Stop listening" : "Voice command (Dictate)"}
          aria-label="Toggle Microphone"
        >
          {isListening ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
        </button>

        {/* Stop Button (Cancels speaking/task) */}
        {(isSpeaking || isListening || petState === "executing") && (
          <button
            type="button"
            onClick={onStop}
            className="p-2 rounded-xl bg-rose-500/20 hover:bg-rose-500 text-rose-300 hover:text-white border border-rose-500/40 transition flex items-center justify-center"
            title="Stop active action"
            aria-label="Stop Action"
          >
            <Square className="w-3.5 h-3.5 fill-current" />
          </button>
        )}

        {/* Send Button */}
        <button
          type="submit"
          disabled={!input.trim()}
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

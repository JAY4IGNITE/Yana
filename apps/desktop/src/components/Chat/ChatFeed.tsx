import React, { useState } from "react";
import { Send, Bot, User, AlertCircle, Sparkles } from "lucide-react";

export type DisplayMessage =
  | { id: string; role: "user"; content: string; timestamp: string }
  | { id: string; role: "assistant"; content: string; timestamp: string }
  | { id: string; role: "error"; content: string; timestamp: string };

interface ChatFeedProps {
  messages: DisplayMessage[];
  onSendMessage: (text: string) => void;
  disabled?: boolean;
}

export const ChatFeed: React.FC<ChatFeedProps> = ({
  messages,
  onSendMessage,
  disabled = false,
}) => {
  const [input, setInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || disabled) return;
    onSendMessage(input.trim());
    setInput("");
  };

  const quickCommands = [
    "Open Notepad",
    "Check system status",
    "List available tools",
  ];

  return (
    <div className="flex flex-col h-full bg-slate-950/40 rounded-2xl border border-slate-800/80 overflow-hidden">
      {/* Messages Scroll Area */}
      <div className="flex-1 p-4 overflow-y-auto space-y-3 min-h-[160px] max-h-[260px]">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-4 text-slate-400">
            <Sparkles className="w-8 h-8 text-sky-400/60 mb-2 animate-pulse" />
            <p className="text-sm font-medium text-slate-300">How can YANA help you?</p>
            <p className="text-xs text-slate-500 mt-1">
              Ask a question or try one of the quick actions below.
            </p>
          </div>
        ) : (
          messages.map((m) => {
            const isUser = m.role === "user";
            const isError = m.role === "error";

            return (
              <div
                key={m.id}
                className={`flex items-start space-x-2.5 ${isUser ? "flex-row-reverse space-x-reverse" : ""}`}
              >
                <div
                  className={`w-7 h-7 rounded-xl flex items-center justify-center flex-shrink-0 text-xs ${
                    isUser
                      ? "bg-sky-500/20 text-sky-300 border border-sky-500/30"
                      : isError
                        ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                        : "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                  }`}
                >
                  {isUser ? <User className="w-3.5 h-3.5" /> : isError ? <AlertCircle className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
                </div>

                <div
                  className={`max-w-[80%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${
                    isUser
                      ? "bg-sky-500 text-slate-950 font-medium"
                      : isError
                        ? "bg-rose-950/50 text-rose-200 border border-rose-800/50"
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

      {/* Quick Action Chips */}
      {messages.length === 0 && (
        <div className="px-3 pb-2 flex flex-wrap gap-1.5 justify-center">
          {quickCommands.map((cmd) => (
            <button
              key={cmd}
              onClick={() => onSendMessage(cmd)}
              className="text-xs px-2.5 py-1 rounded-full bg-slate-900/80 hover:bg-slate-800 text-slate-300 border border-slate-800 transition"
            >
              {cmd}
            </button>
          ))}
        </div>
      )}

      {/* Input Box */}
      <form
        onSubmit={handleSubmit}
        className="p-3 bg-slate-900/60 border-t border-slate-800/80 flex items-center space-x-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Message YANA..."
          disabled={disabled}
          className="flex-1 bg-slate-950/80 border border-slate-800 focus:border-sky-500/60 focus:outline-none focus:ring-1 focus:ring-sky-500/30 text-slate-200 placeholder-slate-500 text-sm rounded-xl px-3.5 py-2 transition"
        />
        <button
          type="submit"
          disabled={!input.trim() || disabled}
          className="p-2 rounded-xl bg-sky-500 hover:bg-sky-400 disabled:opacity-40 disabled:hover:bg-sky-500 text-slate-950 transition flex items-center justify-center"
          title="Send message"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
};

import { PetState, PetMood } from "./pet.js";

export type WindowMode = "collapsed" | "expanded";
export type PetScale = "small" | "medium" | "large";

export interface AppState {
  status: "ready" | "busy" | "error" | "offline";
  debug: boolean;
  version: string;
  agentConnected: boolean;
}

export interface PetStateModel {
  current: PetState;
  mood: PetMood;
  lastStateChange: string;
}

export interface WindowState {
  mode: WindowMode;
  alwaysOnTop: boolean;
  isVisible: boolean;
  scale: PetScale;
}

export type MessageRole = "user" | "assistant" | "system" | "error";

export interface MessageMetadata {
  provider?: string;
  model?: string;
  tokensUsed?: number;
  finishReason?: string;
  isStreaming?: boolean;
  error?: {
    code: string;
    message: string;
    retryable?: boolean;
  };
  extra?: Record<string, unknown>;
}

export interface ConversationMessage {
  id: string;
  conversationId?: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  metadata?: MessageMetadata;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: ConversationMessage[];
}

export interface ConversationSummary {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}

export interface ConversationState {
  messages: ConversationMessage[];
  isListening: boolean;
  isSpeaking: boolean;
  isGenerating?: boolean;
  activeSessionId?: string | null;
  currentConversationId?: string | null;
  conversations?: ConversationSummary[];
  activeInput: string;
}

export interface YanaState {
  app: AppState;
  pet: PetStateModel;
  window: WindowState;
  conversation: ConversationState;
}

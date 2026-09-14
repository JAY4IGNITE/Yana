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

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant" | "system" | "error";
  content: string;
  timestamp: string;
}

export interface ConversationState {
  messages: ConversationMessage[];
  isListening: boolean;
  isSpeaking: boolean;
  activeInput: string;
}

export interface YanaState {
  app: AppState;
  pet: PetStateModel;
  window: WindowState;
  conversation: ConversationState;
}

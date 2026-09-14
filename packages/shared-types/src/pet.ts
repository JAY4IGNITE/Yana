export type PetMood = "happy" | "neutral" | "curious" | "concerned" | "focused";

export type PetState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "executing"
  | "verifying"
  | "success"
  | "error"
  | "offline"
  | "sleeping";

export interface PetStatus {
  state: PetState;
  mood: PetMood;
  lastInteraction: string;
  activeAnimation?: string;
}

export interface PetAnimationConfig {
  speed: number;
  glowColor: string;
  primaryColor: string;
  label: string;
}

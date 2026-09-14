export type PetMood = "happy" | "neutral" | "curious" | "concerned" | "focused";

export type PetState =
  | "idle"
  | "listening"
  | "thinking"
  | "executing"
  | "verifying"
  | "success"
  | "error"
  | "sleeping";

export interface PetStatus {
  state: PetState;
  mood: PetMood;
  lastInteraction: string;
  activeAnimation?: string;
}

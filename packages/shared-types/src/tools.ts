import { RiskLevel } from "@yana/protocol";

export interface ToolParameter {
  name: string;
  type: "string" | "number" | "boolean" | "object" | "array";
  description: string;
  required: boolean;
  default?: unknown;
}

export interface ToolDefinition {
  name: string;
  category: "system" | "computer" | "filesystem" | "terminal" | "browser" | "voice";
  description: string;
  riskLevel: RiskLevel;
  parameters: ToolParameter[];
}

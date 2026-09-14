import {
  ToolCall,
  ToolResult,
  VerificationResult,
  TaskStarted,
  TaskCancelled,
  PermissionResult,
} from "@yana/protocol";

export const DEFAULT_AGENT_URL = "http://127.0.0.1:8765/api";

export interface AgentHealth {
  status: string;
  version: string;
  protocol_version: string;
  environment: string;
}

export class AgentClient {
  private baseUrl: string;

  constructor(baseUrl: string = DEFAULT_AGENT_URL) {
    this.baseUrl = baseUrl;
  }

  async checkHealth(): Promise<AgentHealth> {
    const res = await fetch(`${this.baseUrl}/health`);
    if (!res.ok) {
      throw new Error(`Healthcheck failed with status: ${res.status}`);
    }
    return res.json();
  }

  async getTools(): Promise<Array<{ name: string; category: string; description: string; risk_level: string }>> {
    const res = await fetch(`${this.baseUrl}/tools`);
    if (!res.ok) {
      throw new Error(`Failed to list tools: ${res.status}`);
    }
    return res.json();
  }

  async executeTool(toolCall: ToolCall): Promise<{ tool_result: ToolResult; verification?: VerificationResult }> {
    const res = await fetch(`${this.baseUrl}/tools/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(toolCall),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: { message: res.statusText } }));
      throw err;
    }
    return res.json();
  }

  async createTask(description: string): Promise<TaskStarted> {
    const res = await fetch(`${this.baseUrl}/tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description }),
    });
    if (!res.ok) {
      throw new Error(`Failed to create task: ${res.status}`);
    }
    return res.json();
  }

  async cancelTask(taskId: string, reason: string = "User cancelled"): Promise<TaskCancelled> {
    const res = await fetch(`${this.baseUrl}/tasks/${taskId}/cancel?reason=${encodeURIComponent(reason)}`, {
      method: "POST",
    });
    if (!res.ok) {
      throw new Error(`Failed to cancel task: ${res.status}`);
    }
    return res.json();
  }

  async submitConsent(toolCallId: string, granted: boolean, reason?: string): Promise<PermissionResult> {
    const res = await fetch(`${this.baseUrl}/permissions/consent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ toolCallId, granted, reason }),
    });
    if (!res.ok) {
      throw new Error(`Failed to record consent: ${res.status}`);
    }
    return res.json();
  }
}

export const agentClient = new AgentClient();

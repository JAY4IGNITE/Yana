import {
  ToolCall,
  ToolResult,
  VerificationResult,
  TaskStarted,
  TaskCancelled,
  TaskCompleted,
  TaskStatus,
  TaskStepPayload,
  PermissionResult,
  SafeErrorPayload,
} from "@yana/protocol";
import {
  Conversation,
  ConversationSummary,
  MessageMetadata,
  Task,
} from "@yana/shared-types";

export const DEFAULT_AGENT_URL = "http://127.0.0.1:8765/api";

export interface AgentHealth {
  status: string;
  version: string;
  protocol_version: string;
  environment: string;
}

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onDone: (messageId?: string, metadata?: MessageMetadata) => void;
  onError: (error: SafeErrorPayload) => void;
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

  // =========================================================================
  // Phase 02: Conversation & Streaming Services
  // =========================================================================

  async listConversations(): Promise<ConversationSummary[]> {
    const res = await fetch(`${this.baseUrl}/conversations`);
    if (!res.ok) {
      throw new Error(`Failed to list conversations: ${res.status}`);
    }
    return res.json();
  }

  async createConversation(title: string = "New Chat"): Promise<Conversation> {
    const res = await fetch(`${this.baseUrl}/conversations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    if (!res.ok) {
      throw new Error(`Failed to create conversation: ${res.status}`);
    }
    return res.json();
  }

  async getConversation(id: string): Promise<Conversation> {
    const res = await fetch(`${this.baseUrl}/conversations/${id}`);
    if (!res.ok) {
      throw new Error(`Failed to get conversation: ${res.status}`);
    }
    return res.json();
  }

  async deleteConversation(id: string): Promise<{ deleted: boolean }> {
    const res = await fetch(`${this.baseUrl}/conversations/${id}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      throw new Error(`Failed to delete conversation: ${res.status}`);
    }
    return res.json();
  }

  async clearConversation(id: string): Promise<{ cleared: boolean }> {
    const res = await fetch(`${this.baseUrl}/conversations/${id}/messages`, {
      method: "DELETE",
    });
    if (!res.ok) {
      throw new Error(`Failed to clear conversation: ${res.status}`);
    }
    return res.json();
  }

  async cancelGeneration(sessionId: string): Promise<{ sessionId: string; cancelled: boolean }> {
    const res = await fetch(`${this.baseUrl}/conversation/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId }),
    });
    if (!res.ok) {
      throw new Error(`Failed to cancel generation: ${res.status}`);
    }
    return res.json();
  }

  async streamConversation(
    conversationId: string,
    content: string,
    sessionId: string,
    callbacks: StreamCallbacks,
    signal?: AbortSignal,
  ): Promise<void> {
    const res = await fetch(`${this.baseUrl}/conversation/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversationId, content, sessionId }),
      signal,
    });

    if (!res.ok) {
      throw new Error(`Streaming failed: HTTP ${res.status}`);
    }

    if (!res.body) {
      throw new Error("No response stream available.");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // Keep the last partial line in buffer
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith("data: ")) continue;

          const jsonStr = trimmed.slice(6);
          try {
            const data = JSON.parse(jsonStr);
            if (data.error) {
              callbacks.onError(data.error);
              return;
            }
            if (data.token) {
              callbacks.onToken(data.token);
            }
            if (data.isComplete) {
              callbacks.onDone(data.messageId, data.metadata);
            }
          } catch {
            // Ignore malformed individual chunks
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error)?.name === "AbortError") {
        // User aborted fetch stream
        return;
      }
      callbacks.onError({
        code: "NETWORK_ERROR" as any,
        message: err instanceof Error ? err.message : "Stream connection lost.",
        retryable: true,
      });
    } finally {
      reader.releaseLock();
    }
  }

  async retryConversation(
    conversationId: string,
    sessionId: string,
    callbacks: StreamCallbacks,
    signal?: AbortSignal,
  ): Promise<void> {
    const res = await fetch(`${this.baseUrl}/conversation/retry`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversationId, sessionId }),
      signal,
    });

    if (!res.ok) {
      throw new Error(`Retry failed: HTTP ${res.status}`);
    }

    if (!res.body) {
      throw new Error("No response stream available for retry.");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith("data: ")) continue;

          const jsonStr = trimmed.slice(6);
          try {
            const data = JSON.parse(jsonStr);
            if (data.error) {
              callbacks.onError(data.error);
              return;
            }
            if (data.token) {
              callbacks.onToken(data.token);
            }
            if (data.isComplete) {
              callbacks.onDone(data.messageId, data.metadata);
            }
          } catch {
            // Ignore malformed chunks
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error)?.name === "AbortError") {
        return;
      }
      callbacks.onError({
        code: "NETWORK_ERROR" as any,
        message: err instanceof Error ? err.message : "Retry stream connection lost.",
        retryable: true,
      });
    } finally {
      reader.releaseLock();
    }
  }

  // =========================================================================
  // Phase 03: Autonomous Agent Task & Plan Services
  // =========================================================================

  async planAgentTask(goal: string): Promise<PlanResponse> {
    const res = await fetch(`${this.baseUrl}/agent/plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal }),
    });
    if (!res.ok) {
      throw new Error(`Failed to create plan: ${res.status}`);
    }
    return res.json();
  }

  async runAgentTask(
    goal: string,
    callbacks: AgentTaskCallbacks,
    taskId?: string,
    signal?: AbortSignal,
  ): Promise<void> {
    const res = await fetch(`${this.baseUrl}/agent/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal, taskId }),
      signal,
    });

    if (!res.ok) {
      throw new Error(`Agent task failed to start: HTTP ${res.status}`);
    }

    if (!res.body) {
      throw new Error("No response body available from agent task stream.");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith("data: ")) continue;

          const jsonStr = trimmed.slice(6);
          try {
            const data = JSON.parse(jsonStr);
            if (data.type === "task_status" && callbacks.onStatus) {
              callbacks.onStatus(data);
            } else if (data.type === "task_step" && callbacks.onStep) {
              callbacks.onStep(data);
            } else if (data.type === "task_completed" && callbacks.onCompleted) {
              callbacks.onCompleted(data);
            } else if (data.type === "task_cancelled" && callbacks.onCancelled) {
              callbacks.onCancelled(data);
            } else if (data.type === "error" && callbacks.onError) {
              callbacks.onError(data);
            } else if (data.error && callbacks.onError) {
              callbacks.onError(data.error);
            }
          } catch {
            // Ignore malformed chunks
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error)?.name === "AbortError") {
        return;
      }
      callbacks.onError?.({
        code: "NETWORK_ERROR" as any,
        message: err instanceof Error ? err.message : "Agent task stream disconnected.",
        retryable: true,
      });
    } finally {
      reader.releaseLock();
    }
  }

  async getAgentTask(taskId: string): Promise<Task> {
    const res = await fetch(`${this.baseUrl}/agent/tasks/${taskId}`);
    if (!res.ok) {
      throw new Error(`Failed to fetch task '${taskId}': ${res.status}`);
    }
    return res.json();
  }

  async cancelAgentTask(taskId: string, reason?: string): Promise<TaskCancelled> {
    const res = await fetch(`${this.baseUrl}/agent/tasks/${taskId}/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: reason || "User requested cancellation" }),
    });
    if (!res.ok) {
      throw new Error(`Failed to cancel agent task: ${res.status}`);
    }
    return res.json();
  }

  // ==========================================================================
  // Voice Interaction API (Phase 08)
  // ==========================================================================

  async getVoiceStatus(): Promise<VoiceStatus> {
    const res = await fetch(`${this.baseUrl}/voice/status`);
    if (!res.ok) {
      throw new Error(`Failed to get voice status: ${res.status}`);
    }
    return res.json();
  }

  async getVoiceDevices(): Promise<VoiceDevicesResponse> {
    const res = await fetch(`${this.baseUrl}/voice/devices`);
    if (!res.ok) {
      throw new Error(`Failed to list voice devices: ${res.status}`);
    }
    return res.json();
  }

  async selectVoiceDevice(
    microphoneId?: string,
    speakerId?: string
  ): Promise<Record<string, unknown>> {
    const res = await fetch(`${this.baseUrl}/voice/devices/select`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ microphoneId, speakerId }),
    });
    if (!res.ok) {
      throw new Error(`Failed to select voice device: ${res.status}`);
    }
    return res.json();
  }

  async startPushToTalk(): Promise<{ status: string; state: string; microphone?: string }> {
    const res = await fetch(`${this.baseUrl}/voice/push-to-talk/start`, {
      method: "POST",
    });
    if (!res.ok) {
      throw new Error(`Failed to start push-to-talk: ${res.status}`);
    }
    return res.json();
  }

  async stopPushToTalk(): Promise<PushToTalkStopResponse> {
    const res = await fetch(`${this.baseUrl}/voice/push-to-talk/stop`, {
      method: "POST",
    });
    if (!res.ok) {
      throw new Error(`Failed to stop push-to-talk: ${res.status}`);
    }
    return res.json();
  }

  async stopSpeaking(): Promise<{ status: string; state: string }> {
    const res = await fetch(`${this.baseUrl}/voice/stop`, {
      method: "POST",
    });
    if (!res.ok) {
      throw new Error(`Failed to stop speaking: ${res.status}`);
    }
    return res.json();
  }

  async interruptSpeaking(): Promise<{ status: string; state: string }> {
    const res = await fetch(`${this.baseUrl}/voice/interrupt`, {
      method: "POST",
    });
    if (!res.ok) {
      throw new Error(`Failed to interrupt speaking: ${res.status}`);
    }
    return res.json();
  }

  async triggerVoiceShortcut(): Promise<Record<string, unknown>> {
    const res = await fetch(`${this.baseUrl}/voice/shortcut`, {
      method: "POST",
    });
    if (!res.ok) {
      throw new Error(`Failed to trigger voice shortcut: ${res.status}`);
    }
    return res.json();
  }

  async toggleWakeWord(enabled: boolean): Promise<{ status: string; wakeWordEnabled: boolean }> {
    const res = await fetch(`${this.baseUrl}/voice/wake-word/toggle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    if (!res.ok) {
      throw new Error(`Failed to toggle wake-word: ${res.status}`);
    }
    return res.json();
  }

  async speakText(text: string): Promise<Blob> {
    const res = await fetch(`${this.baseUrl}/voice/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) {
      throw new Error(`Failed to synthesize speech: ${res.status}`);
    }
    return res.blob();
  }
}

export interface AudioDevice {
  id: string;
  name: string;
  deviceType: "input" | "output";
  isDefault: boolean;
  isAvailable: boolean;
  sampleRate?: number;
  channels?: number;
}

export interface VoiceStatus {
  state: "idle" | "listening" | "thinking" | "speaking" | "error";
  microphone?: AudioDevice;
  speaker?: AudioDevice;
  wakeWordEnabled: boolean;
  error?: SafeErrorPayload;
}

export interface VoiceDevicesResponse {
  microphones: AudioDevice[];
  speakers: AudioDevice[];
}

export interface PushToTalkStopResponse {
  status: string;
  state: string;
  transcript: string;
  response: string;
  audio_bytes_length?: number;
}

export interface PlanStepItem {
  stepNumber: number;
  toolName: string;
  description: string;
  arguments: Record<string, unknown>;
}

export interface PlanResponse {
  taskId: string;
  goal: string;
  steps: PlanStepItem[];
}

export interface AgentTaskCallbacks {
  onStatus?: (status: TaskStatus) => void;
  onStep?: (step: TaskStepPayload) => void;
  onCompleted?: (completed: TaskCompleted) => void;
  onCancelled?: (cancelled: TaskCancelled) => void;
  onError?: (error: SafeErrorPayload) => void;
}

export const agentClient = new AgentClient();

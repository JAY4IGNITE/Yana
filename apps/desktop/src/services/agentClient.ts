import {
  ToolCall,
  ToolResult,
  VerificationResult,
  TaskStarted,
  TaskCancelled,
  TaskCompleted,
  TaskStatus,
  TaskStepPayload,
  PermissionRequest,
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
  // Fundamental Text Chat & Conversation Services
  // =========================================================================

  async sendChat(
    message: string,
    conversationId: string = "default",
    signal?: AbortSignal
  ): Promise<{ response: string; conversationId: string; provider: string; model: string }> {
    const res = await fetch(`${this.baseUrl}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, conversationId }),
      signal,
    });
    if (!res.ok) {
      throw new Error(`Chat request failed: HTTP ${res.status}`);
    }
    return res.json();
  }

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
            } else if (data.type === "permission_request" && callbacks.onPermissionRequest) {
              // A HIGH/CRITICAL step is now blocked awaiting the user's decision.
              // The task resumes on the same SSE stream once consent is POSTed to
              // /permissions/consent (see submitConsent).
              callbacks.onPermissionRequest(data);
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

  // =========================================================================
  // Memory System APIs
  // =========================================================================

  async createMemory(payload: {
    key: string;
    content: string;
    memoryType?: "temporary" | "session" | "long_term";
    category?: string;
    sessionId?: string;
    metadata?: Record<string, unknown>;
    tags?: string[];
  }): Promise<MemoryItemPayload> {
    const res = await fetch(`${this.baseUrl}/memory`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(`Failed to create memory: ${res.status}`);
    }
    return res.json();
  }

  async searchMemories(params: {
    q: string;
    category?: string;
    memoryType?: string;
    sessionId?: string;
    limit?: number;
  }): Promise<MemoryItemPayload[]> {
    const query = new URLSearchParams();
    query.set("q", params.q);
    if (params.category) query.set("category", params.category);
    if (params.memoryType) query.set("memoryType", params.memoryType);
    if (params.sessionId) query.set("sessionId", params.sessionId);
    if (params.limit) query.set("limit", params.limit.toString());

    const res = await fetch(`${this.baseUrl}/memory/search?${query.toString()}`);
    if (!res.ok) {
      throw new Error(`Failed to search memories: ${res.status}`);
    }
    return res.json();
  }

  async forgetMemory(id: string): Promise<{ status: string; id: string }> {
    const res = await fetch(`${this.baseUrl}/memory/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      throw new Error(`Failed to forget memory: ${res.status}`);
    }
    return res.json();
  }

  async bulkForgetMemories(params?: {
    category?: string;
    memoryType?: string;
    sessionId?: string;
  }): Promise<{ status: string; deletedCount: number }> {
    const query = new URLSearchParams();
    if (params?.category) query.set("category", params.category);
    if (params?.memoryType) query.set("memoryType", params.memoryType);
    if (params?.sessionId) query.set("sessionId", params.sessionId);

    const res = await fetch(`${this.baseUrl}/memory?${query.toString()}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      throw new Error(`Failed to bulk forget memories: ${res.status}`);
    }
    return res.json();
  }

  async listProjects(): Promise<ProjectMemoryPayload[]> {
    const res = await fetch(`${this.baseUrl}/memory/projects/list`);
    if (!res.ok) {
      throw new Error(`Failed to list projects: ${res.status}`);
    }
    return res.json();
  }

  async saveProject(payload: {
    name: string;
    path: string;
    technology?: string;
    description?: string;
    metadata?: Record<string, unknown>;
  }): Promise<ProjectMemoryPayload> {
    const res = await fetch(`${this.baseUrl}/memory/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(`Failed to save project: ${res.status}`);
    }
    return res.json();
  }

  async forgetProject(nameOrId: string): Promise<{ status: string; project: string }> {
    const res = await fetch(`${this.baseUrl}/memory/projects/${encodeURIComponent(nameOrId)}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      throw new Error(`Failed to forget project: ${res.status}`);
    }
    return res.json();
  }

  async listPreferences(category?: string): Promise<PreferencePayload[]> {
    const query = category ? `?category=${encodeURIComponent(category)}` : "";
    const res = await fetch(`${this.baseUrl}/memory/preferences/list${query}`);
    if (!res.ok) {
      throw new Error(`Failed to list preferences: ${res.status}`);
    }
    return res.json();
  }

  async setPreference(payload: {
    key: string;
    value: unknown;
    category?: string;
  }): Promise<PreferencePayload> {
    const res = await fetch(`${this.baseUrl}/memory/preferences`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(`Failed to set preference: ${res.status}`);
    }
    return res.json();
  }

  async forgetPreference(key: string): Promise<{ status: string; key: string }> {
    const res = await fetch(`${this.baseUrl}/memory/preferences/${encodeURIComponent(key)}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      throw new Error(`Failed to forget preference: ${res.status}`);
    }
    return res.json();
  }
}

export interface MemoryItemPayload {
  id: string;
  key: string;
  content: string;
  memoryType: "temporary" | "session" | "long_term";
  category: string;
  sessionId?: string | null;
  metadata: Record<string, unknown>;
  tags: string[];
  createdAt: string;
  updatedAt: string;
  expiresAt?: string | null;
}

export interface ProjectMemoryPayload {
  id: string;
  name: string;
  path: string;
  technology: string;
  description: string;
  lastUsed: string;
  metadata: Record<string, unknown>;
}

export interface ApplicationMemoryPayload {
  id: string;
  name: string;
  executablePath: string;
  category?: string | null;
  lastLaunched: string;
  metadata: Record<string, unknown>;
}

export interface PreferencePayload {
  key: string;
  value: unknown;
  category: string;
  updatedAt: string;
}

export interface WorkflowMemoryPayload {
  id: string;
  name: string;
  trigger: string;
  description: string;
  steps: Array<Record<string, unknown>>;
  metadata: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
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
  /**
   * Fired when a HIGH/CRITICAL step pauses the task to request consent. The task
   * stays blocked on the server until submitConsent() posts a decision under the
   * same toolCallId; remaining events then continue on this same stream.
   */
  onPermissionRequest?: (request: PermissionRequest) => void;
  onCompleted?: (completed: TaskCompleted) => void;
  onCancelled?: (cancelled: TaskCancelled) => void;
  onError?: (error: SafeErrorPayload) => void;
}

export const agentClient = new AgentClient();

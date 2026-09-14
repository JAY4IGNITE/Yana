import { useState, useEffect, useCallback, useRef } from "react";
import {
  PetState,
  PetMood,
  PetScale,
  WindowMode,
  ConversationMessage,
  ConversationSummary,
  YanaState,
} from "@yana/shared-types";
import {
  PermissionRequest,
  TaskStatus,
  TaskStepPayload,
  TaskCompleted,
  TaskCancelled,
  SafeErrorPayload,
} from "@yana/protocol";
import { agentClient, DEFAULT_AGENT_URL, AudioDevice } from "../services/agentClient";
import { ActiveTaskState } from "../components/Companion/TaskProgressCard";

// Safe Tauri invocation helper (graceful in tests & browser dev server)
async function safeInvoke(cmd: string, args?: Record<string, unknown>) {
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    return await invoke(cmd, args);
  } catch {
    return null;
  }
}

async function safeListen(event: string, callback: (event: any) => void) {
  try {
    const { listen } = await import("@tauri-apps/api/event");
    return await listen(event, callback);
  } catch {
    return () => {};
  }
}

export function useProtocol() {
  // 1. App State
  const [appStatus, setAppStatus] = useState<"ready" | "busy" | "error" | "offline">("ready");
  const [agentConnected, setAgentConnected] = useState<boolean>(false);

  // 2. Pet State
  const [petState, setPetState] = useState<PetState>("idle");
  const [petMood, setPetMood] = useState<PetMood>("happy");

  // 3. Window State
  const [windowMode, setWindowMode] = useState<WindowMode>("expanded");
  const [alwaysOnTop, setAlwaysOnTop] = useState<boolean>(true);
  const [scale, setScale] = useState<PetScale>("medium");

  // 4. Conversation State
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string>("default");
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [isListening, setIsListening] = useState<boolean>(false);
  const [isSpeaking, setIsSpeaking] = useState<boolean>(false);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  // Modals & Tasks
  const [pendingPermission, setPendingPermission] = useState<PermissionRequest | null>(null);
  const [currentTaskStatus, setCurrentTaskStatus] = useState<TaskStatus | null>(null);
  const [activeToolName, setActiveToolName] = useState<string | null>(null);
  const [activeTask, setActiveTask] = useState<ActiveTaskState | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [conversationListOpen, setConversationListOpen] = useState(false);

  // Voice & Audio Hardware State (Phase 08)
  const [microphones, setMicrophones] = useState<AudioDevice[]>([]);
  const [speakers, setSpeakers] = useState<AudioDevice[]>([]);
  const [selectedMicId, setSelectedMicId] = useState<string>("default_mic");
  const [selectedSpeakerId, setSelectedSpeakerId] = useState<string>("default_speaker");
  const [wakeWordEnabled, setWakeWordEnabled] = useState<boolean>(false);

  // Ref to cancel active stream
  const abortControllerRef = useRef<AbortController | null>(null);
  const agentTaskAbortRef = useRef<AbortController | null>(null);

  // Voice device refresher
  const refreshVoiceDevices = useCallback(async () => {
    try {
      const dev = await agentClient.getVoiceDevices();
      setMicrophones(dev.microphones || []);
      setSpeakers(dev.speakers || []);
      const st = await agentClient.getVoiceStatus();
      if (st.microphone) setSelectedMicId(st.microphone.id);
      if (st.speaker) setSelectedSpeakerId(st.speaker.id);
      setWakeWordEnabled(st.wakeWordEnabled);
    } catch {
      // Offline fallback
    }
  }, []);

  // Check backend health
  const checkConnection = useCallback(async () => {
    try {
      await agentClient.checkHealth();
      setAgentConnected(true);
      if (appStatus === "offline") setAppStatus("ready");
      refreshVoiceDevices();
    } catch {
      setAgentConnected(false);
    }
  }, [appStatus, refreshVoiceDevices]);

  useEffect(() => {
    checkConnection();
    const interval = setInterval(checkConnection, 12000);
    return () => clearInterval(interval);
  }, [checkConnection]);

  // Load conversation list and messages on initial connect
  const refreshConversations = useCallback(async () => {
    try {
      const list = await agentClient.listConversations();
      setConversations(list);
    } catch {
      // Offline fallback
    }
  }, []);

  const loadConversation = useCallback(async (id: string) => {
    try {
      const convo = await agentClient.getConversation(id);
      setCurrentConversationId(convo.id);
      setMessages(convo.messages);
    } catch {
      // Fallback
    }
  }, []);

  useEffect(() => {
    if (agentConnected) {
      refreshConversations();
    }
  }, [agentConnected, refreshConversations]);

  // Sync window mode with Tauri native window resizing
  const expandWindow = useCallback(async () => {
    setWindowMode("expanded");
    await safeInvoke("set_window_mode", { mode: "expanded" });
  }, []);

  const collapseWindow = useCallback(async () => {
    setWindowMode("collapsed");
    await safeInvoke("set_window_mode", { mode: "collapsed" });
  }, []);

  const toggleAlwaysOnTop = useCallback(async () => {
    const next = !alwaysOnTop;
    setAlwaysOnTop(next);
    await safeInvoke("set_always_on_top", { alwaysOnTop: next });
  }, [alwaysOnTop]);

  const cycleScale = useCallback(async () => {
    const scales: PetScale[] = ["small", "medium", "large"];
    const nextScale = scales[(scales.indexOf(scale) + 1) % scales.length];
    setScale(nextScale);
    await safeInvoke("set_pet_scale", { scale: nextScale });
  }, [scale]);

  // Listen for global shortcut trigger from native shell
  useEffect(() => {
    let unlistenShortcut: (() => void) | undefined;
    let unlistenSettings: (() => void) | undefined;

    safeListen("global-shortcut-triggered", () => {
      expandWindow();
      setPetState("listening");
    }).then((cleanup) => {
      unlistenShortcut = cleanup;
    });

    safeListen("open-settings", () => {
      expandWindow();
      setSettingsOpen(true);
    }).then((cleanup) => {
      unlistenSettings = cleanup;
    });

    return () => {
      unlistenShortcut?.();
      unlistenSettings?.();
    };
  }, [expandWindow]);

  // Phase 03: Autonomous Agent Task Execution
  const handleRunAgentTask = useCallback(
    async (goal: string) => {
      const taskId = crypto.randomUUID ? crypto.randomUUID() : `task-${Date.now()}`;
      setActiveTask({
        id: taskId,
        goal,
        status: "planning",
        progress: 0.05,
        stepDescription: "Planning execution steps...",
        steps: [],
      });

      setPetState("thinking");
      setPetMood("focused");
      setAppStatus("busy");

      const controller = new AbortController();
      agentTaskAbortRef.current = controller;

      try {
        await agentClient.runAgentTask(
          goal,
          {
            onStatus: (st: TaskStatus) => {
              setActiveTask((prev) =>
                prev
                  ? {
                      ...prev,
                      id: st.taskId || prev.id,
                      status: st.status,
                      progress: st.progress !== undefined ? st.progress : prev.progress,
                      currentStep: st.currentStep !== undefined ? st.currentStep : prev.currentStep,
                      totalSteps: st.totalSteps !== undefined ? st.totalSteps : prev.totalSteps,
                      stepDescription: st.message || prev.stepDescription,
                    }
                  : null
              );

              if (st.status === "executing" || st.status === "running") {
                setPetState("executing");
              } else if (st.status === "verifying") {
                setPetState("thinking");
              } else if (
                st.status === "waiting_confirmation" ||
                st.status === "waiting_permission"
              ) {
                setPetState("listening");
                setPetMood("curious");
              }
            },
            onStep: (step: TaskStepPayload) => {
              setActiveTask((prev) => {
                if (!prev) return null;
                const existingIdx = prev.steps.findIndex(
                  (s) => s.stepNumber === step.stepNumber || s.stepId === step.stepId
                );
                const updatedSteps = [...prev.steps];
                if (existingIdx >= 0) {
                  updatedSteps[existingIdx] = step;
                } else {
                  updatedSteps.push(step);
                }
                return {
                  ...prev,
                  steps: updatedSteps,
                  currentStep: step.stepNumber,
                  stepDescription: step.description,
                };
              });
            },
            onCompleted: (done: TaskCompleted) => {
              setActiveTask((prev) =>
                prev
                  ? {
                      ...prev,
                      status: "completed",
                      progress: 1.0,
                      stepDescription: done.summary || "Task completed successfully",
                    }
                  : null
              );
              setPetState("idle");
              setPetMood("happy");
              setAppStatus("ready");

              const doneMsg: ConversationMessage = {
                id: crypto.randomUUID ? crypto.randomUUID() : `msg-${Date.now()}`,
                conversationId: currentConversationId,
                role: "assistant",
                content: `Task Completed: ${done.summary || goal}`,
                timestamp: new Date().toISOString(),
              };
              setMessages((prev) => [...prev, doneMsg]);
            },
            onCancelled: (cancelled: TaskCancelled) => {
              setActiveTask((prev) =>
                prev
                  ? {
                      ...prev,
                      status: "cancelled",
                      stepDescription: cancelled.reason || "Task cancelled by user",
                    }
                  : null
              );
              setPetState("idle");
              setPetMood("curious");
              setAppStatus("ready");
            },
            onError: (err: SafeErrorPayload) => {
              setActiveTask((prev) =>
                prev
                  ? {
                      ...prev,
                      status: "failed",
                      error: err.message,
                    }
                  : null
              );
              setPetState("error");
              setPetMood("concerned");
              setAppStatus("ready");
            },
          },
          taskId,
          controller.signal
        );
      } catch (err: unknown) {
        setActiveTask((prev) =>
          prev
            ? {
                ...prev,
                status: "failed",
                error: err instanceof Error ? err.message : "Agent task execution error.",
              }
            : null
        );
        setPetState("error");
        setPetMood("concerned");
        setAppStatus("ready");
      }
    },
    [currentConversationId]
  );

  const handleCancelActiveTask = useCallback(async () => {
    if (!activeTask) return;
    if (agentTaskAbortRef.current) {
      agentTaskAbortRef.current.abort();
      agentTaskAbortRef.current = null;
    }
    try {
      await agentClient.cancelAgentTask(activeTask.id);
    } catch {
      // Ignore if already completed or aborted
    }
    setActiveTask((prev) =>
      prev
        ? {
            ...prev,
            status: "cancelled",
            stepDescription: "Cancellation requested by user.",
          }
        : null
    );
    setPetState("idle");
    setPetMood("curious");
    setAppStatus("ready");
  }, [activeTask]);

  const handleDismissActiveTask = useCallback(() => {
    setActiveTask(null);
  }, []);

  // Stop / Cancel active generation
  const handleStop = useCallback(async () => {
    // 1. Abort local fetch
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    if (agentTaskAbortRef.current) {
      agentTaskAbortRef.current.abort();
      agentTaskAbortRef.current = null;
    }

    // 2. Propagate cancel signal to backend provider
    if (activeSessionId && agentConnected) {
      await agentClient.cancelGeneration(activeSessionId).catch(() => {});
    }

    if (activeTask && agentConnected) {
      await agentClient.cancelAgentTask(activeTask.id).catch(() => {});
    }

    setIsListening(false);
    setIsSpeaking(false);
    setIsGenerating(false);
    setActiveSessionId(null);
    setPetState("idle");
    setAppStatus("ready");

    if (activeTask) {
      setActiveTask((prev) =>
        prev
          ? {
              ...prev,
              status: "cancelled",
              stepDescription: "Task stopped by user.",
            }
          : null
      );
    }

    if (currentTaskStatus?.status === "running") {
      setCurrentTaskStatus((prev) =>
        prev
          ? {
              ...prev,
              status: "cancelled",
              message: "Task stopped by user.",
            }
          : null
      );
    }
  }, [activeSessionId, activeTask, agentConnected, currentTaskStatus?.status]);

  // Send message flow (Ollama LLM with streaming & fallback)
  const handleSendMessage = async (text: string) => {
    if (!text.trim()) return;

    // Normal conversational message
    const userMsgId = crypto.randomUUID ? crypto.randomUUID() : `msg-user-${Date.now()}`;
    const assistantMsgId = crypto.randomUUID ? crypto.randomUUID() : `msg-asst-${Date.now()}`;
    const sessionId = crypto.randomUUID ? crypto.randomUUID() : `sess-${Date.now()}`;

    const userMsg: ConversationMessage = {
      id: userMsgId,
      conversationId: currentConversationId,
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };

    // Pre-create placeholder assistant message
    const assistantMsg: ConversationMessage = {
      id: assistantMsgId,
      conversationId: currentConversationId,
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
      metadata: { isStreaming: true },
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setPetState("thinking");
    setAppStatus("busy");
    setIsGenerating(true);
    setActiveSessionId(sessionId);

    // Setup cancellation controller
    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Verify backend connectivity
    if (!agentConnected) {
      try {
        await agentClient.checkHealth();
        setAgentConnected(true);
      } catch {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? {
                  ...m,
                  role: "error",
                  content:
                    "Cannot reach YANA AI backend service at http://127.0.0.1:8765/api. Please ensure the backend agent is running.",
                  metadata: { isStreaming: false },
                }
              : m
          )
        );
        setPetState("error");
        setPetMood("concerned");
        setIsGenerating(false);
        setAppStatus("error");
        setActiveSessionId(null);
        return;
      }
    }

    // Stream from Agent backend (Ollama) with clean non-streaming fallback
    try {
      await agentClient.streamConversation(
        currentConversationId,
        text,
        sessionId,
        {
          onToken: (token: string) => {
            setPetState("speaking");
            setIsSpeaking(true);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId ? { ...m, content: m.content + token } : m
              )
            );
          },
          onDone: (messageId, metadata) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      id: messageId || m.id,
                      metadata: { ...metadata, isStreaming: false },
                    }
                  : m
              )
            );
            setIsSpeaking(false);
            setIsGenerating(false);
            setActiveSessionId(null);
            setPetState("idle");
            setAppStatus("ready");
            refreshConversations();
          },
          onError: (err: SafeErrorPayload) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      role: "error",
                      content: `AI Service Notice: ${err.message}`,
                      metadata: { isStreaming: false, error: err },
                    }
                  : m
              )
            );
            setIsSpeaking(false);
            setIsGenerating(false);
            setActiveSessionId(null);
            setPetState("error");
            setAppStatus("error");
            setTimeout(() => {
              setPetState("idle");
              setAppStatus("ready");
            }, 3500);
          },
        },
        controller.signal
      );
    } catch {
      // Direct fallback to standard non-streaming chat endpoint
      try {
        const chatRes = await agentClient.sendChat(text, currentConversationId, controller.signal);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? {
                  ...m,
                  content: chatRes.response,
                  metadata: { provider: chatRes.provider, model: chatRes.model, isStreaming: false },
                }
              : m
          )
        );
        setIsSpeaking(false);
        setIsGenerating(false);
        setActiveSessionId(null);
        setPetState("idle");
        setAppStatus("ready");
        refreshConversations();
      } catch (fallbackErr: unknown) {
        const errMsg =
          fallbackErr instanceof Error ? fallbackErr.message : "AI communication failed.";
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? {
                  ...m,
                  role: "error",
                  content: `Error: ${errMsg}`,
                  metadata: { isStreaming: false },
                }
              : m
          )
        );
        setIsSpeaking(false);
        setIsGenerating(false);
        setActiveSessionId(null);
        setPetState("error");
        setAppStatus("error");
      }
    }
  };

  // Retry last turn
  const handleRetry = async () => {
    if (isGenerating) return;

    const sessionId = crypto.randomUUID();
    const assistantMsgId = crypto.randomUUID();

    // Placeholder message for retry
    const assistantMsg: ConversationMessage = {
      id: assistantMsgId,
      conversationId: currentConversationId,
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
      metadata: { isStreaming: true },
    };

    setMessages((prev) => [...prev, assistantMsg]);
    setPetState("thinking");
    setAppStatus("busy");
    setIsGenerating(true);
    setActiveSessionId(sessionId);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    if (!agentConnected) {
      setTimeout(() => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? {
                  ...m,
                  content: "Retry simulated: Ready to serve.",
                  metadata: { isStreaming: false },
                }
              : m
          )
        );
        setIsGenerating(false);
        setPetState("idle");
        setAppStatus("ready");
        setActiveSessionId(null);
      }, 500);
      return;
    }

    await agentClient.retryConversation(
      currentConversationId,
      sessionId,
      {
        onToken: (token: string) => {
          setPetState("speaking");
          setIsSpeaking(true);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? { ...m, content: m.content + token }
                : m
            )
          );
        },
        onDone: (messageId, metadata) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? {
                    ...m,
                    id: messageId || m.id,
                    metadata: { ...metadata, isStreaming: false },
                  }
                : m
            )
          );
          setIsSpeaking(false);
          setIsGenerating(false);
          setActiveSessionId(null);
          setPetState("idle");
          setAppStatus("ready");
        },
        onError: (err: SafeErrorPayload) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? {
                    ...m,
                    role: "error",
                    content: `Retry failed: ${err.message}`,
                    metadata: { isStreaming: false, error: err },
                  }
                : m
            )
          );
          setIsSpeaking(false);
          setIsGenerating(false);
          setActiveSessionId(null);
          setPetState("error");
          setAppStatus("error");
          setTimeout(() => {
            setPetState("idle");
            setAppStatus("ready");
          }, 3500);
        },
      },
      controller.signal
    );
  };

  // Clear conversation
  const handleClearConversation = async () => {
    setMessages([]);
    if (agentConnected && currentConversationId) {
      await agentClient.clearConversation(currentConversationId).catch(() => {});
      refreshConversations();
    }
  };

  // New conversation session
  const handleNewConversation = async () => {
    if (agentConnected) {
      try {
        const convo = await agentClient.createConversation("New Chat");
        setCurrentConversationId(convo.id);
        setMessages([]);
        refreshConversations();
        return;
      } catch {
        // Fallback
      }
    }
    setCurrentConversationId(crypto.randomUUID());
    setMessages([]);
  };

  const handleSelectMic = async (id: string) => {
    setSelectedMicId(id);
    try {
      if (agentConnected) {
        await agentClient.selectVoiceDevice(id, undefined);
      }
    } catch {
      // Offline fallback
    }
  };

  const handleSelectSpeaker = async (id: string) => {
    setSelectedSpeakerId(id);
    try {
      if (agentConnected) {
        await agentClient.selectVoiceDevice(undefined, id);
      }
    } catch {
      // Offline fallback
    }
  };

  const handleToggleWakeWord = async (enabled: boolean) => {
    setWakeWordEnabled(enabled);
    try {
      if (agentConnected) {
        await agentClient.toggleWakeWord(enabled);
      }
    } catch {
      // Offline fallback
    }
  };

  const handleStartPushToTalk = async () => {
    if (isSpeaking) {
      await handleInterruptSpeaking();
      return;
    }
    setIsListening(true);
    setPetState("listening");
    setPetMood("curious");
    try {
      if (agentConnected) {
        await agentClient.startPushToTalk();
      }
    } catch {
      // Offline fallback
    }
  };

  const handleStopPushToTalk = async () => {
    setIsListening(false);
    setPetState("thinking");
    setPetMood("focused");

    try {
      if (agentConnected) {
        const res = await agentClient.stopPushToTalk();
        if (res.transcript && res.transcript.trim()) {
          const userMsg: ConversationMessage = {
            id: crypto.randomUUID ? crypto.randomUUID() : `user-${Date.now()}`,
            conversationId: currentConversationId,
            role: "user",
            content: res.transcript,
            timestamp: new Date().toISOString(),
          };
          const assistantMsg: ConversationMessage = {
            id: crypto.randomUUID ? crypto.randomUUID() : `asst-${Date.now()}`,
            conversationId: currentConversationId,
            role: "assistant",
            content: res.response,
            timestamp: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, userMsg, assistantMsg]);
          setPetState("speaking");
          setIsSpeaking(true);
          setPetMood("happy");

          setTimeout(() => {
            setIsSpeaking(false);
            setPetState("idle");
            setPetMood("neutral");
          }, 2500);
        } else {
          setPetState("idle");
          setPetMood("neutral");
        }
      } else {
        setTimeout(() => {
          setPetState("idle");
          setPetMood("neutral");
        }, 1000);
      }
    } catch {
      setPetState("error");
      setTimeout(() => setPetState("idle"), 2500);
    }
  };

  const handleStopSpeaking = async () => {
    if (isSpeaking) {
      setIsSpeaking(false);
      setPetState("idle");
      setPetMood("neutral");
      try {
        if (agentConnected) {
          await agentClient.stopSpeaking();
        }
      } catch {
        // Offline fallback
      }
    }
  };

  const handleInterruptSpeaking = async () => {
    setIsSpeaking(false);
    setIsListening(true);
    setPetState("listening");
    setPetMood("curious");
    try {
      if (agentConnected) {
        await agentClient.interruptSpeaking();
      }
    } catch {
      // Offline fallback
    }
  };

  const handleTriggerShortcut = async () => {
    if (isSpeaking) {
      await handleInterruptSpeaking();
    } else if (isListening) {
      await handleStopPushToTalk();
    } else {
      await handleStartPushToTalk();
    }
  };

  const handleToggleListening = async () => {
    if (isListening) {
      await handleStopPushToTalk();
    } else {
      await handleStartPushToTalk();
    }
  };

  // Global shortcut (Ctrl+Shift+Space) for push-to-talk toggle
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && (e.code === "Space" || e.key === " ")) {
        e.preventDefault();
        handleTriggerShortcut();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isListening, isSpeaking, agentConnected]);

  const handleGrantPermission = async (toolCallId: string) => {
    if (!pendingPermission) return;
    setPendingPermission(null);
    setPetState("executing");
    setActiveToolName(pendingPermission.tool);

    setCurrentTaskStatus({
      version: "1.0.0",
      id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      type: "task_status",
      taskId: pendingPermission.taskId,
      status: "running",
      message: `Executing ${pendingPermission.tool}...`,
      progress: 0.5,
    });

    try {
      if (agentConnected) {
        await agentClient.submitConsent(toolCallId, true);
        const execRes = await agentClient.executeTool({
          version: "1.0.0",
          id: toolCallId,
          timestamp: new Date().toISOString(),
          type: "tool_call",
          taskId: pendingPermission.taskId,
          tool: pendingPermission.tool,
          riskLevel: pendingPermission.riskLevel,
          arguments: pendingPermission.arguments,
        });

        setCurrentTaskStatus({
          version: "1.0.0",
          id: crypto.randomUUID(),
          timestamp: new Date().toISOString(),
          type: "task_status",
          taskId: pendingPermission.taskId,
          status: "completed",
          message: "Action verified and executed successfully.",
          progress: 1.0,
        });
        setPetState("success");
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            conversationId: currentConversationId,
            role: "assistant",
            content: `Tool '${pendingPermission.tool}' executed successfully. Output: ${JSON.stringify(
              execRes.tool_result.output
            )}`,
            timestamp: new Date().toISOString(),
          },
        ]);
      } else {
        setTimeout(() => {
          setCurrentTaskStatus({
            version: "1.0.0",
            id: crypto.randomUUID(),
            timestamp: new Date().toISOString(),
            type: "task_status",
            taskId: pendingPermission.taskId,
            status: "completed",
            message: "Simulation complete.",
            progress: 1.0,
          });
          setPetState("success");
          setMessages((prev) => [
            ...prev,
            {
              id: crypto.randomUUID(),
              conversationId: currentConversationId,
              role: "assistant",
              content: `Simulated execution of ${pendingPermission.tool} complete.`,
              timestamp: new Date().toISOString(),
            },
          ]);
        }, 800);
      }
    } catch (err: unknown) {
      setPetState("error");
      const errMsg = err instanceof Error ? err.message : "Tool execution failed";
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          conversationId: currentConversationId,
          role: "error",
          content: errMsg,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setTimeout(() => {
        setActiveToolName(null);
        setPetState("idle");
      }, 2500);
    }
  };

  const handleDenyPermission = async (toolCallId: string, reason: string) => {
    setPendingPermission(null);
    setPetState("error");
    if (agentConnected) {
      await agentClient.submitConsent(toolCallId, false, reason).catch(() => {});
    }
    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        conversationId: currentConversationId,
        role: "error",
        content: `Permission denied: ${reason}`,
        timestamp: new Date().toISOString(),
      },
    ]);
    setTimeout(() => setPetState("idle"), 2500);
  };

  const yanaState: YanaState = {
    app: {
      status: appStatus,
      debug: true,
      version: "0.1.0",
      agentConnected,
    },
    pet: {
      current: petState,
      mood: petMood,
      lastStateChange: new Date().toISOString(),
    },
    window: {
      mode: windowMode,
      alwaysOnTop,
      isVisible: true,
      scale,
    },
    conversation: {
      messages,
      isListening,
      isSpeaking,
      isGenerating,
      activeSessionId,
      currentConversationId,
      conversations,
      activeInput: "",
    },
  };

  return {
    state: yanaState,
    petState,
    setPetState,
    petMood,
    setPetMood,
    windowMode,
    scale,
    alwaysOnTop,
    messages,
    conversations,
    currentConversationId,
    isListening,
    isSpeaking,
    isGenerating,
    pendingPermission,
    currentTaskStatus,
    activeToolName,
    activeTask,
    agentConnected,
    agentUrl: DEFAULT_AGENT_URL,
    settingsOpen,
    setSettingsOpen,
    conversationListOpen,
    setConversationListOpen,
    expandWindow,
    collapseWindow,
    toggleAlwaysOnTop,
    cycleScale,
    handleSendMessage,
    handleToggleListening,
    handleStop,
    handleRetry,
    handleClearConversation,
    handleNewConversation,
    loadConversation,
    handleGrantPermission,
    handleDenyPermission,
    handleRunAgentTask,
    handleCancelActiveTask,
    handleDismissActiveTask,
    microphones,
    speakers,
    selectedMicId,
    selectedSpeakerId,
    wakeWordEnabled,
    handleSelectMic,
    handleSelectSpeaker,
    handleToggleWakeWord,
    handleStartPushToTalk,
    handleStopPushToTalk,
    handleStopSpeaking,
    handleInterruptSpeaking,
    handleTriggerShortcut,
  };
}

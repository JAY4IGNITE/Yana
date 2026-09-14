import { useState, useEffect, useCallback } from "react";
import {
  PetState,
  PetMood,
  PetScale,
  WindowMode,
  ConversationMessage,
  YanaState,
} from "@yana/shared-types";
import { PermissionRequest, TaskStatus } from "@yana/protocol";
import { agentClient, DEFAULT_AGENT_URL } from "../services/agentClient";

// Safe Tauri invocation helper (graceful in tests & browser dev server)
async function safeInvoke(cmd: string, args?: Record<string, unknown>) {
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    return await invoke(cmd, args);
  } catch {
    // Graceful fallback when running in browser or test environments
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
  const [windowMode, setWindowMode] = useState<WindowMode>("collapsed");
  const [alwaysOnTop, setAlwaysOnTop] = useState<boolean>(true);
  const [scale, setScale] = useState<PetScale>("medium");

  // 4. Conversation State
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [isListening, setIsListening] = useState<boolean>(false);
  const [isSpeaking, setIsSpeaking] = useState<boolean>(false);

  // Modals & Tasks
  const [pendingPermission, setPendingPermission] = useState<PermissionRequest | null>(null);
  const [currentTaskStatus, setCurrentTaskStatus] = useState<TaskStatus | null>(null);
  const [activeToolName, setActiveToolName] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Check backend health
  const checkConnection = useCallback(async () => {
    try {
      await agentClient.checkHealth();
      setAgentConnected(true);
      if (appStatus === "offline") setAppStatus("ready");
    } catch {
      setAgentConnected(false);
    }
  }, [appStatus]);

  useEffect(() => {
    checkConnection();
    const interval = setInterval(checkConnection, 12000);
    return () => clearInterval(interval);
  }, [checkConnection]);

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

  // Send message flow
  const handleSendMessage = async (text: string) => {
    const userMsg: ConversationMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setPetState("thinking");
    setAppStatus("busy");

    // Check if user requested system tool (e.g. notepad)
    if (text.toLowerCase().includes("notepad")) {
      const toolCallId = crypto.randomUUID();
      const req: PermissionRequest = {
        version: "1.0.0",
        id: crypto.randomUUID(),
        timestamp: new Date().toISOString(),
        type: "permission_request",
        taskId: "task-" + Date.now(),
        toolCallId,
        tool: "system.open_application",
        riskLevel: "MEDIUM",
        description: "Launch Windows Notepad application",
        arguments: { app_name: "notepad.exe" },
      };
      setPendingPermission(req);
      setPetState("listening");
      return;
    }

    // Assistant response simulation / backend response
    setTimeout(() => {
      const assistantMsg: ConversationMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `I received your command: "${text}". The desktop companion architecture is operational.`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setPetState("speaking");
      setIsSpeaking(true);

      setTimeout(() => {
        setIsSpeaking(false);
        setPetState("idle");
        setAppStatus("ready");
      }, 1500);
    }, 600);
  };

  const handleToggleListening = () => {
    if (isListening) {
      setIsListening(false);
      setPetState("idle");
    } else {
      setIsListening(true);
      setPetState("listening");
    }
  };

  const handleStop = () => {
    setIsListening(false);
    setIsSpeaking(false);
    setPetState("idle");
    setAppStatus("ready");
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
  };

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
    isListening,
    isSpeaking,
    pendingPermission,
    currentTaskStatus,
    activeToolName,
    agentConnected,
    agentUrl: DEFAULT_AGENT_URL,
    settingsOpen,
    setSettingsOpen,
    expandWindow,
    collapseWindow,
    toggleAlwaysOnTop,
    cycleScale,
    handleSendMessage,
    handleToggleListening,
    handleStop,
    handleGrantPermission,
    handleDenyPermission,
  };
}

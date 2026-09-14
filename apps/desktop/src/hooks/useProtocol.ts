import { useState, useEffect, useCallback } from "react";
import { PetState, PetMood } from "@yana/shared-types";
import { PermissionRequest, TaskStatus } from "@yana/protocol";
import { agentClient, DEFAULT_AGENT_URL } from "../services/agentClient";
import { DisplayMessage } from "../components/Chat/ChatFeed";

export function useProtocol() {
  const [petState, setPetState] = useState<PetState>("idle");
  const [petMood, setPetMood] = useState<PetMood>("happy");
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [pendingPermission, setPendingPermission] = useState<PermissionRequest | null>(null);
  const [currentTaskStatus, setCurrentTaskStatus] = useState<TaskStatus | null>(null);
  const [activeToolName, setActiveToolName] = useState<string | null>(null);
  const [agentConnected, setAgentConnected] = useState<boolean>(false);

  // Periodic healthcheck to detect agent backend
  const checkConnection = useCallback(async () => {
    try {
      await agentClient.checkHealth();
      setAgentConnected(true);
    } catch {
      setAgentConnected(false);
    }
  }, []);

  useEffect(() => {
    checkConnection();
    const interval = setInterval(checkConnection, 10000);
    return () => clearInterval(interval);
  }, [checkConnection]);

  const handleSendMessage = async (text: string) => {
    const userMsg: DisplayMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setPetState("thinking");

    // Check if message looks like a system command
    if (text.toLowerCase().includes("notepad")) {
      const toolCallId = crypto.randomUUID();
      const req: PermissionRequest = {
        version: "1.0.0",
        id: crypto.randomUUID(),
        timestamp: new Date().toISOString(),
        type: "permission_request",
        taskId: "task-" + Date.now(),
        toolCallId: toolCallId,
        tool: "system.open_application",
        riskLevel: "MEDIUM",
        description: "Launch Windows Notepad application",
        arguments: { app_name: "notepad.exe" },
      };
      setPendingPermission(req);
      setPetState("listening");
      return;
    }

    // Default assistant response (mock / live)
    setTimeout(() => {
      const assistantMsg: DisplayMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `I received your command: "${text}". The foundational agent pipeline is ready for execution.`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setPetState("idle");
    }, 600);
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
            content: `Tool ${pendingPermission.tool} executed successfully. Output: ${JSON.stringify(
              execRes.tool_result.output
            )}`,
            timestamp: new Date().toISOString(),
          },
        ]);
      } else {
        // Local simulation when agent offline
        setTimeout(() => {
          setCurrentTaskStatus({
            version: "1.0.0",
            id: crypto.randomUUID(),
            timestamp: new Date().toISOString(),
            type: "task_status",
            taskId: pendingPermission.taskId,
            status: "completed",
            message: "Simulation: Notepad launched.",
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
        }, 1000);
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
      }, 3000);
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

  return {
    petState,
    setPetState,
    petMood,
    setPetMood,
    messages,
    pendingPermission,
    currentTaskStatus,
    activeToolName,
    agentConnected,
    agentUrl: DEFAULT_AGENT_URL,
    handleSendMessage,
    handleGrantPermission,
    handleDenyPermission,
  };
}

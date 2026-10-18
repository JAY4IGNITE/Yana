import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { App } from "../src/App";
import { useProtocol } from "../src/hooks/useProtocol";
import { agentClient } from "../src/services/agentClient";

const nativeEvents = vi.hoisted(() => new Map<string, (event: unknown) => void>());
vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn().mockResolvedValue(null) }));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(async (name: string, callback: (event: unknown) => void) => {
    nativeEvents.set(name, callback);
    return () => nativeEvents.delete(name);
  }),
}));

beforeEach(() => {
  nativeEvents.clear();
  vi.spyOn(agentClient, "checkHealth").mockResolvedValue({ status: "healthy" } as Awaited<ReturnType<typeof agentClient.checkHealth>>);
  vi.spyOn(agentClient, "listConversations").mockResolvedValue([]);
  vi.spyOn(agentClient, "getVoiceDevices").mockResolvedValue({ microphones: [], speakers: [] });
  vi.spyOn(agentClient, "getVoiceStatus").mockResolvedValue({ state: "idle", wakeWordEnabled: false });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("assistant control integration regressions", () => {
  it("does not execute a late voice transcript after Stop", async () => {
    let finish!: (value: Awaited<ReturnType<typeof agentClient.stopPushToTalk>>) => void;
    vi.spyOn(agentClient, "stopPushToTalk").mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    const run = vi.spyOn(agentClient, "runAgentTask").mockResolvedValue();
    const { result } = renderHook(() => useProtocol());
    await waitFor(() => expect(result.current.agentConnected).toBe(true));
    act(() => result.current.setAgentMode("agent"));
    let transcription!: Promise<void>;
    act(() => { transcription = result.current.handleStopPushToTalk(); });
    await act(async () => { await result.current.handleStop(); });
    await act(async () => {
      finish({ status: "success", state: "idle", transcript: "Open Notepad", response: "" });
      await transcription;
    });
    expect(run).not.toHaveBeenCalled();
    expect(result.current.isListening).toBe(false);
  });
  it("lets the user opt into PC control and routes their goal to the agent", async () => {
    const runTask = vi.spyOn(agentClient, "runAgentTask").mockImplementation(() => new Promise(() => {}));
    const chat = vi.spyOn(agentClient, "streamConversation").mockResolvedValue();
    render(<App />);
    await screen.findByText("Online & Ready");

    const mode = screen.getByRole("combobox", { name: "Assistant mode" });
    expect(mode).toHaveValue("chat");
    fireEvent.change(mode, { target: { value: "agent" } });
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Open Notepad" } });
    fireEvent.click(screen.getByRole("button", { name: "Send Message" }));

    await waitFor(() => expect(runTask).toHaveBeenCalledWith(
      "Open Notepad", expect.any(Object), expect.any(String), expect.any(AbortSignal)
    ));
    expect(chat).not.toHaveBeenCalled();
    expect(screen.getByRole("textbox")).toBeDisabled();
  });

  it("the native global shortcut starts actual voice capture", async () => {
    const capture = vi.spyOn(agentClient, "startPushToTalk").mockResolvedValue({ status: "ok", state: "listening" });
    const { result } = renderHook(() => useProtocol());
    await waitFor(() => expect(result.current.agentConnected).toBe(true));
    await waitFor(() => expect(nativeEvents.has("global-shortcut-triggered")).toBe(true));

    await act(async () => { nativeEvents.get("global-shortcut-triggered")!({ payload: null }); });

    await waitFor(() => expect(capture).toHaveBeenCalledTimes(1));
    expect(result.current.isListening).toBe(true);
  });

  it("does not show a listening indicator after microphone capture fails", async () => {
    vi.spyOn(agentClient, "startPushToTalk").mockRejectedValue(new Error("Microphone access denied"));
    const { result } = renderHook(() => useProtocol());
    await waitFor(() => expect(result.current.agentConnected).toBe(true));

    await act(async () => { await result.current.handleStartPushToTalk(); });

    expect(result.current.isListening).toBe(false);
    expect(result.current.messages.some(message => message.role === "error" && /microphone/i.test(message.content))).toBe(true);
  });

  it("stopping a streamed reply does not start a fallback reply or leave it streaming", async () => {
    vi.spyOn(agentClient, "streamConversation").mockImplementation((_conversation, _text, _session, _callbacks, signal) =>
      new Promise((_resolve, reject) => {
        signal?.addEventListener("abort", () => reject(new DOMException("Cancelled", "AbortError")), { once: true });
      })
    );
    const fallback = vi.spyOn(agentClient, "sendChat").mockRejectedValue(new DOMException("Cancelled", "AbortError"));
    vi.spyOn(agentClient, "cancelGeneration").mockResolvedValue({ sessionId: "session", cancelled: true });
    const { result } = renderHook(() => useProtocol());
    await waitFor(() => expect(result.current.agentConnected).toBe(true));
    let send: Promise<void>;
    act(() => { send = result.current.handleSendMessage("Explain this code"); });
    expect(result.current.isGenerating).toBe(true);

    await act(async () => {
      await result.current.handleStop();
      await send!;
    });

    expect(fallback).not.toHaveBeenCalled();
    expect(result.current.isGenerating).toBe(false);
    expect(result.current.messages.every(message => !message.metadata?.isStreaming)).toBe(true);
    expect(result.current.messages.some(message => message.role === "error")).toBe(false);
  });

  it("a network failure during retry releases the input and displays the error", async () => {
    vi.spyOn(agentClient, "retryConversation").mockRejectedValue(new Error("Connection interrupted"));
    const { result } = renderHook(() => useProtocol());
    await waitFor(() => expect(result.current.agentConnected).toBe(true));

    await act(async () => { await result.current.handleRetry().catch(() => {}); });

    expect(result.current.isGenerating).toBe(false);
    expect(result.current.messages.some(message => message.role === "error" && /connection interrupted/i.test(message.content))).toBe(true);
  });
});

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ExpandedAssistantView } from "../src/components/Companion/ExpandedAssistantView";
import { ConversationMessage } from "@yana/shared-types";

describe("ExpandedAssistantView - Conversational UI", () => {
  const mockMessages: ConversationMessage[] = [
    {
      id: "msg-1",
      role: "user",
      content: "Hello YANA",
      timestamp: new Date().toISOString(),
    },
    {
      id: "msg-2",
      role: "assistant",
      content: "Hello! How may I assist you today?",
      timestamp: new Date().toISOString(),
    },
  ];

  it("renders conversation messages with user and assistant bubbles", () => {
    render(
      <ExpandedAssistantView
        petState="idle"
        messages={mockMessages}
        isListening={false}
        isSpeaking={false}
        isGenerating={false}
        alwaysOnTop={true}
        agentConnected={true}
        onCollapse={vi.fn()}
        onToggleAlwaysOnTop={vi.fn()}
        onSendMessage={vi.fn()}
        onToggleListening={vi.fn()}
        onStop={vi.fn()}
        onOpenSettings={vi.fn()}
      />
    );

    expect(screen.getByText("Hello YANA")).toBeInTheDocument();
    expect(screen.getByText("Hello! How may I assist you today?")).toBeInTheDocument();
  });

  it("submits message on send click and clears input", () => {
    const handleSendMessage = vi.fn();
    render(
      <ExpandedAssistantView
        petState="idle"
        messages={[]}
        isListening={false}
        isSpeaking={false}
        isGenerating={false}
        alwaysOnTop={true}
        agentConnected={true}
        onCollapse={vi.fn()}
        onToggleAlwaysOnTop={vi.fn()}
        onSendMessage={handleSendMessage}
        onToggleListening={vi.fn()}
        onStop={vi.fn()}
        onOpenSettings={vi.fn()}
      />
    );

    const input = screen.getByPlaceholderText("Ask YANA...") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "Who are you?" } });
    expect(input.value).toBe("Who are you?");

    const sendBtn = screen.getByLabelText("Send Message");
    fireEvent.click(sendBtn);

    expect(handleSendMessage).toHaveBeenCalledWith("Who are you?");
    expect(input.value).toBe("");
  });

  it("renders Stop button and disables input during generation", () => {
    const handleStop = vi.fn();
    render(
      <ExpandedAssistantView
        petState="speaking"
        messages={mockMessages}
        isListening={false}
        isSpeaking={true}
        isGenerating={true}
        alwaysOnTop={true}
        agentConnected={true}
        onCollapse={vi.fn()}
        onToggleAlwaysOnTop={vi.fn()}
        onSendMessage={vi.fn()}
        onToggleListening={vi.fn()}
        onStop={handleStop}
        onOpenSettings={vi.fn()}
      />
    );

    const stopBtn = screen.getByLabelText("Stop Action");
    expect(stopBtn).toBeInTheDocument();
    fireEvent.click(stopBtn);
    expect(handleStop).toHaveBeenCalled();

    const input = screen.getByPlaceholderText("YANA is responding...");
    expect(input).toBeDisabled();
  });

  it("triggers retry on retry button click", () => {
    const handleRetry = vi.fn();
    render(
      <ExpandedAssistantView
        petState="idle"
        messages={mockMessages}
        isListening={false}
        isSpeaking={false}
        isGenerating={false}
        alwaysOnTop={true}
        agentConnected={true}
        onCollapse={vi.fn()}
        onToggleAlwaysOnTop={vi.fn()}
        onSendMessage={vi.fn()}
        onToggleListening={vi.fn()}
        onStop={vi.fn()}
        onRetry={handleRetry}
        onOpenSettings={vi.fn()}
      />
    );

    const retryBtn = screen.getByTitle("Retry Response");
    expect(retryBtn).toBeInTheDocument();
    fireEvent.click(retryBtn);
    expect(handleRetry).toHaveBeenCalled();
  });

  it("triggers clear conversation", () => {
    const handleClear = vi.fn();
    render(
      <ExpandedAssistantView
        petState="idle"
        messages={mockMessages}
        isListening={false}
        isSpeaking={false}
        isGenerating={false}
        alwaysOnTop={true}
        agentConnected={true}
        onCollapse={vi.fn()}
        onToggleAlwaysOnTop={vi.fn()}
        onSendMessage={vi.fn()}
        onToggleListening={vi.fn()}
        onStop={vi.fn()}
        onClearConversation={handleClear}
        onOpenSettings={vi.fn()}
      />
    );

    const clearBtn = screen.getByLabelText("Clear Messages");
    expect(clearBtn).toBeInTheDocument();
    fireEvent.click(clearBtn);
    expect(handleClear).toHaveBeenCalled();
  });
});

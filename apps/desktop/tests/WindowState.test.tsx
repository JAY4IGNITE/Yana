import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CollapsedPetView } from "../src/components/Companion/CollapsedPetView";
import { ExpandedAssistantView } from "../src/components/Companion/ExpandedAssistantView";

describe("WindowState & Dual Mode Views", () => {
  describe("CollapsedPetView", () => {
    it("renders collapsed pet with drag attribute", () => {
      render(
        <CollapsedPetView
          petState="idle"
          scale="medium"
          alwaysOnTop={true}
          onExpand={vi.fn()}
          onToggleAlwaysOnTop={vi.fn()}
          onCycleScale={vi.fn()}
        />
      );
      expect(screen.getByTestId("collapsed-pet-view")).toHaveAttribute("data-tauri-drag-region");
    });

    it("triggers onExpand when pet is clicked", () => {
      const handleExpand = vi.fn();
      render(
        <CollapsedPetView
          petState="idle"
          scale="medium"
          alwaysOnTop={true}
          onExpand={handleExpand}
          onToggleAlwaysOnTop={vi.fn()}
          onCycleScale={vi.fn()}
        />
      );
      fireEvent.click(screen.getByTestId("pet-companion"));
      expect(handleExpand).toHaveBeenCalled();
    });

    it("triggers onCycleScale and onToggleAlwaysOnTop from hover controls", () => {
      const handleScale = vi.fn();
      const handlePin = vi.fn();
      render(
        <CollapsedPetView
          petState="idle"
          scale="medium"
          alwaysOnTop={false}
          onExpand={vi.fn()}
          onToggleAlwaysOnTop={handlePin}
          onCycleScale={handleScale}
        />
      );

      fireEvent.click(screen.getByLabelText("Change Pet Size"));
      expect(handleScale).toHaveBeenCalled();

      fireEvent.click(screen.getByLabelText("Toggle Always On Top"));
      expect(handlePin).toHaveBeenCalled();
    });
  });

  describe("ExpandedAssistantView", () => {
    it("renders assistant header, conversation area, and input controls", () => {
      render(
        <ExpandedAssistantView
          petState="idle"
          messages={[]}
          isListening={false}
          isSpeaking={false}
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

      expect(screen.getByTestId("expanded-assistant-view")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("Ask YANA...")).toBeInTheDocument();
      expect(screen.getByLabelText("Toggle Microphone")).toBeInTheDocument();
      expect(screen.getByLabelText("Collapse Interface")).toBeInTheDocument();
    });

    it("submits message on enter or button click", () => {
      const handleSend = vi.fn();
      render(
        <ExpandedAssistantView
          petState="idle"
          messages={[]}
          isListening={false}
          isSpeaking={false}
          alwaysOnTop={true}
          agentConnected={true}
          onCollapse={vi.fn()}
          onToggleAlwaysOnTop={vi.fn()}
          onSendMessage={handleSend}
          onToggleListening={vi.fn()}
          onStop={vi.fn()}
          onOpenSettings={vi.fn()}
        />
      );

      const input = screen.getByPlaceholderText("Ask YANA...");
      fireEvent.change(input, { target: { value: "Hello YANA" } });
      fireEvent.click(screen.getByLabelText("Send Message"));

      expect(handleSend).toHaveBeenCalledWith("Hello YANA");
    });

    it("triggers onCollapse when minimize button is clicked", () => {
      const handleCollapse = vi.fn();
      render(
        <ExpandedAssistantView
          petState="idle"
          messages={[]}
          isListening={false}
          isSpeaking={false}
          alwaysOnTop={true}
          agentConnected={true}
          onCollapse={handleCollapse}
          onToggleAlwaysOnTop={vi.fn()}
          onSendMessage={vi.fn()}
          onToggleListening={vi.fn()}
          onStop={vi.fn()}
          onOpenSettings={vi.fn()}
        />
      );

      fireEvent.click(screen.getByLabelText("Collapse Interface"));
      expect(handleCollapse).toHaveBeenCalled();
    });
  });
});

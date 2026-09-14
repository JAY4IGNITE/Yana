import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SettingsModal } from "../src/components/Settings/SettingsModal";
import { agentClient } from "../src/services/agentClient";

describe("MemorySettings - Local Persistent Memory & Privacy Controls", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders Memory tab with privacy guard and selective persistence guarantees", async () => {
    vi.spyOn(agentClient, "listProjects").mockResolvedValue([
      {
        id: "proj-1",
        name: "IntelliRepo",
        path: "C:\\Users\\ramuv\\IntelliRepo",
        technology: "Python",
        description: "Intelligent code analysis system",
        lastUsed: "2026-09-14T10:00:00Z",
        metadata: {},
      },
    ]);

    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        agentConnected={true}
        agentUrl="http://127.0.0.1:8765/api"
      />
    );

    // Switch to Memory tab
    const memoryTabBtn = screen.getByText("Memory");
    fireEvent.click(memoryTabBtn);

    // Verify privacy and persistence guarantees
    expect(screen.getByText(/Privacy Guard & Credential Filter/i)).toBeDefined();
    expect(screen.getByText(/Zero credentials stored/i)).toBeDefined();
    expect(screen.getByText(/Selective Persistence/i)).toBeDefined();

    // Verify project IntelliRepo appears
    await waitFor(() => {
      expect(screen.getByText("IntelliRepo")).toBeDefined();
      expect(screen.getByText("Python")).toBeDefined();
    });
  });

  it("invokes bulk forget when clearing session memories", async () => {
    const purgeSpy = vi.spyOn(agentClient, "bulkForgetMemories").mockResolvedValue({
      status: "ok",
      deletedCount: 4,
    });

    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        agentConnected={true}
        agentUrl="http://127.0.0.1:8765/api"
      />
    );

    const memoryTabBtn = screen.getByText("Memory");
    fireEvent.click(memoryTabBtn);

    const clearSessionBtn = screen.getByText("Clear Session");
    fireEvent.click(clearSessionBtn);

    await waitFor(() => {
      expect(purgeSpy).toHaveBeenCalledWith({ memoryType: "session" });
      expect(screen.getByText(/Cleared 4 session memories/i)).toBeDefined();
    });
  });
});

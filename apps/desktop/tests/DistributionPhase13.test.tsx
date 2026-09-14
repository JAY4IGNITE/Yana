import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SettingsModal } from "../src/components/Settings/SettingsModal";

// Mock @tauri-apps/api/core invoke
vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(async (cmd: string, args?: any) => {
    if (cmd === "get_launch_at_startup") return false;
    if (cmd === "set_launch_at_startup") return args?.enable ?? true;
    if (cmd === "check_for_updates") {
      return {
        current_version: "0.1.0",
        update_available: false,
        message: "YANA v0.1.0 is up to date.",
      };
    }
    if (cmd === "get_agent_supervisor_status") {
      return {
        state: "Running",
        circuit_breaker_tripped: false,
        message: "Agent service is healthy and running.",
      };
    }
    if (cmd === "restart_agent_service") {
      return {
        state: "Running",
        circuit_breaker_tripped: false,
        message: "Supervisor state reset to Running.",
      };
    }
    return null;
  }),
}));

describe("Phase 13: Windows Distribution UI Components", () => {
  it("renders Windows Startup option and environment badge in General tab", () => {
    render(
      <SettingsModal
        isOpen={true}
        onClose={() => {}}
        agentConnected={true}
        agentUrl="http://127.0.0.1:8765/api"
      />
    );

    // Verify Windows Startup toggle exists
    expect(screen.getByText("Windows Startup")).toBeInTheDocument();
    expect(screen.getByText("Launch YANA when Windows boots")).toBeInTheDocument();
    const toggle = screen.getByTestId("startup-toggle");
    expect(toggle).toBeInTheDocument();

    // Verify Environment and Release version badges
    expect(screen.getByText("Production Native")).toBeInTheDocument();
    expect(screen.getByText("v0.1.0")).toBeInTheDocument();
  });

  it("handles checking for updates securely", async () => {
    render(
      <SettingsModal
        isOpen={true}
        onClose={() => {}}
        agentConnected={true}
        agentUrl="http://127.0.0.1:8765/api"
      />
    );

    const updateBtn = screen.getByTestId("check-updates-btn");
    expect(updateBtn).toBeInTheDocument();
    fireEvent.click(updateBtn);

    const statusText = await screen.findByText(/YANA v0.1.0 is up to date/);
    expect(statusText).toBeInTheDocument();
  });

  it("shows crash supervisor recovery options when agent is disconnected", () => {
    render(
      <SettingsModal
        isOpen={true}
        onClose={() => {}}
        agentConnected={false}
        agentUrl="http://127.0.0.1:8765/api"
      />
    );

    expect(screen.getByText("Disconnected")).toBeInTheDocument();
    expect(screen.getByText("Agent is unreachable or restarting.")).toBeInTheDocument();
    const restartBtn = screen.getByTestId("restart-agent-btn");
    expect(restartBtn).toBeInTheDocument();

    fireEvent.click(restartBtn);
  });
});

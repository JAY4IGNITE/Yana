import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
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
        message: "Automatic updates are not configured.",
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
  afterEach(() => vi.unstubAllGlobals());
  it("can restart a connected agent to reload configuration without duplicate requests", async () => {
    render(<SettingsModal isOpen onClose={() => {}} agentConnected agentUrl="http://127.0.0.1:8765/api" />);
    // Let initial status requests settle before holding the restart response.
    await act(async () => {});
    const restart = screen.getByRole("button", { name: "Restart" });
    let finish!: (status: unknown) => void;
    vi.mocked(invoke).mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    fireEvent.click(restart);
    expect(restart).toBeDisabled();
    expect(screen.getByText("Restarting...")).toBeInTheDocument();
    fireEvent.click(restart);
    await act(async () => finish({ state: "Running", circuit_breaker_tripped: false, message: "Agent ready." }));
    await waitFor(() => expect(restart).toBeEnabled());
    expect(screen.getByRole("status")).toHaveTextContent("Agent ready.");
  });

  it("shows a native restart failure and releases the restart button", async () => {
    vi.stubGlobal("__TAURI_INTERNALS__", {});
    render(<SettingsModal isOpen onClose={() => {}} agentConnected agentUrl="http://127.0.0.1:8765/api" />);
    await act(async () => {});
    vi.mocked(invoke).mockRejectedValueOnce({ message: "Agent exited during startup." });
    fireEvent.click(screen.getByRole("button", { name: "Restart" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Agent exited during startup.");
    expect(screen.getByRole("button", { name: "Restart" })).toBeEnabled();
  });

  it("gives browser preview restart instructions instead of a native bridge error", async () => {
    render(<SettingsModal isOpen onClose={() => {}} agentConnected agentUrl="http://127.0.0.1:8765/api" />);
    await act(async () => {});
    vi.mocked(invoke).mockRejectedValueOnce(new TypeError("Cannot read properties of undefined"));
    fireEvent.click(screen.getByRole("button", { name: "Restart" }));
    expect(await screen.findByRole("status")).toHaveTextContent("For browser preview, restart the agent in its terminal.");
  });

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
    expect(screen.getByText("Browser Preview")).toBeInTheDocument();
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

    const statusText = await screen.findByText(/Automatic updates are not configured/);
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

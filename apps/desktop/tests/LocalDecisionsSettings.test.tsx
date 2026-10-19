import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SettingsModal } from "../src/components/Settings/SettingsModal";
import { LocalDecisionsSettings } from "../src/components/Settings/LocalDecisionsSettings";
import { agentClient, DecisionStatusPayload } from "../src/services/agentClient";

describe("LocalDecisionsSettings - Desktop UI & Setup Guidance", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const readyStatus: DecisionStatusPayload = {
    state: "ready",
    mode: "shadow",
    is_ready: true,
    model_commit: "7b928d828b7b0e022f929d9bd2e44165aa270148",
    threads: 4,
    active_permitted: true,
    calibration_status: "verified",
    telemetry_summary: {
      total_recorded: 12,
      avg_latency_ms: 145.2,
      tier_distribution: { routine: 8, complex: 4 },
      status_distribution: { ok: 11, abstained: 1 },
    },
  };

  it("shows disconnected notice when agent is not connected", () => {
    render(<LocalDecisionsSettings agentConnected={false} />);
    expect(
      screen.getByText(/Connect to YANA Agent to configure local decision routing/i)
    ).toBeDefined();
  });

  it("renders ready state and telemetry overview in SettingsModal tab", async () => {
    vi.spyOn(agentClient, "getDecisionStatus").mockResolvedValue(readyStatus);

    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        agentConnected={true}
        agentUrl="http://127.0.0.1:8765/api"
      />
    );

    // Click Decisions tab
    const tabBtn = screen.getByText("Decisions");
    fireEvent.click(tabBtn);

    await waitFor(() => {
      expect(screen.getByText("Ready")).toBeDefined();
      expect(screen.getByText(/Revision: 7b928d828b7b/i)).toBeDefined();
      expect(screen.getByText(/4 CPU Threads/i)).toBeDefined();
      expect(screen.getByText(/Decisions Evaluated:/i)).toBeDefined();
      expect(screen.getByText("12")).toBeDefined();
      expect(screen.getByText("145.2 ms")).toBeDefined();
    });
  });

  it("handles mode changes to active and off", async () => {
    vi.spyOn(agentClient, "getDecisionStatus").mockResolvedValue(readyStatus);
    const setModeSpy = vi.spyOn(agentClient, "setDecisionMode").mockResolvedValue({
      status: "ok",
      mode: "active",
      state: "ready",
    });

    render(<LocalDecisionsSettings agentConnected={true} />);

    await waitFor(() => {
      expect(screen.getByText("Active")).toBeDefined();
    });

    // Click Active mode button
    const activeBtn = screen.getByText("Active").closest("button");
    expect(activeBtn).not.toBeNull();
    fireEvent.click(activeBtn!);

    await waitFor(() => {
      expect(setModeSpy).toHaveBeenCalledWith("active");
    });

    // Click Off mode button
    const offBtn = screen.getByText("Off").closest("button");
    expect(offBtn).not.toBeNull();
    fireEvent.click(offBtn!);

    await waitFor(() => {
      expect(setModeSpy).toHaveBeenCalledWith("off");
    });
  });

  it("guides user through explicit model setup when model is missing", async () => {
    const missingStatus: DecisionStatusPayload = {
      state: "model_missing",
      mode: "off",
      is_ready: false,
      model_commit: null,
      threads: 4,
      active_permitted: false,
      calibration_status: "uncalibrated",
      telemetry_summary: {
        total_recorded: 0,
        avg_latency_ms: 0,
        tier_distribution: {},
        status_distribution: {},
      },
    };

    vi.spyOn(agentClient, "getDecisionStatus").mockResolvedValue(missingStatus);
    const setupSpy = vi.spyOn(agentClient, "setupDecisionModel").mockResolvedValue({
      success: true,
      message: "Model verified and provisioned successfully",
      model_commit: "7b928d828b7b0e022f929d9bd2e44165aa270148",
      disk_free_gb: 42.5,
    });

    render(<LocalDecisionsSettings agentConnected={true} />);

    await waitFor(() => {
      expect(screen.getByText("Model Missing")).toBeDefined();
      expect(screen.getByText(/Requires at least 3.0 GB free disk space/i)).toBeDefined();
    });

    const setupBtn = screen.getByText("Setup Local Model Checkpoint").closest("button");
    expect(setupBtn).not.toBeNull();
    fireEvent.click(setupBtn!);

    await waitFor(() => {
      expect(setupSpy).toHaveBeenCalledTimes(1);
      expect(
        screen.getByText(/Model verified and provisioned successfully \(42.5 GB free\)/i)
      ).toBeDefined();
    });
  });

  it("displays lite mode badge when PyTorch is not installed", async () => {
    const notInstalledStatus: DecisionStatusPayload = {
      state: "not_installed",
      mode: "off",
      is_ready: false,
      model_commit: null,
      threads: 4,
      active_permitted: false,
      calibration_status: "uncalibrated",
      telemetry_summary: {
        total_recorded: 0,
        avg_latency_ms: 0,
        tier_distribution: {},
        status_distribution: {},
      },
    };

    vi.spyOn(agentClient, "getDecisionStatus").mockResolvedValue(notInstalledStatus);

    render(<LocalDecisionsSettings agentConnected={true} />);

    await waitFor(() => {
      expect(screen.getByText("Lite (No PyTorch)")).toBeDefined();
      expect(
        screen.getByText(/Operating in standard Lite mode. PyTorch \/ Laya dependencies are excluded/i)
      ).toBeDefined();
    });
  });
});

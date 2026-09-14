import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PermissionModal } from "../src/components/Permissions/PermissionModal";
import { PermissionRequest } from "@yana/protocol";

const sampleRequest: PermissionRequest = {
  version: "1.0.0",
  id: "req-1",
  timestamp: new Date().toISOString(),
  type: "permission_request",
  taskId: "task-1",
  toolCallId: "call-1",
  tool: "terminal.run_command",
  riskLevel: "HIGH",
  description: "Execute powershell script",
  arguments: { command: "dir" },
};

describe("PermissionModal Component", () => {
  it("renders nothing when request is null", () => {
    const { container } = render(
      <PermissionModal request={null} onGrant={vi.fn()} onDeny={vi.fn()} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders modal details when request is provided", () => {
    render(
      <PermissionModal request={sampleRequest} onGrant={vi.fn()} onDeny={vi.fn()} />
    );
    expect(screen.getByTestId("permission-modal")).toBeInTheDocument();
    expect(screen.getByText("Permission Required")).toBeInTheDocument();
    expect(screen.getByText("terminal.run_command")).toBeInTheDocument();
    expect(screen.getByText("HIGH RISK")).toBeInTheDocument();
  });

  it("calls onGrant with toolCallId on authorize button click", () => {
    const handleGrant = vi.fn();
    render(
      <PermissionModal request={sampleRequest} onGrant={handleGrant} onDeny={vi.fn()} />
    );
    fireEvent.click(screen.getByText("Authorize & Execute"));
    expect(handleGrant).toHaveBeenCalledWith("call-1");
  });

  it("calls onDeny with toolCallId on deny button click", () => {
    const handleDeny = vi.fn();
    render(
      <PermissionModal request={sampleRequest} onGrant={vi.fn()} onDeny={handleDeny} />
    );
    fireEvent.click(screen.getByText("Deny"));
    expect(handleDeny).toHaveBeenCalledWith("call-1", "User rejected permission");
  });
});

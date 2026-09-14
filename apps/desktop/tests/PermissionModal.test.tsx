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
    expect(screen.getByText("YANA CONFIRMATION")).toBeInTheDocument();
    expect(screen.getByText("Permission Required")).toBeInTheDocument();
    expect(screen.getByText("HIGH RISK")).toBeInTheDocument();
    expect(screen.getByText("Action")).toBeInTheDocument();
    expect(screen.getByText("Affected resources")).toBeInTheDocument();
    expect(screen.getByText("dir")).toBeInTheDocument();
  });

  it("calls onGrant with toolCallId on allow button click", () => {
    const handleGrant = vi.fn();
    render(
      <PermissionModal request={sampleRequest} onGrant={handleGrant} onDeny={vi.fn()} />
    );
    fireEvent.click(screen.getByText("Allow"));
    expect(handleGrant).toHaveBeenCalledWith("call-1");
  });

  it("calls onDeny with toolCallId on cancel button click", () => {
    const handleDeny = vi.fn();
    render(
      <PermissionModal request={sampleRequest} onGrant={vi.fn()} onDeny={handleDeny} />
    );
    fireEvent.click(screen.getByText("Cancel"));
    expect(handleDeny).toHaveBeenCalledWith("call-1", "User rejected permission");
  });
});

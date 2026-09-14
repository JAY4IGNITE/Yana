import { describe, it, expect } from "vitest";
import { PROTOCOL_VERSION, ErrorCode, SafeErrorPayload } from "@yana/protocol";

describe("Protocol Package Integration", () => {
  it("exports correct protocol version", () => {
    expect(PROTOCOL_VERSION).toBe("1.0.0");
  });

  it("contains all required ErrorCode variants", () => {
    expect(ErrorCode.VALIDATION_ERROR).toBe("VALIDATION_ERROR");
    expect(ErrorCode.CONFIGURATION_ERROR).toBe("CONFIGURATION_ERROR");
    expect(ErrorCode.AI_ERROR).toBe("AI_ERROR");
    expect(ErrorCode.TOOL_ERROR).toBe("TOOL_ERROR");
    expect(ErrorCode.PERMISSION_ERROR).toBe("PERMISSION_ERROR");
    expect(ErrorCode.TIMEOUT_ERROR).toBe("TIMEOUT_ERROR");
    expect(ErrorCode.NETWORK_ERROR).toBe("NETWORK_ERROR");
    expect(ErrorCode.SYSTEM_ERROR).toBe("SYSTEM_ERROR");
  });

  it("constructs valid SafeErrorPayload structure", () => {
    const errorPayload: SafeErrorPayload = {
      code: ErrorCode.PERMISSION_ERROR,
      message: "Permission denied for destructive action",
      taskId: "task-99",
      toolId: "terminal.run_command",
      retryable: false,
    };
    expect(errorPayload.code).toBe("PERMISSION_ERROR");
    expect(errorPayload.retryable).toBe(false);
  });
});

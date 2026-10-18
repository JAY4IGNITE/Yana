import { afterEach, describe, expect, it, vi } from "vitest";
import { AgentClient } from "../src/services/agentClient";

afterEach(() => vi.unstubAllGlobals());

describe("stream interruption", () => {
  it("reports a stream that ends without a completion event", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('data: {"token":"Hello"}\n\n')));
    const onError = vi.fn();
    await new AgentClient().streamConversation("c", "hi", "s", { onToken: vi.fn(), onDone: vi.fn(), onError });
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ retryable: true }));
  });
  it("does not leave a disconnected agent task running", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('data: {"type":"task_status","status":"planning"}\n\n')));
    const onError = vi.fn();
    await new AgentClient().runAgentTask("goal", { onError });
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ retryable: true }));
  });
});

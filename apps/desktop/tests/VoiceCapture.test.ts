import { describe, expect, it, vi } from "vitest";
import { encodeWav, VoiceCapture } from "../src/services/voiceCapture";

describe("microphone audio encoding", () => {
  it("releases a late microphone grant after the user cancels", async () => {
    let grant!: (stream: MediaStream) => void;
    const stop = vi.fn();
    const original = Object.getOwnPropertyDescriptor(navigator, "mediaDevices");
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: {
      getUserMedia: () => new Promise<MediaStream>((resolve) => { grant = resolve; }),
    } });
    try {
      const capture = new VoiceCapture();
      const start = capture.start();
      capture.cancel();
      grant({ getTracks: () => [{ stop }] } as unknown as MediaStream);
      await expect(start).rejects.toThrow("cancelled");
      expect(stop).toHaveBeenCalledOnce();
    } finally {
      if (original) Object.defineProperty(navigator, "mediaDevices", original);
      else Reflect.deleteProperty(navigator, "mediaDevices");
    }
  });
  it("encodes mono signed 16-bit WAV at the transcription sample rate", () => {
    const wav = encodeWav(new Float32Array([-1, 0, 1, 2]), 16000);
    const data = new DataView(wav);
    expect(new TextDecoder().decode(wav.slice(0, 4))).toBe("RIFF");
    expect(data.getUint32(24, true)).toBe(16000);
    expect(data.getUint16(22, true)).toBe(1);
    expect(data.getUint32(40, true)).toBe(8);
    expect(data.getInt16(44, true)).toBe(-32768);
    expect(data.getInt16(46, true)).toBe(0);
    expect(data.getInt16(48, true)).toBe(32767);
    expect(data.getInt16(50, true)).toBe(32767);
  });
});

/** The desktop webview owns microphone permission and audio playback. */
export function encodeWav(samples: Float32Array, sampleRate: number): ArrayBuffer {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const text = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i));
  };
  text(0, "RIFF"); view.setUint32(4, buffer.byteLength - 8, true);
  text(8, "WAVE"); text(12, "fmt "); view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  text(36, "data"); view.setUint32(40, samples.length * 2, true);
  samples.forEach((sample, i) => {
    const clipped = Math.max(-1, Math.min(1, sample));
    view.setInt16(44 + i * 2, clipped * (clipped < 0 ? 32768 : 32767), true);
  });
  return buffer;
}

export class VoiceCapture {
  private stream: MediaStream | null = null;
  private recorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private recordingError: Error | null = null;
  private limitTimer: ReturnType<typeof setTimeout> | null = null;
  private generation = 0;

  async start(deviceId?: string): Promise<void> {
    this.cancel();
    const generation = this.generation;
    if (!navigator.mediaDevices?.getUserMedia) throw new Error("Microphone capture is unavailable in this browser.");
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true,
        ...(deviceId && !deviceId.startsWith("default") ? { deviceId: { exact: deviceId } } : {}) },
    });
    if (generation !== this.generation) {
      stream.getTracks().forEach((track) => track.stop());
      throw new Error("Microphone recording cancelled.");
    }
    this.stream = stream;
    try {
      this.chunks = [];
      this.recordingError = null;
      this.recorder = new MediaRecorder(this.stream);
      this.recorder.ondataavailable = (event) => { if (event.data.size) this.chunks.push(event.data); };
      this.recorder.onerror = () => {
        this.recordingError = new Error("Microphone recording failed. Try again.");
        this.releaseTracks();
      };
      this.recorder.start();
      this.limitTimer = setTimeout(() => {
        this.recordingError = new Error("Recording reached the two-minute limit. Please try a shorter command.");
        this.cancel();
      }, 120000);
    } catch (error) { this.cancel(); throw error; }
  }

  private releaseTracks() {
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    if (this.limitTimer) clearTimeout(this.limitTimer);
    this.limitTimer = null;
  }

  cancel() {
    this.generation++;
    if (this.recorder?.state === "recording") this.recorder.stop();
    this.recorder = null;
    this.releaseTracks();
  }

  async stop(): Promise<ArrayBuffer> {
    if (this.recordingError) throw this.recordingError;
    const recorder = this.recorder;
    if (!recorder || recorder.state !== "recording") throw new Error("No microphone recording is active.");
    const blob = await new Promise<Blob>((resolve, reject) => {
      recorder.onstop = () => resolve(new Blob(this.chunks, { type: recorder.mimeType }));
      recorder.onerror = () => reject(new Error("Microphone recording failed."));
      recorder.stop();
      this.releaseTracks();
      this.recorder = null;
    });
    const context = new AudioContext();
    try {
      const decoded = await context.decodeAudioData(await blob.arrayBuffer());
      const offline = new OfflineAudioContext(1, Math.ceil(decoded.duration * 16000), 16000);
      const source = offline.createBufferSource();
      source.buffer = decoded;
      source.connect(offline.destination);
      source.start();
      const pcm = await offline.startRendering();
      return encodeWav(pcm.getChannelData(0), 16000);
    } finally { await context.close(); }
  }
}

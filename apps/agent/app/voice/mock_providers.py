"""Mock providers for zero-hardware automated testing of YANA voice pipelines."""

import struct
from typing import Any

from app.errors import SpeechToTextError, TextToSpeechError
from app.voice.base import (
    SpeechToTextProvider,
    TextToSpeechProvider,
    VoiceActivityDetector,
    WakeWordProvider,
)


def create_dummy_wav_bytes(duration_ms: int = 100, sample_rate: int = 16000) -> bytes:
    """Generate a minimal valid 16-bit mono RIFF WAV byte payload."""
    num_samples = int((duration_ms / 1000.0) * sample_rate)
    data_size = num_samples * 2  # 16-bit = 2 bytes per sample
    total_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        total_size,
        b"WAVE",
        b"fmt ",
        16,  # Subchunk1Size for PCM
        1,  # AudioFormat (PCM)
        1,  # NumChannels (Mono)
        sample_rate,
        sample_rate * 2,  # ByteRate
        2,  # BlockAlign
        16,  # BitsPerSample
        b"data",
        data_size,
    )
    payload = b"\x00" * data_size
    return header + payload


class MockSpeechToTextProvider(SpeechToTextProvider):
    """Mock STT provider for deterministic transcription testing."""

    name: str = "mock_stt"

    def __init__(
        self,
        default_transcript: str = "Hello YANA",
        should_fail: bool = False,
        failure_error: str = "Simulated STT recognition failure",
    ) -> None:
        self.default_transcript = default_transcript
        self.transcript_queue: list[str] = []
        self.should_fail = should_fail
        self.failure_error = failure_error
        self.transcription_history: list[dict[str, Any]] = []

    def is_available(self) -> bool:
        return True

    def enqueue_transcript(self, text: str) -> None:
        """Queue a specific transcript for the next transcribe() call."""
        self.transcript_queue.append(text)

    async def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str = "en",
    ) -> str:
        if self.should_fail:
            raise SpeechToTextError(self.failure_error)

        if not audio_data:
            return ""

        result = self.transcript_queue.pop(0) if self.transcript_queue else self.default_transcript
        self.transcription_history.append(
            {
                "length_bytes": len(audio_data),
                "sample_rate": sample_rate,
                "language": language,
                "result": result,
            }
        )
        return result


class MockTextToSpeechProvider(TextToSpeechProvider):
    """Mock TTS provider for deterministic speech synthesis testing."""

    name: str = "mock_tts"

    def __init__(
        self,
        should_fail: bool = False,
        failure_error: str = "Simulated TTS synthesis failure",
    ) -> None:
        self.should_fail = should_fail
        self.failure_error = failure_error
        self.spoken_texts: list[str] = []
        self.is_currently_speaking: bool = False

    def is_available(self) -> bool:
        return True

    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        if self.should_fail:
            raise TextToSpeechError(self.failure_error)

        self.spoken_texts.append(text)
        self.is_currently_speaking = True
        return create_dummy_wav_bytes(duration_ms=200)

    def stop_speaking(self) -> None:
        self.is_currently_speaking = False


class MockWakeWordProvider(WakeWordProvider):
    """Mock WakeWord detector verifying the 'Hey YANA' trigger invariant."""

    name: str = "mock_wakeword"
    wake_phrase: str = "Hey YANA"

    def __init__(
        self,
        should_trigger: bool = False,
        trigger_keyword: bytes = b"HEY_YANA_TRIGGER",
    ) -> None:
        self.should_trigger = should_trigger
        self.trigger_keyword = trigger_keyword
        self.trigger_count = 0

    def is_available(self) -> bool:
        return True

    async def detect(self, audio_chunk: bytes) -> bool:
        if self.should_trigger or self.trigger_keyword in audio_chunk:
            self.trigger_count += 1
            return True
        return False


class MockVoiceActivityDetector(VoiceActivityDetector):
    """Mock Voice Activity Detector for testing speech vs silence frame flows."""

    def __init__(self, force_speech: bool = False, energy_threshold: float = 300.0) -> None:
        self.force_speech = force_speech
        self.energy_threshold = energy_threshold
        self._speech_active = False
        self.frames_processed = 0

    def is_available(self) -> bool:
        return True

    @property
    def is_speech_active(self) -> bool:
        return self._speech_active

    def reset(self) -> None:
        self._speech_active = False
        self.frames_processed = 0

    def process_frame(self, frame: bytes) -> bool:
        self.frames_processed += 1
        if self.force_speech:
            self._speech_active = True
            return True

        if not frame:
            self._speech_active = False
            return False

        # Calculate RMS energy of 16-bit little endian PCM samples
        sample_count = len(frame) // 2
        if sample_count == 0:
            self._speech_active = False
            return False

        samples = struct.unpack(f"<{sample_count}h", frame[: sample_count * 2])
        energy = (sum(s * s for s in samples) / sample_count) ** 0.5
        self._speech_active = energy >= self.energy_threshold
        return self._speech_active

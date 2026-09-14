"""Abstract base classes and core data models for YANA Voice Interaction."""

from abc import ABC, abstractmethod
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class VoiceState(StrEnum):
    """Voice pipeline state machine states mapped to Pet companion animations."""

    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"


class AudioDeviceType(StrEnum):
    INPUT = "input"
    OUTPUT = "output"


class AudioDevice(BaseModel):
    """Audio input or output hardware device representation."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    device_type: AudioDeviceType = Field(..., alias="deviceType")
    is_default: bool = Field(default=False, alias="isDefault")
    is_available: bool = Field(default=True, alias="isAvailable")
    sample_rate: int = Field(default=16000, alias="sampleRate")
    channels: int = 1


class SpeechToTextProvider(ABC):
    """Abstract provider for speech recognition (STT)."""

    name: str = "base_stt"

    @abstractmethod
    async def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str = "en",
    ) -> str:
        """Transcribe raw audio bytes into recognized text."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is healthy and ready to transcribe."""
        pass


class TextToSpeechProvider(ABC):
    """Abstract provider for speech synthesis (TTS)."""

    name: str = "base_tts"

    @abstractmethod
    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        """Synthesize text into audio bytes (e.g. WAV / MP3 payload)."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is healthy and ready to synthesize."""
        pass


class WakeWordProvider(ABC):
    """Abstract provider for privacy-conscious wake-word detection.

    Must operate locally on raw PCM frames without streaming audio to external servers.
    """

    name: str = "base_wakeword"
    wake_phrase: str = "Hey YANA"

    @abstractmethod
    async def detect(self, audio_chunk: bytes) -> bool:
        """Evaluate an audio chunk and return True if the wake phrase is detected."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the wake-word engine is active and initialized."""
        pass


class VoiceActivityDetector(ABC):
    """Abstract Voice Activity Detection (VAD) to distinguish speech from silence."""

    @abstractmethod
    def process_frame(self, frame: bytes) -> bool:
        """Process a frame of PCM audio. Returns True if speech is active."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset internal history and state."""
        pass

    @property
    @abstractmethod
    def is_speech_active(self) -> bool:
        """Current speech activity status."""
        pass

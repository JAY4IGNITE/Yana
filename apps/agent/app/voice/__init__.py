"""Voice recognition and synthesis module boundary for YANA."""

from app.voice.base import (
    AudioDevice,
    AudioDeviceType,
    SpeechToTextProvider,
    TextToSpeechProvider,
    VoiceActivityDetector,
    VoiceState,
    WakeWordProvider,
)
from app.voice.device_manager import AudioDeviceManager
from app.voice.mock_providers import (
    MockSpeechToTextProvider,
    MockTextToSpeechProvider,
    MockVoiceActivityDetector,
    MockWakeWordProvider,
    create_dummy_wav_bytes,
)
from app.voice.pipeline import VoicePipeline

# Global default voice pipeline instance
voice_pipeline = VoicePipeline()

__all__ = [
    "AudioDevice",
    "AudioDeviceManager",
    "AudioDeviceType",
    "MockSpeechToTextProvider",
    "MockTextToSpeechProvider",
    "MockVoiceActivityDetector",
    "MockWakeWordProvider",
    "SpeechToTextProvider",
    "TextToSpeechProvider",
    "VoiceActivityDetector",
    "VoicePipeline",
    "VoiceState",
    "WakeWordProvider",
    "create_dummy_wav_bytes",
    "voice_pipeline",
]

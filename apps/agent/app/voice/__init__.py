"""Voice recognition and synthesis module boundary for YANA."""

from app.config import settings
from app.voice.base import (
    AudioDevice,
    AudioDeviceType,
    SpeechToTextProvider,
    TextToSpeechProvider,
    VoiceActivityDetector,
    VoiceState,
    WakeWordProvider,
)
from app.voice.cartesia_tts import CartesiaTTSProvider
from app.voice.device_manager import AudioDeviceManager
from app.voice.edge_tts_provider import NaturalEdgeTTSProvider
from app.voice.mock_providers import (
    MockSpeechToTextProvider,
    MockTextToSpeechProvider,
    MockVoiceActivityDetector,
    MockWakeWordProvider,
    create_dummy_wav_bytes,
)
from app.voice.parakeet_stt import NvidiaParakeetSTTProvider
from app.voice.pipeline import VoicePipeline


def create_voice_pipeline() -> VoicePipeline:
    """Initialize active voice pipeline matching environment configuration."""
    stt = (
        NvidiaParakeetSTTProvider()
        if settings.stt_provider == "nvidia_parakeet"
        else MockSpeechToTextProvider()
    )
    tts: TextToSpeechProvider
    if settings.tts_provider == "cartesia":
        tts = CartesiaTTSProvider()
    elif settings.tts_provider == "edge_tts":
        tts = NaturalEdgeTTSProvider()
    else:
        tts = MockTextToSpeechProvider()
    return VoicePipeline(stt_provider=stt, tts_provider=tts)


# Global default voice pipeline instance
voice_pipeline = create_voice_pipeline()

__all__ = [
    "AudioDevice",
    "AudioDeviceManager",
    "AudioDeviceType",
    "CartesiaTTSProvider",
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

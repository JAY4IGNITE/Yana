"""Natural Text-To-Speech (TTS) engine powered by Microsoft Edge Neural Voices."""

import io
from typing import Any

from app.config import settings
from app.errors import TextToSpeechError
from app.logger import logger
from app.voice.base import TextToSpeechProvider


class NaturalEdgeTTSProvider(TextToSpeechProvider):
    """Generates ultra-natural human-quality speech using Edge Neural Voices.

    - Expressive, human-like cadence and inflection.
    - Zero external API key required.
    - Highly responsive async streaming.
    """

    name: str = "edge_tts"

    def __init__(self, voice: str | None = None) -> None:
        self.default_voice = voice or settings.tts_voice or "en-US-AriaNeural"
        self._available = True

    def is_available(self) -> bool:
        return self._available

    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        """Synthesize text into MP3/WAV audio bytes."""
        if not text.strip():
            return b""

        target_voice = voice or self.default_voice
        try:
            import edge_tts

            communicate = edge_tts.Communicate(text=text, voice=target_voice)
            audio_buffer = io.BytesIO()

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])

            result = audio_buffer.getvalue()
            if not result:
                raise TextToSpeechError("Edge TTS produced empty audio payload.")

            return result
        except Exception as e:
            logger.error("Edge TTS synthesis failed: %s", e)
            raise TextToSpeechError(f"Natural speech synthesis failed: {e}") from e

    async def list_voices(self) -> list[dict[str, Any]]:
        """List available natural neural voices."""
        try:
            import edge_tts

            voices = await edge_tts.list_voices()
            return [
                {
                    "name": v["ShortName"],
                    "gender": v["Gender"],
                    "locale": v["Locale"],
                    "friendly_name": v["FriendlyName"],
                }
                for v in voices
                if v.get("Locale", "").startswith("en-")
            ]
        except Exception as e:
            logger.warning("Failed to list Edge TTS voices: %s", e)
            return []

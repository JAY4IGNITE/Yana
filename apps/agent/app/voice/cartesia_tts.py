"""Cartesia (Sonic) Text-To-Speech (TTS) Provider.

Synthesizes speech through Cartesia's hosted Sonic models. Unlike edge_tts, this
provider targets a specific Cartesia *voice ID* -- typically a cloned/custom voice
created in the Cartesia dashboard -- so YANA can speak in the user's own voice.

Follows the same httpx + explicit status-code error handling shape as the NVIDIA
Parakeet STT provider, and the "fail honestly" convention used across the agent:
a misconfiguration or API error raises a clear TextToSpeechError instead of
returning empty/fake audio that looks like silence.
"""

from typing import Any

import httpx

from app.config import settings
from app.errors import TextToSpeechError
from app.logger import logger
from app.voice.base import TextToSpeechProvider


class CartesiaTTSProvider(TextToSpeechProvider):
    """Speech synthesis powered by Cartesia Sonic, targeting a specific voice ID.

    - Speaks in a custom/cloned Cartesia voice (set via ``YANA_CARTESIA_VOICE_ID``).
    - Requires an API key (``YANA_CARTESIA_API_KEY``); reports unavailable without one.
    - Returns a WAV container so it plugs into the existing audio/wav pipeline.

    Note: Cartesia revises ``model_id`` names and the date-based ``Cartesia-Version``
    header periodically. Both are env-overridable (``YANA_CARTESIA_MODEL`` /
    ``YANA_CARTESIA_VERSION``) so a docs change never requires a code edit.
    """

    name: str = "cartesia"
    # Cartesia returns a WAV container; expose it so callers decode correctly and
    # the pipeline's audio_format mirrors the real payload.
    output_format: str = "audio/wav"

    def __init__(
        self,
        api_key: str | None = None,
        voice_id: str | None = None,
        model: str | None = None,
        version: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.cartesia_api_key.get_secret_value()
        self.voice_id = voice_id or settings.cartesia_voice_id
        self.model = model or settings.cartesia_model or "sonic-2"
        self.version = version or settings.cartesia_version or "2024-11-13"
        self.base_url = (
            base_url or settings.cartesia_base_url or "https://api.cartesia.ai"
        ).rstrip("/")

    def is_available(self) -> bool:
        """Cartesia needs both an API key and a target voice to synthesize."""
        return bool(self.api_key and self.voice_id)

    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        """Synthesize text into WAV audio bytes via Cartesia's /tts/bytes endpoint."""
        if not text.strip():
            return b""

        target_voice = voice or self.voice_id
        if not self.api_key or not target_voice:
            # Do NOT return empty audio: a missing key or voice cannot produce
            # speech. Surface it clearly so setup problems are visible instead of
            # being mistaken for silence.
            raise TextToSpeechError(
                "Cartesia TTS is not configured. Set YANA_CARTESIA_API_KEY and "
                "YANA_CARTESIA_VOICE_ID (or pass a voice id)."
            )

        endpoint = f"{self.base_url}/tts/bytes"
        headers = {
            "X-API-Key": self.api_key,
            "Cartesia-Version": self.version,
            "Content-Type": "application/json",
        }
        payload = {
            "model_id": self.model,
            "transcript": text,
            "voice": {"mode": "id", "id": target_voice},
            "output_format": {
                "container": "wav",
                "encoding": "pcm_s16le",
                "sample_rate": 44100,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=float(settings.tool_timeout_seconds)) as client:
                res = await client.post(endpoint, headers=headers, json=payload)

            if res.status_code == 200:
                audio = res.content
                if not audio:
                    raise TextToSpeechError("Cartesia TTS returned an empty audio payload.")
                return audio

            if res.status_code in (401, 403):
                logger.error("Cartesia TTS authentication failed (%d).", res.status_code)
                raise TextToSpeechError(
                    "Cartesia TTS authentication failed. Check YANA_CARTESIA_API_KEY."
                )

            logger.error(
                "Cartesia TTS failed with code %d: %s",
                res.status_code,
                res.text,
            )
            raise TextToSpeechError(f"Cartesia TTS returned error {res.status_code}: {res.text}")
        except TextToSpeechError:
            raise
        except Exception as e:
            logger.error("Cartesia TTS synthesis error: %s", e)
            raise TextToSpeechError(f"Cartesia speech synthesis failed: {e}") from e

    async def list_voices(self) -> list[dict[str, Any]]:
        """List voices available to the configured Cartesia account.

        Not required by the TextToSpeechProvider ABC; provided for parity with
        edge_tts so callers can discover voice IDs. Returns an empty list on any
        failure rather than raising, since voice discovery is best-effort.
        """
        if not self.api_key:
            return []

        endpoint = f"{self.base_url}/voices"
        headers = {
            "X-API-Key": self.api_key,
            "Cartesia-Version": self.version,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(endpoint, headers=headers)
            if res.status_code != 200:
                logger.warning("Failed to list Cartesia voices (%d): %s", res.status_code, res.text)
                return []
            body = res.json()
            voices = body if isinstance(body, list) else body.get("data", [])
            return [
                {
                    "id": v.get("id"),
                    "name": v.get("name"),
                    "language": v.get("language"),
                }
                for v in voices
                if isinstance(v, dict)
            ]
        except Exception as e:
            logger.warning("Failed to list Cartesia voices: %s", e)
            return []

"""NVIDIA Parakeet Speech-To-Text (STT) Provider."""

import httpx

from app.config import settings
from app.errors import SpeechToTextError
from app.logger import logger
from app.voice.base import SpeechToTextProvider


class NvidiaParakeetSTTProvider(SpeechToTextProvider):
    """Speech recognition powered by NVIDIA Parakeet ASR models on NVIDIA NIM."""

    name: str = "nvidia_parakeet"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = (
            api_key
            or settings.stt_api_key.get_secret_value()
            or settings.ai_heavy_api_key.get_secret_value()
            or settings.ai_api_key.get_secret_value()
        )
        self.base_url = (
            base_url or settings.ai_heavy_base_url or "https://integrate.api.nvidia.com/v1"
        )
        self.model = model or settings.stt_model or "nvidia/parakeet-ctc-1.1b-asr"

    def is_available(self) -> bool:
        return bool(self.api_key and self.base_url)

    async def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str = "en",
    ) -> str:
        """Transcribe PCM/WAV audio bytes into text via NVIDIA ASR API."""
        if not audio_data:
            return ""

        if not self.is_available():
            raise SpeechToTextError("NVIDIA Parakeet STT API key or base URL is not configured.")

        # Ensure audio is properly packaged as WAV format
        wav_payload = self._ensure_wav_header(audio_data, sample_rate)

        endpoint = f"{self.base_url.rstrip('/')}/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        files = {
            "file": ("audio.wav", wav_payload, "audio/wav"),
        }
        data = {
            "model": self.model,
            "language": language,
            "response_format": "json",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(endpoint, headers=headers, files=files, data=data)
                if res.status_code == 200:
                    body = res.json()
                    return body.get("text", "").strip()
                elif res.status_code == 404:
                    # A 404 means the transcription endpoint/model path is wrong.
                    # Surface it as an error so misconfiguration is visible during
                    # setup instead of silently returning an empty transcript that
                    # looks like "heard nothing".
                    logger.error(
                        "NVIDIA ASR endpoint 404 at %s. Check base_url/model configuration.",
                        endpoint,
                    )
                    raise SpeechToTextError(
                        f"NVIDIA ASR endpoint not found (404) at '{endpoint}'. "
                        "Verify YANA_STT_MODEL and the NIM base URL / ASR interface."
                    )
                else:
                    logger.error(
                        "NVIDIA Parakeet transcription failed with code %d: %s",
                        res.status_code,
                        res.text,
                    )
                    raise SpeechToTextError(
                        f"NVIDIA Parakeet returned error {res.status_code}: {res.text}"
                    )
        except SpeechToTextError:
            raise
        except Exception as e:
            logger.error("NVIDIA Parakeet transcription error: %s", e)
            raise SpeechToTextError(f"Transcription connection failed: {e}") from e

    def _ensure_wav_header(self, audio_data: bytes, sample_rate: int = 16000) -> bytes:
        """Add RIFF WAV header if raw PCM bytes were supplied."""
        if audio_data.startswith(b"RIFF"):
            return audio_data

        import struct

        data_size = len(audio_data)
        total_size = 36 + data_size
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            total_size,
            b"WAVE",
            b"fmt ",
            16,
            1,  # PCM format
            1,  # Mono
            sample_rate,
            sample_rate * 2,  # Byte rate (16-bit)
            2,  # Block align
            16,  # Bits per sample
            b"data",
            data_size,
        )
        return header + audio_data

"""Tests for the Cartesia (Sonic) TTS provider and its pipeline wiring.

Fully mocked: no network calls and no real Cartesia API key are required. The
HTTP layer is patched at httpx.AsyncClient.post so the request shape and the
"fail honestly" error behavior can be asserted deterministically.
"""

from typing import Any

import httpx
import pytest

from app.errors import TextToSpeechError
from app.voice.cartesia_tts import CartesiaTTSProvider
from app.voice.mock_providers import create_dummy_wav_bytes


class _FakeResponse:
    """Minimal stand-in for httpx.Response covering what the provider reads."""

    def __init__(self, status_code: int, content: bytes = b"", json_body: Any = None) -> None:
        self.status_code = status_code
        self.content = content
        self.text = content.decode("utf-8", errors="replace") if content else ""
        self._json_body = json_body

    def json(self) -> Any:
        return self._json_body


def _patch_post(monkeypatch: pytest.MonkeyPatch, response: _FakeResponse) -> dict[str, Any]:
    """Patch httpx.AsyncClient.post to capture the request and return `response`."""
    captured: dict[str, Any] = {}

    async def fake_post(self: httpx.AsyncClient, url: str, **kwargs: Any) -> _FakeResponse:
        captured["url"] = url
        captured["headers"] = kwargs.get("headers")
        captured["json"] = kwargs.get("json")
        return response

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    return captured


@pytest.mark.asyncio
async def test_synthesize_returns_audio_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    wav = create_dummy_wav_bytes(duration_ms=150, sample_rate=44100)
    captured = _patch_post(monkeypatch, _FakeResponse(200, content=wav))

    provider = CartesiaTTSProvider(api_key="sk_test", voice_id="voice-123")
    audio = await provider.synthesize("Hello in my own voice.")

    assert audio == wav
    # Request shape: endpoint, headers, and body carry the required fields.
    assert captured["url"].endswith("/tts/bytes")
    assert captured["headers"]["X-API-Key"] == "sk_test"
    assert captured["headers"]["Cartesia-Version"]  # non-empty date header
    assert captured["json"]["model_id"]
    assert captured["json"]["transcript"] == "Hello in my own voice."
    assert captured["json"]["voice"]["id"] == "voice-123"
    assert captured["json"]["output_format"]["container"] == "wav"


@pytest.mark.asyncio
async def test_empty_text_returns_empty_without_http(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a: Any, **_k: Any) -> None:  # pragma: no cover - must not be called
        raise AssertionError("HTTP should not be called for empty text")

    monkeypatch.setattr(httpx.AsyncClient, "post", _boom)

    provider = CartesiaTTSProvider(api_key="sk_test", voice_id="voice-123")
    assert await provider.synthesize("   ") == b""


@pytest.mark.asyncio
async def test_missing_key_is_unavailable_and_raises() -> None:
    provider = CartesiaTTSProvider(api_key="", voice_id="voice-123")
    assert provider.is_available() is False
    with pytest.raises(TextToSpeechError, match="not configured"):
        await provider.synthesize("Hi")


@pytest.mark.asyncio
async def test_missing_voice_is_unavailable_and_raises() -> None:
    provider = CartesiaTTSProvider(api_key="sk_test", voice_id="")
    assert provider.is_available() is False
    with pytest.raises(TextToSpeechError, match="not configured"):
        await provider.synthesize("Hi")


@pytest.mark.asyncio
async def test_auth_error_raises_not_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_post(monkeypatch, _FakeResponse(401, content=b"unauthorized"))

    provider = CartesiaTTSProvider(api_key="bad", voice_id="voice-123")
    with pytest.raises(TextToSpeechError, match="authentication failed"):
        await provider.synthesize("Hi")


@pytest.mark.asyncio
async def test_non_200_raises_with_status(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_post(monkeypatch, _FakeResponse(422, content=b"bad model_id"))

    provider = CartesiaTTSProvider(api_key="sk_test", voice_id="voice-123")
    with pytest.raises(TextToSpeechError, match="422"):
        await provider.synthesize("Hi")


@pytest.mark.asyncio
async def test_empty_payload_on_200_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_post(monkeypatch, _FakeResponse(200, content=b""))

    provider = CartesiaTTSProvider(api_key="sk_test", voice_id="voice-123")
    with pytest.raises(TextToSpeechError, match="empty audio"):
        await provider.synthesize("Hi")


def test_pipeline_selects_cartesia_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import voice as voice_module
    from app.config import settings

    monkeypatch.setattr(settings, "tts_provider", "cartesia")
    pipeline = voice_module.create_voice_pipeline()
    assert type(pipeline.tts).__name__ == "CartesiaTTSProvider"


def test_output_format_is_wav() -> None:
    provider = CartesiaTTSProvider(api_key="sk_test", voice_id="voice-123")
    assert provider.output_format == "audio/wav"

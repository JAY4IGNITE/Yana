"""Tests for Voice API routes."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.voice import voice_pipeline


@pytest.mark.asyncio
async def test_voice_status_and_devices_routes() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Status
        resp = await client.get("/api/voice/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "state" in data
        assert "microphone" in data
        assert "speaker" in data
        assert "wakeWordEnabled" in data

        # Devices list
        resp_dev = await client.get("/api/voice/devices")
        assert resp_dev.status_code == 200
        dev_data = resp_dev.json()
        assert "microphones" in dev_data
        assert "speakers" in dev_data
        assert len(dev_data["microphones"]) >= 1
        assert len(dev_data["speakers"]) >= 1


@pytest.mark.asyncio
async def test_voice_select_device_route() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Valid selection
        resp = await client.post(
            "/api/voice/devices/select",
            json={"microphoneId": "default_mic", "speakerId": "default_speaker"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        # Invalid selection
        resp_invalid = await client.post(
            "/api/voice/devices/select",
            json={"microphoneId": "non_existent_device_xyz"},
        )
        assert resp_invalid.status_code == 400


@pytest.mark.asyncio
async def test_voice_push_to_talk_and_shortcut_routes() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # PTT Start
        start_resp = await client.post("/api/voice/push-to-talk/start")
        assert start_resp.status_code == 200
        assert start_resp.json()["status"] == "listening"

        # PTT Stop
        stop_resp = await client.post("/api/voice/push-to-talk/stop")
        assert stop_resp.status_code == 200
        data = stop_resp.json()
        assert data["status"] == "success"
        assert "transcript" in data
        assert "response" in data

        # Shortcut toggle
        shortcut_resp = await client.post("/api/voice/shortcut")
        assert shortcut_resp.status_code == 200


@pytest.mark.asyncio
async def test_voice_speak_and_stop_routes() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Speak
        speak_resp = await client.post("/api/voice/speak", json={"text": "Hello, world!"})
        assert speak_resp.status_code == 200
        assert "audio/wav" in speak_resp.headers["content-type"]
        assert len(speak_resp.content) > 44

        # Stop
        stop_resp = await client.post("/api/voice/stop")
        assert stop_resp.status_code == 200
        assert stop_resp.json()["status"] == "stopped"

        # Interrupt
        int_resp = await client.post("/api/voice/interrupt")
        assert int_resp.status_code == 200
        assert int_resp.json()["status"] == "interrupted"


@pytest.mark.asyncio
async def test_voice_wake_word_toggle_and_feed_routes() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Toggle wake-word
        toggle_resp = await client.post("/api/voice/wake-word/toggle", json={"enabled": True})
        assert toggle_resp.status_code == 200
        assert toggle_resp.json()["wakeWordEnabled"] is True
        assert voice_pipeline.wake_word_enabled is True

        # Feed chunk
        raw_pcm = b"\x00\x00" * 160
        feed_resp = await client.post(
            "/api/voice/feed-chunk",
            json={"chunkHex": raw_pcm.hex()},
        )
        assert feed_resp.status_code == 200

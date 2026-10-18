"""Tests for user-visible paths, without real hardware or external services."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.planner.base import LLMPlanner, RuleBasedPlanner
from app.errors import ConfigurationError, ValidationError
from app.main import app
from app.tools import register_default_tools
from app.voice import voice_pipeline
from app.voice.mock_providers import create_dummy_wav_bytes


@pytest.mark.asyncio
async def test_unknown_real_goal_cannot_succeed_through_mock_tool(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "nvidia")
    with pytest.raises(ValidationError):
        await RuleBasedPlanner().create_plan(
            "organize my invoices", register_default_tools().list_tools()
        )


@pytest.mark.asyncio
async def test_basic_command_still_works_when_provider_cannot_be_initialized(monkeypatch):
    from app.ai import factory

    monkeypatch.setattr(settings, "ai_provider", "nvidia")

    def unavailable_provider():
        raise ConfigurationError("AI key is missing")

    monkeypatch.setattr(factory, "get_ai_provider", unavailable_provider)
    plan = await LLMPlanner().create_plan("Show system info", register_default_tools().list_tools())
    assert plan.steps[0].tool_name == "system.get_system_info"


@pytest.mark.asyncio
async def test_application_launch_preserves_requested_name():
    plan = await RuleBasedPlanner().create_plan(
        "open app mspaint.exe", register_default_tools().list_tools()
    )
    assert plan.steps[0].arguments["app_name"] == "mspaint.exe"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "goal",
    [
        "write file budget.txt with my new budget",
        "copy file source.docx to archive.docx",
        "open notepad and write a letter",
        "click the delete button",
    ],
)
async def test_offline_fallback_never_invents_arguments_or_drops_steps(monkeypatch, goal):
    monkeypatch.setattr(settings, "ai_provider", "nvidia")
    with pytest.raises(ValidationError):
        await RuleBasedPlanner().create_plan(goal, register_default_tools().list_tools())


@pytest.mark.asyncio
async def test_voice_upload_transcribes_without_echo_or_executing_tools(monkeypatch):
    transcribe = AsyncMock(return_value="Open Notepad")
    monkeypatch.setattr(voice_pipeline.stt, "transcribe", transcribe)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        audio = create_dummy_wav_bytes()
        response = await client.post(
            "/api/voice/transcribe", content=audio, headers={"Content-Type": "audio/wav"}
        )
        assert response.status_code == 200
        assert response.json()["transcript"] == "Open Notepad"
        transcribe.assert_awaited_once_with(audio)
        invalid = await client.post("/api/voice/transcribe", content=b"invalid")
        assert invalid.status_code == 400


@pytest.mark.asyncio
async def test_speech_response_uses_provider_audio_format(monkeypatch):
    monkeypatch.setattr(voice_pipeline, "direct_synthesize", AsyncMock(return_value=b"mp3"))
    monkeypatch.setattr(voice_pipeline.tts, "output_format", "audio/mpeg", raising=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/voice/speak", json={"text": "Hello"})
        assert response.headers["content-type"] == "audio/mpeg"


@pytest.mark.asyncio
async def test_untrusted_web_pages_cannot_control_local_agent():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/agent/run",
            json={"goal": "Show system info"},
            headers={"Origin": "https://untrusted.example"},
        )
        assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("interrupted", [False, True])
async def test_agent_shutdown_closes_its_automation_browser(monkeypatch, interrupted):
    from app.main import db_manager, lifespan
    from app.tools.browser.session import browser_session

    monkeypatch.setattr(db_manager, "initialize", AsyncMock())
    close = AsyncMock()
    monkeypatch.setattr(browser_session, "close_session", close)
    try:
        async with lifespan(app):
            if interrupted:
                raise RuntimeError("Service stopped with a request error")
    except RuntimeError:
        assert interrupted
    close.assert_awaited_once()

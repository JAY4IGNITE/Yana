"""FastAPI routes for YANA voice interaction, devices, PTT, and speech synthesis."""

from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from app.errors import YanaBaseError
from app.voice import voice_pipeline

router = APIRouter(prefix="/api/voice", tags=["Voice"])


class DeviceSelectRequest(BaseModel):
    microphone_id: str | None = Field(default=None, alias="microphoneId")
    speaker_id: str | None = Field(default=None, alias="speakerId")


class SpeakRequest(BaseModel):
    text: str


class WakeWordToggleRequest(BaseModel):
    enabled: bool


class AudioFeedRequest(BaseModel):
    chunk_hex: str = Field(..., alias="chunkHex")


@router.get("/status")
async def get_voice_status() -> dict[str, Any]:
    """Retrieve current voice engine state, device configuration, and wake word toggle."""
    try:
        mic = voice_pipeline.device_manager.get_selected_microphone()
        spk = voice_pipeline.device_manager.get_selected_speaker()
        return {
            "state": voice_pipeline.state.value,
            "microphone": mic.model_dump(by_alias=True),
            "speaker": spk.model_dump(by_alias=True),
            "wakeWordEnabled": voice_pipeline.wake_word_enabled,
        }
    except YanaBaseError as ex:
        return {
            "state": voice_pipeline.state.value,
            "error": ex.to_safe_payload(),
            "wakeWordEnabled": voice_pipeline.wake_word_enabled,
        }


@router.get("/devices")
async def list_audio_devices() -> dict[str, Any]:
    """List all enumerated microphones and speakers."""
    mics = [m.model_dump(by_alias=True) for m in voice_pipeline.device_manager.list_microphones()]
    spks = [s.model_dump(by_alias=True) for s in voice_pipeline.device_manager.list_speakers()]
    return {
        "microphones": mics,
        "speakers": spks,
    }


@router.post("/devices/select")
async def select_audio_device(req: DeviceSelectRequest) -> dict[str, Any]:
    """Select active microphone and/or speaker hardware device."""
    res: dict[str, Any] = {"status": "ok"}
    try:
        if req.microphone_id:
            mic = voice_pipeline.device_manager.select_microphone(req.microphone_id)
            res["microphone"] = mic.model_dump(by_alias=True)
        if req.speaker_id:
            spk = voice_pipeline.device_manager.select_speaker(req.speaker_id)
            res["speaker"] = spk.model_dump(by_alias=True)
        return res
    except YanaBaseError as ex:
        raise HTTPException(status_code=400, detail=ex.to_safe_payload()) from ex


@router.post("/push-to-talk/start")
async def push_to_talk_start() -> dict[str, Any]:
    """Trigger push-to-talk start: sets state to LISTENING."""
    try:
        return await voice_pipeline.push_to_talk_start()
    except YanaBaseError as ex:
        raise HTTPException(status_code=400, detail=ex.to_safe_payload()) from ex


@router.post("/push-to-talk/stop")
async def push_to_talk_stop() -> dict[str, Any]:
    """Trigger push-to-talk stop: runs STT, agent reasoning, and TTS response."""
    try:
        return await voice_pipeline.push_to_talk_stop()
    except YanaBaseError as ex:
        raise HTTPException(status_code=400, detail=ex.to_safe_payload()) from ex


@router.post("/shortcut")
async def trigger_shortcut() -> dict[str, Any]:
    """Trigger push-to-talk or barge-in from global shortcut keybinding."""
    try:
        return await voice_pipeline.trigger_shortcut()
    except YanaBaseError as ex:
        raise HTTPException(status_code=400, detail=ex.to_safe_payload()) from ex


@router.post("/speak")
async def speak_text(req: SpeakRequest) -> Response:
    """Synthesize text to speech and return WAV audio stream."""
    try:
        audio = await voice_pipeline.direct_synthesize(req.text)
        return Response(content=audio, media_type="audio/wav")
    except YanaBaseError as ex:
        raise HTTPException(status_code=400, detail=ex.to_safe_payload()) from ex


@router.post("/stop")
async def stop_speaking() -> dict[str, Any]:
    """Stop active speech synthesis playback."""
    return await voice_pipeline.stop_speaking()


@router.post("/interrupt")
async def interrupt_speaking() -> dict[str, Any]:
    """Interrupt active speaking and transition immediately to listening."""
    return await voice_pipeline.interrupt_speaking()


@router.post("/wake-word/toggle")
async def toggle_wake_word(req: WakeWordToggleRequest) -> dict[str, Any]:
    """Toggle local privacy-conscious wake-word detection."""
    voice_pipeline.set_wake_word_enabled(req.enabled)
    return {
        "status": "ok",
        "wakeWordEnabled": voice_pipeline.wake_word_enabled,
    }


@router.post("/feed-chunk")
async def feed_audio_chunk(req: AudioFeedRequest) -> dict[str, Any]:
    """Feed a hex-encoded raw audio frame into the voice pipeline."""
    try:
        raw_bytes = bytes.fromhex(req.chunk_hex)
        return await voice_pipeline.feed_audio_chunk(raw_bytes)
    except ValueError as ex:
        raise HTTPException(
            status_code=400,
            detail={"code": "VALIDATION_ERROR", "message": f"Invalid hex data: {ex}"},
        ) from ex

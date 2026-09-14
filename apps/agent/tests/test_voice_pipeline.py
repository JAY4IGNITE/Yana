"""Comprehensive unit and integration tests for YANA Phase 08 voice pipeline and abstractions."""

import pytest

from app.errors import (
    MicrophoneUnavailableError,
    SpeakerUnavailableError,
    SpeechToTextError,
    TextToSpeechError,
    VoicePermissionDeniedError,
)
from app.voice.base import AudioDevice, AudioDeviceType, VoiceState
from app.voice.device_manager import AudioDeviceManager
from app.voice.mock_providers import (
    MockSpeechToTextProvider,
    MockTextToSpeechProvider,
    MockVoiceActivityDetector,
    MockWakeWordProvider,
    create_dummy_wav_bytes,
)
from app.voice.pipeline import VoicePipeline

# ============================================================================
# Device Manager Tests
# ============================================================================


def test_device_manager_enumeration_and_defaults() -> None:
    dm = AudioDeviceManager()
    mics = dm.list_microphones()
    speakers = dm.list_speakers()

    assert len(mics) >= 1
    assert len(speakers) >= 1
    assert any(m.is_default for m in mics)
    assert any(s.is_default for s in speakers)

    current_mic = dm.get_selected_microphone()
    current_speaker = dm.get_selected_speaker()
    assert current_mic.device_type == AudioDeviceType.INPUT
    assert current_speaker.device_type == AudioDeviceType.OUTPUT


def test_device_manager_selection_and_errors() -> None:
    dm = AudioDeviceManager()

    # Register custom devices
    usb_mic = AudioDevice(
        id="usb_mic_01",
        name="USB Podcast Microphone",
        device_type=AudioDeviceType.INPUT,
        is_default=False,
        is_available=True,
    )
    studio_monitor = AudioDevice(
        id="studio_spk_01",
        name="Studio Monitor Speakers",
        device_type=AudioDeviceType.OUTPUT,
        is_default=False,
        is_available=True,
    )
    dm.register_device(usb_mic)
    dm.register_device(studio_monitor)

    # Select valid
    selected_mic = dm.select_microphone("usb_mic_01")
    assert selected_mic.id == "usb_mic_01"
    assert dm.get_selected_microphone().id == "usb_mic_01"

    selected_spk = dm.select_speaker("studio_spk_01")
    assert selected_spk.id == "studio_spk_01"
    assert dm.get_selected_speaker().id == "studio_spk_01"

    # Non-existent device error
    with pytest.raises(MicrophoneUnavailableError, match="does not exist"):
        dm.select_microphone("non_existent_mic")

    with pytest.raises(SpeakerUnavailableError, match="does not exist"):
        dm.select_speaker("non_existent_spk")

    # Wrong type error
    with pytest.raises(MicrophoneUnavailableError, match="output device"):
        dm.select_microphone("studio_spk_01")

    with pytest.raises(SpeakerUnavailableError, match="input device"):
        dm.select_speaker("usb_mic_01")


def test_device_manager_permission_denial() -> None:
    dm = AudioDeviceManager()

    # Deny mic
    dm.set_microphone_permission(False)
    with pytest.raises(VoicePermissionDeniedError, match="Microphone access permission denied"):
        dm.get_selected_microphone()

    with pytest.raises(VoicePermissionDeniedError, match="Microphone access permission denied"):
        dm.select_microphone("default_mic")

    # Restore mic, deny speaker
    dm.set_microphone_permission(True)
    dm.set_speaker_permission(False)
    with pytest.raises(VoicePermissionDeniedError, match="Speaker access permission denied"):
        dm.get_selected_speaker()

    with pytest.raises(VoicePermissionDeniedError, match="Speaker access permission denied"):
        dm.select_speaker("default_speaker")


def test_device_manager_unavailable_status() -> None:
    dm = AudioDeviceManager()
    dm.set_device_availability("default_mic", False)

    with pytest.raises(MicrophoneUnavailableError, match="unavailable or disconnected"):
        dm.get_selected_microphone()

    dm.set_device_availability("default_speaker", False)
    with pytest.raises(SpeakerUnavailableError, match="unavailable or disconnected"):
        dm.get_selected_speaker()


# ============================================================================
# Voice Pipeline & State Machine Tests
# ============================================================================


@pytest.mark.asyncio
async def test_push_to_talk_complete_pipeline() -> None:
    stt = MockSpeechToTextProvider(default_transcript="What is the weather in Neo-Tokyo?")
    tts = MockTextToSpeechProvider()
    vad = MockVoiceActivityDetector()
    pipeline = VoicePipeline(stt_provider=stt, tts_provider=tts, vad=vad)

    state_transitions: list[VoiceState] = []
    pipeline.add_state_listener(lambda s: state_transitions.append(s))

    assert pipeline.state == VoiceState.IDLE

    # 1. PTT Start -> LISTENING
    start_res = await pipeline.push_to_talk_start()
    assert start_res["status"] == "listening"
    assert pipeline.state == VoiceState.LISTENING

    # 2. Feed audio frames
    audio_frame = create_dummy_wav_bytes(duration_ms=100)
    feed_res = await pipeline.feed_audio_chunk(audio_frame)
    assert feed_res["status"] == "recording"
    assert feed_res["buffer_size"] > 0

    # 3. PTT Stop -> THINKING -> SPEAKING
    stop_res = await pipeline.push_to_talk_stop()
    assert stop_res["status"] == "success"
    assert stop_res["transcript"] == "What is the weather in Neo-Tokyo?"
    assert "I heard you say" in stop_res["response"]
    assert stop_res["audio_bytes_length"] > 0
    assert pipeline.state == VoiceState.SPEAKING

    # Verify state transitions order
    assert VoiceState.LISTENING in state_transitions
    assert VoiceState.THINKING in state_transitions
    assert VoiceState.SPEAKING in state_transitions


@pytest.mark.asyncio
async def test_stop_speaking() -> None:
    tts = MockTextToSpeechProvider()
    pipeline = VoicePipeline(tts_provider=tts)

    await pipeline.push_to_talk_start()
    await pipeline.push_to_talk_stop()
    assert pipeline.state == VoiceState.SPEAKING

    stop_res = await pipeline.stop_speaking()
    assert stop_res["status"] == "stopped"
    assert pipeline.state == VoiceState.IDLE
    assert tts.is_currently_speaking is False


@pytest.mark.asyncio
async def test_interrupt_speaking_barge_in() -> None:
    tts = MockTextToSpeechProvider()
    pipeline = VoicePipeline(tts_provider=tts)

    # Transition to speaking
    await pipeline.push_to_talk_start()
    await pipeline.push_to_talk_stop()
    assert pipeline.state == VoiceState.SPEAKING

    # User triggers barge-in interrupt
    int_res = await pipeline.interrupt_speaking()
    assert int_res["status"] == "interrupted"
    assert pipeline.state == VoiceState.LISTENING
    assert tts.is_currently_speaking is False


@pytest.mark.asyncio
async def test_vad_auto_barge_in_during_speech() -> None:
    vad = MockVoiceActivityDetector(force_speech=True)
    tts = MockTextToSpeechProvider()
    pipeline = VoicePipeline(tts_provider=tts, vad=vad)

    # Transition to speaking
    await pipeline.push_to_talk_start()
    await pipeline.push_to_talk_stop()
    assert pipeline.state == VoiceState.SPEAKING

    # User speaks while YANA is speaking -> VAD triggers automatic barge-in!
    feed_res = await pipeline.feed_audio_chunk(b"\x00" * 320)
    assert feed_res.get("interrupted") is True
    assert pipeline.state == VoiceState.LISTENING


@pytest.mark.asyncio
async def test_wake_word_local_privacy_invariant() -> None:
    wake = MockWakeWordProvider(should_trigger=False)
    pipeline = VoicePipeline(wake_word_provider=wake, wake_word_enabled=False)

    # Disabled: does not trigger
    feed1 = await pipeline.feed_audio_chunk(b"HEY_YANA_TRIGGER_FRAME")
    assert feed1.get("wake_word_detected") is None
    assert pipeline.state == VoiceState.IDLE

    # Enable wake-word
    pipeline.set_wake_word_enabled(True)
    assert pipeline.wake_word_enabled is True

    # Now feed trigger keyword frame
    feed2 = await pipeline.feed_audio_chunk(b"HEY_YANA_TRIGGER_FRAME")
    assert feed2.get("wake_word_detected") is True
    assert pipeline.state == VoiceState.LISTENING
    assert wake.trigger_count == 1


@pytest.mark.asyncio
async def test_global_shortcut_push_to_talk_toggle() -> None:
    pipeline = VoicePipeline()
    assert pipeline.state == VoiceState.IDLE

    # 1. First shortcut press starts listening
    res1 = await pipeline.trigger_shortcut()
    assert res1["status"] == "listening"
    assert pipeline.state == VoiceState.LISTENING

    # 2. Second shortcut press stops listening and enters thinking/speaking
    res2 = await pipeline.trigger_shortcut()
    assert res2["status"] == "success"
    assert pipeline.state == VoiceState.SPEAKING

    # 3. Third shortcut press interrupts speaking and goes back to listening
    res3 = await pipeline.trigger_shortcut()
    assert res3["status"] == "interrupted"
    assert pipeline.state == VoiceState.LISTENING


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.asyncio
async def test_stt_failure_handling() -> None:
    stt = MockSpeechToTextProvider(should_fail=True, failure_error="Network timeout to STT model")
    pipeline = VoicePipeline(stt_provider=stt)

    await pipeline.push_to_talk_start()
    await pipeline.feed_audio_chunk(b"some audio")

    with pytest.raises(SpeechToTextError, match="Network timeout to STT model"):
        await pipeline.push_to_talk_stop()

    assert pipeline.state == VoiceState.ERROR


@pytest.mark.asyncio
async def test_tts_failure_handling() -> None:
    tts = MockTextToSpeechProvider(should_fail=True, failure_error="Audio device playback error")
    pipeline = VoicePipeline(tts_provider=tts)

    await pipeline.push_to_talk_start()

    with pytest.raises(TextToSpeechError, match="Audio device playback error"):
        await pipeline.push_to_talk_stop()

    assert pipeline.state == VoiceState.ERROR


@pytest.mark.asyncio
async def test_mic_unavailable_at_ptt_start() -> None:
    dm = AudioDeviceManager()
    dm.set_device_availability("default_mic", False)
    pipeline = VoicePipeline(device_manager=dm)

    with pytest.raises(MicrophoneUnavailableError):
        await pipeline.push_to_talk_start()

    assert pipeline.state == VoiceState.ERROR


@pytest.mark.asyncio
async def test_speaker_unavailable_at_speech_output() -> None:
    dm = AudioDeviceManager()
    pipeline = VoicePipeline(device_manager=dm)

    await pipeline.push_to_talk_start()
    # Break speaker before speech playback
    dm.set_device_availability("default_speaker", False)

    with pytest.raises(SpeakerUnavailableError):
        await pipeline.push_to_talk_stop()

    assert pipeline.state == VoiceState.ERROR

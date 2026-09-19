"""Voice interaction pipeline coordinating Mic, VAD, STT, Agent, TTS, and Speaker."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from app.errors import (
    MicrophoneUnavailableError,
    SpeakerUnavailableError,
    SpeechToTextError,
    TextToSpeechError,
    VoicePermissionDeniedError,
    YanaBaseError,
)
from app.logger import logger
from app.voice.base import (
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
)


class VoicePipeline:
    """End-to-end voice pipeline managing states, push-to-talk, VAD, wake-word, and barge-in."""

    def __init__(
        self,
        device_manager: AudioDeviceManager | None = None,
        stt_provider: SpeechToTextProvider | None = None,
        tts_provider: TextToSpeechProvider | None = None,
        vad: VoiceActivityDetector | None = None,
        wake_word_provider: WakeWordProvider | None = None,
        agent_handler: Callable[[str], Awaitable[str]] | None = None,
        wake_word_enabled: bool = False,
    ) -> None:
        self.device_manager = device_manager or AudioDeviceManager()
        self.stt = stt_provider or MockSpeechToTextProvider()
        self.tts = tts_provider or MockTextToSpeechProvider()
        self.vad = vad or MockVoiceActivityDetector()
        self.wake_word = wake_word_provider or MockWakeWordProvider()
        self.agent_handler = agent_handler or self._default_agent_handler

        self._state: VoiceState = VoiceState.IDLE
        self._wake_word_enabled: bool = wake_word_enabled
        self._audio_buffer: bytearray = bytearray()
        self._state_listeners: list[Callable[[VoiceState], None]] = []
        self._active_playback_task: asyncio.Task[None] | None = None
        self._last_error: str | None = None

    @property
    def state(self) -> VoiceState:
        return self._state

    @property
    def wake_word_enabled(self) -> bool:
        return self._wake_word_enabled

    def set_wake_word_enabled(self, enabled: bool) -> None:
        """Enable or disable local wake-word detection."""
        self._wake_word_enabled = enabled
        logger.info(f"Local wake-word detection enabled: {enabled}")

    def add_state_listener(self, listener: Callable[[VoiceState], None]) -> None:
        """Register a callback for voice state transitions (for pet animations)."""
        self._state_listeners.append(listener)

    def _set_state(self, new_state: VoiceState) -> None:
        """Update internal voice state and broadcast to registered listeners."""
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            logger.info(f"Voice state transition: {old_state.value} -> {new_state.value}")
            for listener in self._state_listeners:
                try:
                    listener(new_state)
                except Exception as ex:
                    logger.warning(f"Error in voice state listener: {ex}")

    async def _default_agent_handler(self, transcript: str) -> str:
        """Default conversational echo when no external orchestrator is attached."""
        return f"I heard you say: '{transcript}'. How can I help you next?"

    async def push_to_talk_start(self) -> dict[str, Any]:
        """Start listening via push-to-talk.

        Validates microphone access and interrupts active speech if currently speaking.
        """
        try:
            # 1. Validate microphone hardware & permission
            mic = self.device_manager.get_selected_microphone()

            # 2. Barge-in interruption if currently speaking
            if self._state == VoiceState.SPEAKING:
                await self.interrupt_speaking()
            else:
                self._set_state(VoiceState.LISTENING)

            self._audio_buffer.clear()
            self.vad.reset()
            self._last_error = None

            return {
                "status": "listening",
                "state": self._state.value,
                "microphone": mic.name,
            }
        except (MicrophoneUnavailableError, VoicePermissionDeniedError) as err:
            self._last_error = err.message
            self._set_state(VoiceState.ERROR)
            raise

    async def push_to_talk_stop(self) -> dict[str, Any]:
        """Stop listening, run STT, call agent, synthesize TTS, and transition to SPEAKING."""
        if self._state != VoiceState.LISTENING:
            return {"status": "ignored", "state": self._state.value}

        self._set_state(VoiceState.THINKING)
        recorded_audio = bytes(self._audio_buffer)

        try:
            # 1. Speech recognition (STT)
            if not recorded_audio:
                transcript = ""
            else:
                transcript = await self.stt.transcribe(recorded_audio)

            # 2. Call YANA Agent
            if not transcript.strip():
                response_text = "I didn't hear anything. Please try speaking again."
            else:
                response_text = await self.agent_handler(transcript)

            # 3. Text-to-Speech (TTS)
            # Verify speaker is available before synthesizing
            self.device_manager.get_selected_speaker()
            audio_bytes = await self.tts.synthesize(response_text)

            # 4. Enter SPEAKING state
            self._set_state(VoiceState.SPEAKING)

            # Return the synthesized audio (base64) so the client can actually
            # play the response, not just its length. audio_format mirrors the
            # provider's output so the frontend knows how to decode it.
            import base64

            return {
                "status": "success",
                "state": self._state.value,
                "transcript": transcript,
                "response": response_text,
                "audio_bytes_length": len(audio_bytes),
                "audio_base64": base64.b64encode(audio_bytes).decode("ascii"),
                "audio_format": getattr(self.tts, "output_format", "audio/wav"),
            }
        except (
            SpeechToTextError,
            TextToSpeechError,
            SpeakerUnavailableError,
            VoicePermissionDeniedError,
            YanaBaseError,
        ) as err:
            self._last_error = err.message
            self._set_state(VoiceState.ERROR)
            raise

    async def feed_audio_chunk(self, chunk: bytes) -> dict[str, Any]:
        """Feed an audio chunk into the pipeline for VAD, wake-word, or buffer accumulation.

        Privacy guarantee: Wake-word processing executes entirely locally on the chunk.
        """
        # 1. Optional local wake-word detection when IDLE
        if self._wake_word_enabled and self._state == VoiceState.IDLE:
            is_wake = await self.wake_word.detect(chunk)
            if is_wake:
                logger.info(f"Wake phrase '{self.wake_word.wake_phrase}' detected locally!")
                # Validate mic access
                self.device_manager.get_selected_microphone()
                self._set_state(VoiceState.LISTENING)
                self._audio_buffer.clear()
                self.vad.reset()
                return {
                    "wake_word_detected": True,
                    "state": self._state.value,
                }

        # 2. Accumulate audio when LISTENING
        if self._state == VoiceState.LISTENING:
            self._audio_buffer.extend(chunk)
            is_speech = self.vad.process_frame(chunk)
            return {
                "status": "recording",
                "state": self._state.value,
                "buffer_size": len(self._audio_buffer),
                "is_speech": is_speech,
            }

        # 3. Barge-in detection when SPEAKING
        if self._state == VoiceState.SPEAKING:
            is_speech = self.vad.process_frame(chunk)
            if is_speech:
                logger.info("User speech detected during output: triggering barge-in interruption!")
                await self.interrupt_speaking()
                return {
                    "interrupted": True,
                    "state": self._state.value,
                }

        return {"status": "idle", "state": self._state.value}

    async def stop_speaking(self) -> dict[str, Any]:
        """Immediately stop speech synthesis playback and return to IDLE."""
        if self._state == VoiceState.SPEAKING:
            if hasattr(self.tts, "stop_speaking"):
                self.tts.stop_speaking()
            self._set_state(VoiceState.IDLE)
            logger.info("Voice speaking stopped by user.")
            return {"status": "stopped", "state": self._state.value}
        return {"status": "not_speaking", "state": self._state.value}

    async def interrupt_speaking(self) -> dict[str, Any]:
        """Interrupt active speech output and transition immediately to LISTENING."""
        if hasattr(self.tts, "stop_speaking"):
            self.tts.stop_speaking()

        self._set_state(VoiceState.LISTENING)
        self._audio_buffer.clear()
        self.vad.reset()
        logger.info("Voice playback interrupted; now listening for user.")
        return {"status": "interrupted", "state": self._state.value}

    async def trigger_shortcut(self) -> dict[str, Any]:
        """Trigger push-to-talk toggle from a global shortcut (e.g. Ctrl+Shift+Space)."""
        if self._state == VoiceState.LISTENING:
            return await self.push_to_talk_stop()
        elif self._state in (VoiceState.IDLE, VoiceState.ERROR):
            return await self.push_to_talk_start()
        elif self._state == VoiceState.SPEAKING:
            return await self.interrupt_speaking()
        return {"status": "busy", "state": self._state.value}

    async def direct_synthesize(self, text: str) -> bytes:
        """Synthesize text into speech bytes directly."""
        try:
            self.device_manager.get_selected_speaker()
            self._set_state(VoiceState.SPEAKING)
            audio = await self.tts.synthesize(text)
            return audio
        except Exception as err:
            self._set_state(VoiceState.ERROR)
            if isinstance(err, YanaBaseError):
                raise
            raise TextToSpeechError(f"TTS synthesis failed: {err}") from err

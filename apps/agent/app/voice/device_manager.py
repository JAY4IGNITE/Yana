"""Audio Hardware and Device Manager for Microphone and Speaker Selection."""

from app.errors import (
    MicrophoneUnavailableError,
    SpeakerUnavailableError,
    VoicePermissionDeniedError,
)
from app.logger import logger
from app.voice.base import AudioDevice, AudioDeviceType


class AudioDeviceManager:
    """Manages audio input/output device enumeration, selection, and permissions."""

    def __init__(self) -> None:
        self._devices: dict[str, AudioDevice] = {}
        self._selected_mic_id: str | None = None
        self._selected_speaker_id: str | None = None
        self._mic_permission_granted: bool = True
        self._speaker_permission_granted: bool = True
        self._initialize_default_devices()

    def _initialize_default_devices(self) -> None:
        """Initialize standard default audio devices."""
        default_mic = AudioDevice(
            id="default_mic",
            name="Default Microphone (System)",
            device_type=AudioDeviceType.INPUT,
            is_default=True,
            is_available=True,
            sample_rate=16000,
            channels=1,
        )
        default_speaker = AudioDevice(
            id="default_speaker",
            name="Default Speaker (System)",
            device_type=AudioDeviceType.OUTPUT,
            is_default=True,
            is_available=True,
            sample_rate=16000,
            channels=2,
        )
        self._devices = {
            default_mic.id: default_mic,
            default_speaker.id: default_speaker,
        }
        self._selected_mic_id = default_mic.id
        self._selected_speaker_id = default_speaker.id

    def list_microphones(self) -> list[AudioDevice]:
        """Return all registered audio input devices."""
        return [d for d in self._devices.values() if d.device_type == AudioDeviceType.INPUT]

    def list_speakers(self) -> list[AudioDevice]:
        """Return all registered audio output devices."""
        return [d for d in self._devices.values() if d.device_type == AudioDeviceType.OUTPUT]

    def get_selected_microphone(self) -> AudioDevice:
        """Return the currently selected microphone device."""
        if not self._mic_permission_granted:
            raise VoicePermissionDeniedError("Microphone access permission denied by system/user.")

        if not self._selected_mic_id or self._selected_mic_id not in self._devices:
            raise MicrophoneUnavailableError("No microphone is currently selected or configured.")

        mic = self._devices[self._selected_mic_id]
        if not mic.is_available:
            raise MicrophoneUnavailableError(
                f"Selected microphone '{mic.name}' ({mic.id}) is unavailable or disconnected."
            )
        return mic

    def get_selected_speaker(self) -> AudioDevice:
        """Return the currently selected speaker device."""
        if not self._speaker_permission_granted:
            raise VoicePermissionDeniedError("Speaker access permission denied by system/user.")

        if not self._selected_speaker_id or self._selected_speaker_id not in self._devices:
            raise SpeakerUnavailableError("No speaker is currently selected or configured.")

        spk = self._devices[self._selected_speaker_id]
        if not spk.is_available:
            raise SpeakerUnavailableError(
                f"Selected speaker '{spk.name}' ({spk.id}) is unavailable or disconnected."
            )
        return spk

    def select_microphone(self, device_id: str) -> AudioDevice:
        """Select an active microphone device by ID."""
        if not self._mic_permission_granted:
            raise VoicePermissionDeniedError("Microphone access permission denied by system/user.")

        if device_id not in self._devices:
            raise MicrophoneUnavailableError(
                f"Microphone device '{device_id}' does not exist or is not recognized."
            )

        dev = self._devices[device_id]
        if dev.device_type != AudioDeviceType.INPUT:
            raise MicrophoneUnavailableError(
                f"Device '{device_id}' is an output device, not a microphone."
            )

        if not dev.is_available:
            raise MicrophoneUnavailableError(
                f"Microphone device '{dev.name}' ({device_id}) is not available or disconnected."
            )

        self._selected_mic_id = device_id
        logger.info(f"Microphone selected: {dev.name} ({device_id})")
        return dev

    def select_speaker(self, device_id: str) -> AudioDevice:
        """Select an active speaker device by ID."""
        if not self._speaker_permission_granted:
            raise VoicePermissionDeniedError("Speaker access permission denied by system/user.")

        if device_id not in self._devices:
            raise SpeakerUnavailableError(
                f"Speaker device '{device_id}' does not exist or is not recognized."
            )

        dev = self._devices[device_id]
        if dev.device_type != AudioDeviceType.OUTPUT:
            raise SpeakerUnavailableError(
                f"Device '{device_id}' is an input device, not a speaker."
            )

        if not dev.is_available:
            raise SpeakerUnavailableError(
                f"Speaker device '{dev.name}' ({device_id}) is not available or disconnected."
            )

        self._selected_speaker_id = device_id
        logger.info(f"Speaker selected: {dev.name} ({device_id})")
        return dev

    def register_device(self, device: AudioDevice) -> None:
        """Register a new or enumerated audio hardware device."""
        self._devices[device.id] = device

    def set_device_availability(self, device_id: str, is_available: bool) -> None:
        """Toggle the availability flag of a device for simulation."""
        if device_id in self._devices:
            self._devices[device_id].is_available = is_available

    def set_microphone_permission(self, granted: bool) -> None:
        """Toggle system microphone permission status for testing."""
        self._mic_permission_granted = granted

    def set_speaker_permission(self, granted: bool) -> None:
        """Toggle system speaker permission status for testing."""
        self._speaker_permission_granted = granted

"""Standardized Error Model for YANA Agent."""

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Unified error codes across all YANA layers."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    AI_ERROR = "AI_ERROR"
    TOOL_ERROR = "TOOL_ERROR"
    PERMISSION_ERROR = "PERMISSION_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    MICROPHONE_UNAVAILABLE = "MICROPHONE_UNAVAILABLE"
    SPEAKER_UNAVAILABLE = "SPEAKER_UNAVAILABLE"
    STT_ERROR = "STT_ERROR"
    TTS_ERROR = "TTS_ERROR"
    VOICE_PERMISSION_DENIED = "VOICE_PERMISSION_DENIED"
    LOOP_DETECTED = "LOOP_DETECTED"
    SECURITY_ERROR = "SECURITY_ERROR"
    BROWSER_ERROR = "BROWSER_ERROR"
    VOICE_ERROR = "VOICE_ERROR"


class YanaBaseError(Exception):
    """Base exception for all YANA operations."""

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.SYSTEM_ERROR,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
        task_id: str | None = None,
        tool_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.retryable = retryable
        self.task_id = task_id
        self.tool_id = tool_id

    def to_safe_payload(self) -> dict[str, Any]:
        """Produce a safe error payload for transmission to the UI."""
        payload: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.details:
            payload["details"] = self.details
        if self.task_id:
            payload["taskId"] = self.task_id
        if self.tool_id:
            payload["toolId"] = self.tool_id
        return payload


class ValidationError(YanaBaseError):
    def __init__(self, message: str, details: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(message, code=ErrorCode.VALIDATION_ERROR, details=details, **kwargs)


class ConfigurationError(YanaBaseError):
    def __init__(self, message: str, details: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(message, code=ErrorCode.CONFIGURATION_ERROR, details=details, **kwargs)


class AIError(YanaBaseError):
    def __init__(self, message: str, details: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(message, code=ErrorCode.AI_ERROR, details=details, **kwargs)


class ToolError(YanaBaseError):
    def __init__(self, message: str, details: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(message, code=ErrorCode.TOOL_ERROR, details=details, **kwargs)


class PermissionError(YanaBaseError):
    def __init__(self, message: str, details: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(message, code=ErrorCode.PERMISSION_ERROR, details=details, **kwargs)


class TimeoutError(YanaBaseError):
    def __init__(self, message: str, details: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(message, code=ErrorCode.TIMEOUT_ERROR, details=details, **kwargs)


class NetworkError(YanaBaseError):
    def __init__(self, message: str, details: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(message, code=ErrorCode.NETWORK_ERROR, details=details, **kwargs)


class SystemError(YanaBaseError):
    def __init__(self, message: str, details: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(message, code=ErrorCode.SYSTEM_ERROR, details=details, **kwargs)


class MicrophoneUnavailableError(YanaBaseError):
    def __init__(self, message: str, details: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(
            message,
            code=ErrorCode.MICROPHONE_UNAVAILABLE,
            details=details,
            retryable=True,
            **kwargs,
        )


class SpeakerUnavailableError(YanaBaseError):
    def __init__(self, message: str, details: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(
            message,
            code=ErrorCode.SPEAKER_UNAVAILABLE,
            details=details,
            retryable=True,
            **kwargs,
        )


class SpeechToTextError(YanaBaseError):
    def __init__(self, message: str, details: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(
            message, code=ErrorCode.STT_ERROR, details=details, retryable=True, **kwargs
        )


class TextToSpeechError(YanaBaseError):
    def __init__(self, message: str, details: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(
            message, code=ErrorCode.TTS_ERROR, details=details, retryable=True, **kwargs
        )


class VoicePermissionDeniedError(YanaBaseError):
    def __init__(self, message: str, details: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(
            message,
            code=ErrorCode.VOICE_PERMISSION_DENIED,
            details=details,
            retryable=False,
            **kwargs,
        )


class SecurityError(YanaBaseError):
    def __init__(self, message: str, details: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(
            message,
            code=ErrorCode.SECURITY_ERROR,
            details=details,
            retryable=False,
            **kwargs,
        )


class LoopDetectedError(YanaBaseError):
    def __init__(self, message: str, details: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(
            message,
            code=ErrorCode.LOOP_DETECTED,
            details=details,
            retryable=False,
            **kwargs,
        )


class BrowserError(YanaBaseError):
    def __init__(self, message: str, details: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(
            message,
            code=ErrorCode.BROWSER_ERROR,
            details=details,
            retryable=False,
            **kwargs,
        )


class VoiceError(YanaBaseError):
    def __init__(self, message: str, details: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(
            message,
            code=ErrorCode.VOICE_ERROR,
            details=details,
            retryable=False,
            **kwargs,
        )

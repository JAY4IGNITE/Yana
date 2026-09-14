"""Tests for Standardized Error Model."""

from app.errors import ErrorCode, PermissionError, ValidationError, YanaBaseError


def test_error_codes_enum() -> None:
    assert ErrorCode.VALIDATION_ERROR == "VALIDATION_ERROR"
    assert ErrorCode.CONFIGURATION_ERROR == "CONFIGURATION_ERROR"
    assert ErrorCode.AI_ERROR == "AI_ERROR"
    assert ErrorCode.TOOL_ERROR == "TOOL_ERROR"
    assert ErrorCode.PERMISSION_ERROR == "PERMISSION_ERROR"
    assert ErrorCode.TIMEOUT_ERROR == "TIMEOUT_ERROR"
    assert ErrorCode.NETWORK_ERROR == "NETWORK_ERROR"
    assert ErrorCode.SYSTEM_ERROR == "SYSTEM_ERROR"


def test_safe_payload_generation() -> None:
    err = ValidationError("Invalid argument provided", details={"field": "app_name"}, task_id="t-1")
    payload = err.to_safe_payload()
    assert payload["code"] == "VALIDATION_ERROR"
    assert payload["message"] == "Invalid argument provided"
    assert payload["details"] == {"field": "app_name"}
    assert payload["taskId"] == "t-1"
    assert "traceback" not in payload


def test_permission_error_inheritance() -> None:
    err = PermissionError("Action disallowed")
    assert isinstance(err, YanaBaseError)
    assert err.code == ErrorCode.PERMISSION_ERROR

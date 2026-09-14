use serde_json::json;
use yana_desktop_lib::error::{DesktopError, ErrorCode, SafeCommandError};
use yana_desktop_lib::protocol::{PermissionRequestPayload, RiskLevel, ToolCallPayload, PROTOCOL_VERSION};

#[test]
fn test_protocol_version() {
    assert_eq!(PROTOCOL_VERSION, "1.0.0");
}

#[test]
fn test_risk_level_serialization() {
    let serialized = serde_json::to_string(&RiskLevel::High).unwrap();
    assert_eq!(serialized, "\"HIGH\"");
}

#[test]
fn test_tool_call_payload_deserialization() {
    let json_str = json!({
        "taskId": "task-abc",
        "tool": "system.open_application",
        "riskLevel": "MEDIUM",
        "arguments": {
            "app_name": "notepad"
        }
    })
    .to_string();

    let payload: ToolCallPayload = serde_json::from_str(&json_str).unwrap();
    assert_eq!(payload.task_id, "task-abc");
    assert_eq!(payload.tool, "system.open_application");
    assert_eq!(payload.risk_level, RiskLevel::Medium);
}

#[test]
fn test_safe_command_error_mapping() {
    let err = DesktopError::Validation("Invalid argument supplied".to_string());
    let safe_err: SafeCommandError = err.into();
    assert_eq!(safe_err.code, ErrorCode::ValidationError);
    assert_eq!(safe_err.message, "Invalid argument supplied");
}

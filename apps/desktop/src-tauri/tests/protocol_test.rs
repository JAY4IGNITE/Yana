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

#[test]
fn test_permission_request_deserialization() {
    let json_str = json!({
        "taskId": "task-xyz",
        "toolCallId": "call-123",
        "tool": "terminal.run_command",
        "riskLevel": "HIGH",
        "description": "Execute script",
        "arguments": { "command": "dir" }
    })
    .to_string();

    let req: PermissionRequestPayload = serde_json::from_str(&json_str).unwrap();
    assert_eq!(req.task_id, "task-xyz");
    assert_eq!(req.tool_call_id, "call-123");
    assert_eq!(req.risk_level, RiskLevel::High);
}

#[test]
fn test_window_status_serialization() {
    use yana_desktop_lib::commands::system::WindowStatus;
    let status = WindowStatus {
        mode: "collapsed".to_string(),
        always_on_top: true,
        is_visible: true,
    };
    let json_val = serde_json::to_value(&status).unwrap();
    assert_eq!(json_val["mode"], "collapsed");
    assert_eq!(json_val["always_on_top"], true);
    assert_eq!(json_val["is_visible"], true);
}

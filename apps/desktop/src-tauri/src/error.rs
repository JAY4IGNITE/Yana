use serde::Serialize;
use thiserror::Error;

#[derive(Debug, Serialize, PartialEq, Eq)]
pub enum ErrorCode {
    #[serde(rename = "VALIDATION_ERROR")]
    ValidationError,
    #[serde(rename = "CONFIGURATION_ERROR")]
    ConfigurationError,
    #[serde(rename = "AI_ERROR")]
    AiError,
    #[serde(rename = "TOOL_ERROR")]
    ToolError,
    #[serde(rename = "PERMISSION_ERROR")]
    PermissionError,
    #[serde(rename = "TIMEOUT_ERROR")]
    TimeoutError,
    #[serde(rename = "NETWORK_ERROR")]
    NetworkError,
    #[serde(rename = "SYSTEM_ERROR")]
    SystemError,
    #[serde(rename = "BROWSER_ERROR")]
    BrowserError,
    #[serde(rename = "VOICE_ERROR")]
    VoiceError,
}

#[derive(Debug, Error)]
pub enum DesktopError {
    #[error("Validation error: {0}")]
    Validation(String),
    #[error("Security error: {0}")]
    Security(String),
    #[error("System error: {0}")]
    System(String),
    #[error("Agent communication error: {0}")]
    Agent(String),
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
}

#[derive(Debug, Serialize)]
pub struct SafeCommandError {
    pub code: ErrorCode,
    pub message: String,
}

impl From<DesktopError> for SafeCommandError {
    fn from(err: DesktopError) -> Self {
        match err {
            DesktopError::Validation(msg) => SafeCommandError {
                code: ErrorCode::ValidationError,
                message: msg,
            },
            DesktopError::Security(msg) => SafeCommandError {
                code: ErrorCode::PermissionError,
                message: msg,
            },
            DesktopError::Agent(msg) => SafeCommandError {
                code: ErrorCode::NetworkError,
                message: msg,
            },
            DesktopError::System(msg) => SafeCommandError {
                code: ErrorCode::SystemError,
                message: msg,
            },
            DesktopError::Io(e) => SafeCommandError {
                code: ErrorCode::SystemError,
                message: e.to_string(),
            },
        }
    }
}

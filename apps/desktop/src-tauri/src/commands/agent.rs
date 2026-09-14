use serde::Serialize;
use crate::error::SafeCommandError;

#[derive(Debug, Serialize)]
pub struct DesktopInfo {
    pub os: String,
    pub arch: String,
    pub yana_version: String,
    pub protocol_version: String,
}

#[tauri::command]
pub async fn get_desktop_info() -> Result<DesktopInfo, SafeCommandError> {
    Ok(DesktopInfo {
        os: std::env::consts::OS.to_string(),
        arch: std::env::consts::ARCH.to_string(),
        yana_version: "0.1.0".to_string(),
        protocol_version: crate::protocol::PROTOCOL_VERSION.to_string(),
    })
}

#[tauri::command]
pub async fn ping_agent() -> Result<String, SafeCommandError> {
    Ok("pong".to_string())
}

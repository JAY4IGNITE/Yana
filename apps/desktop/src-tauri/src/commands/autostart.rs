use crate::error::{DesktopError, SafeCommandError};

const REG_KEY: &str = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run";
const APP_NAME: &str = "YANA";

#[tauri::command]
pub async fn get_launch_at_startup() -> Result<bool, SafeCommandError> {
    #[cfg(target_os = "windows")]
    {
        use std::process::Command;
        let output = Command::new("reg.exe")
            .args(["query", REG_KEY, "/v", APP_NAME])
            .output();

        match output {
            Ok(out) => Ok(out.status.success()),
            Err(_) => Ok(false),
        }
    }
    #[cfg(not(target_os = "windows"))]
    {
        Ok(false)
    }
}

#[tauri::command]
pub async fn set_launch_at_startup(enable: bool) -> Result<bool, SafeCommandError> {
    #[cfg(target_os = "windows")]
    {
        use std::process::Command;
        if enable {
            let current_exe = std::env::current_exe()
                .map_err(|e| DesktopError::System(format!("Failed to locate current executable: {}", e)))?;
            let exe_str = current_exe.to_string_lossy().to_string();

            let status = Command::new("reg.exe")
                .args(["add", REG_KEY, "/v", APP_NAME, "/t", "REG_SZ", "/d", &format!("\"{}\"", exe_str), "/f"])
                .status()
                .map_err(|e| DesktopError::System(format!("Failed to register startup key: {}", e)))?;

            Ok(status.success())
        } else {
            let status = Command::new("reg.exe")
                .args(["delete", REG_KEY, "/v", APP_NAME, "/f"])
                .status()
                .map_err(|e| DesktopError::System(format!("Failed to delete startup key: {}", e)))?;

            Ok(status.success())
        }
    }
    #[cfg(not(target_os = "windows"))]
    {
        Ok(enable)
    }
}

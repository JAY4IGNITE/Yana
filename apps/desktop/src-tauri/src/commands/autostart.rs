use crate::error::{DesktopError, SafeCommandError};

const REG_KEY: &str = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run";
const APP_NAME: &str = "YANA";

#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x08000000;

#[tauri::command]
pub async fn get_launch_at_startup() -> Result<bool, SafeCommandError> {
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        use std::process::Command;

        let output = Command::new("reg.exe")
            .creation_flags(CREATE_NO_WINDOW)
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
        use std::os::windows::process::CommandExt;
        use std::process::Command;

        if enable {
            let current_exe = std::env::current_exe()
                .map_err(|e| DesktopError::System(format!("Failed to locate current executable: {}", e)))?;
            let exe_str = current_exe.to_string_lossy().to_string();

            let status = Command::new("reg.exe")
                .creation_flags(CREATE_NO_WINDOW)
                .args(["add", REG_KEY, "/v", APP_NAME, "/t", "REG_SZ", "/d", &format!("\"{}\"", exe_str), "/f"])
                .status()
                .map_err(|e| DesktopError::System(format!("Failed to register startup key: {}", e)))?;

            Ok(status.success())
        } else {
            let status = Command::new("reg.exe")
                .creation_flags(CREATE_NO_WINDOW)
                .args(["delete", REG_KEY, "/v", APP_NAME, "/f"])
                .status()
                .map_err(|e| DesktopError::System(format!("Failed to delete startup key: {}", e)))?;

            // Exit code 0 means deleted; exit code 1 means key did not exist (idempotent success)
            Ok(status.success() || status.code() == Some(1))
        }
    }
    #[cfg(not(target_os = "windows"))]
    {
        Ok(enable)
    }
}

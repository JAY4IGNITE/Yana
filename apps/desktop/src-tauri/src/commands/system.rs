use crate::error::SafeCommandError;
use tauri::AppHandle;

#[tauri::command]
pub async fn minimize_window(app: AppHandle) -> Result<(), SafeCommandError> {
    use tauri::Manager;
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.minimize();
    }
    Ok(())
}

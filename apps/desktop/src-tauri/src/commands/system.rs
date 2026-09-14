use crate::error::SafeCommandError;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, LogicalSize, Manager};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WindowStatus {
    pub mode: String,
    pub always_on_top: bool,
    pub is_visible: bool,
}

#[tauri::command]
pub async fn set_window_mode(app: AppHandle, mode: String) -> Result<(), SafeCommandError> {
    if let Some(window) = app.get_webview_window("main") {
        match mode.as_str() {
            "expanded" => {
                let _ = window.set_size(LogicalSize::new(380.0, 540.0));
                let _ = window.set_resizable(true);
            }
            "collapsed" | _ => {
                let _ = window.set_size(LogicalSize::new(180.0, 220.0));
                let _ = window.set_resizable(true);
            }
        }
    }
    Ok(())
}

#[tauri::command]
pub async fn set_always_on_top(app: AppHandle, always_on_top: bool) -> Result<(), SafeCommandError> {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.set_always_on_top(always_on_top);
    }
    Ok(())
}

#[tauri::command]
pub async fn set_pet_scale(app: AppHandle, scale: String) -> Result<(), SafeCommandError> {
    if let Some(window) = app.get_webview_window("main") {
        match scale.as_str() {
            "small" => {
                let _ = window.set_size(LogicalSize::new(150.0, 185.0));
            }
            "large" => {
                let _ = window.set_size(LogicalSize::new(220.0, 270.0));
            }
            "medium" | _ => {
                let _ = window.set_size(LogicalSize::new(180.0, 220.0));
            }
        }
    }
    Ok(())
}

#[tauri::command]
pub async fn show_window(app: AppHandle) -> Result<(), SafeCommandError> {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.set_focus();
    }
    Ok(())
}

#[tauri::command]
pub async fn hide_window(app: AppHandle) -> Result<(), SafeCommandError> {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.hide();
    }
    Ok(())
}

#[tauri::command]
pub async fn toggle_window(app: AppHandle) -> Result<bool, SafeCommandError> {
    if let Some(window) = app.get_webview_window("main") {
        let is_visible = window.is_visible().unwrap_or(false);
        if is_visible {
            let _ = window.hide();
            return Ok(false);
        } else {
            let _ = window.show();
            let _ = window.set_focus();
            return Ok(true);
        }
    }
    Ok(false)
}

#[tauri::command]
pub async fn minimize_window(app: AppHandle) -> Result<(), SafeCommandError> {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.minimize();
    }
    Ok(())
}

#[tauri::command]
pub async fn close_window(app: AppHandle) -> Result<(), SafeCommandError> {
    app.exit(0);
    Ok(())
}

pub mod agent_supervisor;
pub mod commands;
pub mod error;
pub mod protocol;
pub mod updater;

use tauri::menu::{Menu, MenuItem};
use tauri::tray::{TrayIconBuilder, TrayIconEvent};
use tauri::{Emitter, Manager};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutState};

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .setup(|app| {
            // Build Native System Tray Menu
            let show_i = MenuItem::with_id(app, "show", "Open YANA", true, None::<&str>)?;
            let hide_i = MenuItem::with_id(app, "hide", "Hide YANA", true, None::<&str>)?;
            let settings_i = MenuItem::with_id(app, "settings", "Settings", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Quit YANA", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_i, &hide_i, &settings_i, &quit_i])?;

            let _tray = TrayIconBuilder::new()
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "quit" => {
                        app.exit(0);
                    }
                    "hide" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.hide();
                        }
                    }
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    "settings" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                            let _ = window.emit("open-settings", ());
                        }
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: tauri::tray::MouseButton::Left,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            if window.is_visible().unwrap_or(false) {
                                let _ = window.hide();
                            } else {
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                        }
                    }
                })
                .icon(app.default_window_icon().unwrap().clone())
                .build(app)?;

            // Register Global Shortcut: Ctrl + Space
            let shortcut: Shortcut = "Ctrl+Space".parse().unwrap();
            let app_handle = app.handle().clone();
            let _ = app.global_shortcut().on_shortcut(shortcut, move |_app, _shortcut, event| {
                if event.state == ShortcutState::Pressed {
                    if let Some(window) = app_handle.get_webview_window("main") {
                        let _ = window.show();
                        let _ = window.unminimize();
                        let _ = window.set_focus();
                        let _ = window.emit("global-shortcut-triggered", ());
                    }
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::agent::get_desktop_info,
            commands::agent::ping_agent,
            commands::autostart::get_launch_at_startup,
            commands::autostart::set_launch_at_startup,
            commands::system::set_window_mode,
            commands::system::set_always_on_top,
            commands::system::set_pet_scale,
            commands::system::show_window,
            commands::system::hide_window,
            commands::system::toggle_window,
            commands::system::minimize_window,
            commands::system::close_window,
            updater::check_for_updates,
            agent_supervisor::get_agent_supervisor_status,
            agent_supervisor::restart_agent_service,
            agent_supervisor::report_agent_heartbeat,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

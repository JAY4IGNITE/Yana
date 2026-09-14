pub mod commands;
pub mod error;
pub mod protocol;

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            commands::agent::get_desktop_info,
            commands::agent::ping_agent,
            commands::system::minimize_window,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

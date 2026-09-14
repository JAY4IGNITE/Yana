# Desktop Architecture (Tauri 2 + React)

The YANA Desktop application is built with **Tauri 2** (Rust) and **React 18** with **TypeScript** and **Tailwind CSS**.

## Separation of Concerns

- **React UI Responsibilities**:
  - Rendering the animated AI Pet with state transitions (`idle`, `listening`, `thinking`, `executing`, `verifying`, `success`, `error`, `sleeping`).
  - Conversation feed and quick action bar.
  - Multi-step task progress visualization.
  - Interactive permission prompt dialogs for user authorization.
  - Visual settings and connectivity diagnostics.
  - **Rule**: React components must NEVER contain operating system logic or direct process execution.

- **Tauri 2 / Rust Responsibilities**:
  - Native Windows desktop windowing (custom frameless chrome, transparency, always-on-top mode).
  - Windows System Tray integration with context menu.
  - Global hotkeys (e.g. summoning YANA from anywhere).
  - Secure IPC command routing.
  - Process lifecycle management (launching and monitoring the Python agent daemon).
  - OS-level error translation into safe error structures.

## Tauri IPC Commands

All native commands are registered in `apps/desktop/src-tauri/src/lib.rs` and return typed `Result<T, SafeCommandError>`.

| Command | Signature | Description |
| :--- | :--- | :--- |
| `get_desktop_info` | `() -> Result<DesktopInfo, SafeCommandError>` | Retrieves host OS, architecture, and protocol version. |
| `ping_agent` | `() -> Result<String, SafeCommandError>` | Healthcheck IPC ping. |
| `minimize_window` | `(app: AppHandle) -> Result<(), SafeCommandError>` | Minimizes the desktop companion window to the system tray. |

## UI Design Tokens & Theme

The desktop UI uses a sleek dark glassmorphism palette:
- `yana-bg`: `#0B0F19` (Deep Obsidian)
- `yana-card`: `#121A29` (Translucent Slate)
- `yana-primary`: `#38BDF8` (Sky Blue)
- `yana-secondary`: `#818CF8` (Soft Indigo)
- `yana-accent`: `#F43F5E` (Rose Pink)
- `yana-success`: `#10B981` (Emerald)
- `yana-warning`: `#F59E0B` (Amber)

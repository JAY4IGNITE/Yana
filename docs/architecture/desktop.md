# Desktop Architecture (Tauri 2 + React)

The YANA Desktop application is built with **Tauri 2** (Rust) and **React 18** with **TypeScript** and **Tailwind CSS**.

---

## Dual-Mode Windowing Architecture

YANA operates in two primary visual modes:

1. **Collapsed Floating Pet Mode**:
   - Compact desktop companion (~180×220px, scalable from 150×185px to 220×270px).
   - Fully **transparent**, **frameless**, and **draggable** (`data-tauri-drag-region`).
   - Floats directly above the user's desktop with zero rectangular box or border.
   - Hover reveals quick controls: size scaling (`small`/`medium`/`large`), pin toggle (`alwaysOnTop`), and expansion trigger.
   - Clicking on the pet body expands the interface.

2. **Expanded Assistant Mode**:
   - Smoothly resizes to ~380×540px.
   - Displays a sleek dark glassmorphism card (`.glass-card`).
   - Contains:
     - Header with title, pin toggle, settings icon, and collapse button.
     - Animated compact pet with live status indicator.
     - Conversation stream area.
     - Command bar with text input, microphone dictation control, stop button, and send action.
   - Pressing `Escape` or clicking the minimize button instantly collapses back to the floating pet.

---

## Native Windows Shell Integration

- **Transparent Frameless Window**:
  Configured in `tauri.conf.json` with `transparent: true`, `decorations: false`, `alwaysOnTop: true`, and `shadow: false` (to prevent rectangular DWM shadow boxes around the transparent pet).
- **System Tray**:
  Built natively with `TrayIconBuilder`:
  - **Left Click**: Toggles hide/show of the desktop pet.
  - **Right Click Menu**:
    - `Open YANA` (shows and focuses window)
    - `Hide YANA` (hides window from desktop)
    - `Settings` (opens placeholder settings view)
    - `Quit YANA` (cleanly terminates process)
- **Global Shortcut**:
  Registered with `tauri-plugin-global-shortcut` (default: `Ctrl + Space`):
  - Automatically un-minimizes YANA, brings it to the foreground, expands into the assistant interface, and focuses the command input.
- **Hardware-Accelerated Pet Animations**:
  Animations use GPU-accelerated CSS `transform` and `opacity` properties, with strict `@media (prefers-reduced-motion: reduce)` fallbacks for accessibility.

---

## Registered Tauri IPC Commands

All native commands are registered in `apps/desktop/src-tauri/src/lib.rs`:

| Command | Signature | Description |
| :--- | :--- | :--- |
| `get_desktop_info` | `() -> Result<DesktopInfo, SafeCommandError>` | Retrieves host OS, architecture, and protocol version. |
| `ping_agent` | `() -> Result<String, SafeCommandError>` | IPC healthcheck ping. |
| `set_window_mode` | `(mode: String) -> Result<(), SafeCommandError>` | Dynamically adjusts window size between collapsed pet (~180×220) and expanded assistant (~380×540). |
| `set_always_on_top` | `(always_on_top: bool) -> Result<(), SafeCommandError>` | Toggles whether YANA stays on top of other Windows desktop windows. |
| `set_pet_scale` | `(scale: String) -> Result<(), SafeCommandError>` | Adjusts collapsed pet size (`small`, `medium`, `large`). |
| `show_window` | `() -> Result<(), SafeCommandError>` | Shows and focuses the desktop window. |
| `hide_window` | `() -> Result<(), SafeCommandError>` | Hides the window to the system tray. |
| `toggle_window` | `() -> Result<bool, SafeCommandError>` | Toggles visibility state. |
| `minimize_window` | `() -> Result<(), SafeCommandError>` | Minimizes the window. |
| `close_window` | `() -> Result<(), SafeCommandError>` | Cleanly exits the desktop application. |

---

## The 8-State Pet Animation System

The robotic companion character responds visually to 8 discrete states:

| State | Visual Behavior | Eyes / Visor | Aura Color |
| :--- | :--- | :--- | :--- |
| `IDLE` | Subtle gentle breathing float | Calm, receptive oval eyes | Cyan (`#38BDF8`) |
| `LISTENING` | Attentive posture, antenna ping | Wide oval eyes with audio pulse | Deep Cyan (`#0284C7`) |
| `THINKING` | Visor scan line sweeping horizontally | Focused narrowed eyes | Indigo (`#818CF8`) |
| `SPEAKING` | Rhythmic mouth soundwave modulation | Communicative expressive eyes | Electric Cyan (`#06B6D4`) |
| `EXECUTING` | Activity pulse and gear indicators | Alert rapid eyes | Amber (`#F59E0B`) |
| `SUCCESS` | Cheerful floating bounce, blushing cheeks | Crescent happy eyes, smiling mouth | Emerald (`#10B981`) |
| `ERROR` | Warning badge, glitch animation | Alert cross eyes | Rose/Red (`#F43F5E`) |
| `OFFLINE` | Dimmed shell chassis | Closed resting curved eyes | Slate/Muted (`#334155`) |

# Manual Desktop Testing Checklist (Native Windows Companion)

This checklist provides step-by-step instructions for validating native Windows capabilities that require visual and OS-level verification.

---

## Prerequisites

1. Run the development environment:
   ```powershell
   .\scripts\dev.ps1
   ```
2. Or launch the native Tauri window directly:
   ```powershell
   npm run dev:tauri
   ```

---

## Test Scenarios

### 1. Transparent & Frameless Window
- [ ] **Appearance**: When YANA launches in collapsed mode, only the floating robotic pet is visible over your desktop wallpaper.
- [ ] **No Black/White Box**: Verify there is no solid rectangular container or black box surrounding the pet.
- [ ] **DWM Shadow**: Verify there is no rectangular shadow box behind the transparent window.

### 2. Desktop Movement & Dragging
- [ ] **Drag Action**: Click and drag anywhere on the pet body or container.
- [ ] **Movement**: Verify the pet smoothly moves across your desktop monitor and can be positioned anywhere.

### 3. Pet Sizing & Scale Cycling
- [ ] **Hover**: Move cursor over the pet to reveal the control overlay in the top right.
- [ ] **Zoom/Scale**: Click the zoom button (`ZoomIn` icon) to cycle through:
  - Small (~150×185px)
  - Medium (~180×220px)
  - Large (~220×270px)
- [ ] **Visual Clarity**: Verify SVG crispness and glowing eyes at all sizes.

### 4. Expansion & Collapse Interaction
- [ ] **Click Expand**: Click on the pet body or the expand icon (`Maximize2`).
- [ ] **Assistant View**: Window smoothly resizes to ~380×540px and displays:
  - Header with YANA title, pin toggle, settings icon, and collapse button.
  - Compact animated pet character with status indicator.
  - Clean conversation history feed.
  - Bottom input bar: `[ Ask YANA... ]` with microphone and send buttons.
- [ ] **Escape Key**: Press `Escape` while focused on the assistant to collapse back to the floating pet.
- [ ] **Minimize Button**: Click the minimize icon in the header to collapse back to the floating pet.

### 5. Always-On-Top (Pinning)
- [ ] **Toggle Pin**: Click the pin icon in the hover controls or assistant header.
- [ ] **Verification**: When pinned, YANA stays visible above other maximized windows (e.g. Chrome, VS Code, Notepad). When unpinned, other windows can occlude YANA.

### 6. System Tray Integration
- [ ] **Tray Icon**: Confirm the YANA icon appears in the Windows System Tray (near the taskbar clock).
- [ ] **Left-Click**: Single left-click toggles hide/show of the YANA desktop pet.
- [ ] **Right-Click Context Menu**: Verify menu items:
  - `Open YANA` (shows and focuses window)
  - `Hide YANA` (hides pet from desktop)
  - `Settings` (brings up settings modal)
  - `Quit YANA` (cleanly exits application)

### 7. Global Shortcut (`Ctrl + Space`)
- [ ] **Hotkey Test**: Minimize or defocus YANA. Press `Ctrl + Space` anywhere in Windows.
- [ ] **Result**: YANA immediately unminimizes, comes to foreground, expands to assistant view, and focuses the command input ready for typing.

### 8. Pet State Animations
- [ ] **IDLE**: Gentle breathing float and calm cyan eyes.
- [ ] **LISTENING**: Click mic icon or send message. Eyes widen and antenna tips ping.
- [ ] **THINKING**: Visor horizontal scan line sweeps across face.
- [ ] **SPEAKING**: Soundwave bars modulate in the mouth area.
- [ ] **EXECUTING**: Rapid activity indicator with amber alert glow.
- [ ] **SUCCESS**: Cheerful crescent happy eyes, blushing cheeks, emerald aura.
- [ ] **ERROR**: Red alert cross eyes with warning badge.
- [ ] **OFFLINE**: Dimmed shell and closed resting curve eyes.
- [ ] **Reduced Motion**: Under Windows Settings > Accessibility > Visual Effects > Animation Effects (Off), verify that continuous float and pulse animations are disabled.

# Assistant repair verification

The repair connects the desktop controls to actual agent and audio operations, removes misleading fallback success, and makes startup failures visible.

## Changes

- Chat and Control my PC are separate, selectable modes. Task execution blocks duplicate submissions and displays tool results.
- Streaming failures and cancellation release the interface. A late speech transcript cannot start a task after Stop.
- Microphone capture records locally, converts audio to mono 16 kHz WAV, and sends it to the speech provider. Chat voice replies play through the webview.
- Provider authentication errors retain their real error type. Tier routing uses configured providers, models, and credentials; it does not substitute mock responses after a real failure.
- When AI planning fails, only explicit basic commands have deterministic recovery. The fallback no longer invents file content, filenames, or coordinates.
- The native shell starts its Python service, checks readiness, recovers from service crashes, and terminates its owned process tree on shutdown.
- Packaging includes the Python executable. Setup preserves existing configuration. Installed configuration can be read from `%LOCALAPPDATA%\YANA\.env`.
- Settings and task results fit the 380 × 540 desktop window. Wake-word detection and automatic updates report their unavailable state.
- Browser automation falls back to installed Edge/Chrome when Playwright Chromium is absent. Closed browser windows and contexts recover, concurrent initialization shares one session, and shutdown closes the owned browser session.
- Settings exposes Restart while connected, prevents duplicate restart requests, and shows native errors or browser-preview instructions.

## Verified paths

- Python regression suite: 285 passing tests, including nine new browser initialization, recovery, and shutdown regressions.
- Frontend regression suite: 63 passing tests; TypeScript and Vite build pass.
- Rust suite: 14 passing tests, including owned process-tree shutdown.
- Chromium: read-only system-information task, visible output, accessible composer at native window size, Settings restart feedback, audio settings, synthetic microphone recording, WAV upload, and transcript-to-task routing. No browser page errors.
- Native release runtime: bundled service startup, automatic recovery after terminating its own test service, and service shutdown when the desktop window closes. Tests use temporary storage and mock providers.
- Frozen Python executable: startup, a real read-only system-information task, browser navigation/reading with no developer Chromium cache, and process cleanup pass on an isolated port with temporary storage and mock AI providers. The standard bundle is 90,915,352 bytes after excluding optional Laya/Torch dependencies. First launch can take longer while Windows scans and unpacks the executable.
- Final Windows NSIS installer build succeeds: `apps/desktop/src-tauri/target/release/bundle/nsis/YANA_0.1.0_x64-setup.exe` (85,725,188 bytes). SHA-256: `97B853D5F62BF5EE47CCEA3DEB3194592D72B1AFB6CB8E3C968747E5CD53ACF9`. This verifies packaging, not installation on a clean machine.

## Remaining validation

The last live NVIDIA inference request was rejected for authorization. The user has not yet updated the key; real chat and AI-generated plans need a successful provider check after that update. Endpoint health alone does not prove access to a chosen inference model.

Browser audio checks use a synthetic microphone and stubbed transcription response. They verify recording and routing, not the user's microphone, NVIDIA speech recognition, or audible Cartesia playback. Those require working service credentials and hardware validation.

Wake-word detection and automatic update delivery are not implemented. A full NSIS installation on a clean PC has not been tested.

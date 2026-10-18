# YANA — Windows personal AI assistant

YANA combines a Tauri desktop window, a React interface, and a local Python agent. Chat answers and PC actions use separate modes. PC actions run through registered tools, permission checks, and result verification.

## Setup and launch

Requirements: Windows 10/11, Node.js 20+, Python 3.11+, uv, Rust/Cargo, and Visual Studio C++ Build Tools.

```powershell
.\scripts\setup.ps1
# Edit .env with your provider configuration, then:
npm run dev:tauri
```

The desktop starts and supervises the local agent on `127.0.0.1:8765`. You do not need to launch Python separately. `scripts/dev.ps1` starts the same native workflow; `scripts/dev.ps1 -Browser` starts a browser preview and Python instead. Browser preview does not provide native tray, startup, or window controls.

Setup creates `.env` only when it is missing. Keep API keys in that file; never put them in chat, screenshots, or source control. Restart the agent after editing configuration.

In the native desktop app, **Settings → General & Security → Restart** is available even while the agent is connected. It shows progress and reports startup errors. Browser preview uses a separately started agent; restart that agent in its terminal.

## Configure real AI

The example configuration uses `mock` for offline demonstrations. Mock responses are not real AI. For NVIDIA, configure:

```dotenv
YANA_AI_PROVIDER=nvidia
YANA_AI_BASE_URL=https://integrate.api.nvidia.com/v1
YANA_AI_MODEL=<a model your NVIDIA account can access>
YANA_AI_API_KEY=<your key>
YANA_AI_ROUTING_MODE=local
YANA_PLANNER_MODE=auto
```

For compatibility, routing mode `local` uses the primary `YANA_AI_PROVIDER` configuration, which may be a cloud provider. `auto` enables tier routing between the separately configured local, heavy, and fallback providers. `heavy` and `fallback` force their respective tier. Supply the matching URL, model, and API key for each cloud tier. A key is reused for the heavy tier only when the provider and endpoint match.

For local inference, set the primary provider to `ollama`, base URL to `http://localhost:11434/v1`, and model to a model already installed in Ollama. Ollama must be running.

Authentication failures appear as errors. Check both the key and model entitlement. Endpoint health does not guarantee inference access to every model. Automatic routing never silently substitutes mock answers.

## Use the assistant

- **Chat** answers questions and stores conversation history locally.
- **Control my PC** plans and executes a task. Review permission prompts before approving tools. Expand **View result** to read each tool's output.
- Basic offline commands include `show system info`, `take a screenshot`, `open app notepad.exe`, and `read file "C:\path\file.txt"`. More complex tasks require working AI. If planning fails, the assistant does not invent filenames, coordinates, or file content.
- The microphone button and **Ctrl+Shift+Space** toggle voice recording. Click again to transcribe. Transcripts follow the selected Chat or Control my PC mode.
- **Stop** cancels current generation, recording, or task execution. Completed actions cannot be undone by cancelling a later step.
- Settings provides audio device selection, memory controls, native startup settings, and agent restart.

Browser automation uses Playwright Chromium when installed. On Windows, if that browser is missing, it tries installed Microsoft Edge, then Google Chrome using an isolated automation profile. The installer does not contain a Chromium download. At least one supported browser is required. Closed automation windows and contexts are recovered on the next browser action; agent shutdown closes its automation session. Browser channel support follows the [Playwright browser documentation](https://playwright.dev/python/docs/browsers).

## Voice configuration

Voice capture uses the browser/webview microphone permission and uploads mono 16 kHz WAV to the agent. Recordings are limited to two minutes. Transcription requires a working speech service; cloud transcription sends that recording to the configured provider.

```dotenv
YANA_STT_PROVIDER=nvidia_parakeet
YANA_STT_API_KEY=<NVIDIA speech key>
YANA_STT_MODEL=nvidia/parakeet-ctc-1.1b-asr
YANA_STT_BASE_URL=https://1598d209-5e27-4d3c-8079-4751568b1081.invocation.api.nvcf.nvidia.com/v1
YANA_TTS_PROVIDER=edge_tts
```

The speech endpoint is separate from the chat endpoint. Cartesia playback instead requires `YANA_TTS_PROVIDER=cartesia`, `YANA_CARTESIA_API_KEY`, and `YANA_CARTESIA_VOICE_ID`. Edge TTS requires internet access. Voice chat replies play through the selected output device when the webview supports output selection.

Wake-word detection is not implemented in the desktop capture path, so its switch is disabled. Use the microphone button or keyboard shortcut. Actual microphone hardware and cloud STT/TTS need separate validation on the target PC.

## Packaging

```powershell
npm run build             # TypeScript and frontend bundle
npm run build:prod        # Python executable and Rust release executable
npm run build:installer   # Python executable and NSIS desktop installer
```

The installer build includes `yana-agent.exe` as a resource; no API keys are bundled. The PyInstaller spec uses the current [spec-file format](https://pyinstaller.org/en/latest/spec-files.html). For an installed app, create `%LOCALAPPDATA%\YANA\.env` with your configuration. Production data is stored in `%LOCALAPPDATA%\YANA\data`. Agent logs are in Tauri's application log folder (`%LOCALAPPDATA%\com.yana.desktop\logs\agent.log` on Windows).

Automatic updates are not configured. The app reports that limitation instead of claiming an update or signature was verified. Optional Laya intent routing is disabled by default to avoid model downloads and startup delays; AI task planning does not require it.

Standard installers exclude the optional Laya/Torch runtime to reduce size and first-launch delay. For a build that includes it, set `$env:YANA_BUNDLE_INTENT_ROUTER='1'` before building, then enable `YANA_INTENT_ROUTER_ENABLED` in the agent configuration.

## Verification

```powershell
npm run test:frontend
npm run build
cd apps\agent
.\.venv\Scripts\python.exe -m pytest -q
cd ..\desktop\src-tauri
cargo test --offline
```

`scripts/browser_smoke.py` checks a read-only PC task, Settings restart feedback, and synthetic microphone capture against the running browser preview and agent. Its transcription response is stubbed; it does not verify cloud recognition. `scripts/native_smoke.py --release` checks bundled agent startup, recovery after terminating its own test service, and shutdown when the desktop closes. Run that check with the independent agent stopped and the agent executable beside the release desktop. `scripts/packaged_agent_smoke.py` tests the frozen service, a read-only system-information task, and browser automation without a developer Chromium cache on an isolated port. The native and packaged checks use temporary data and mock AI providers.

This is a working development project, not a claim that every application or arbitrary instruction can be automated. Tool availability, Windows permissions, model quality, and provider access affect results. The tests cover specific paths; they are not 100% coverage.

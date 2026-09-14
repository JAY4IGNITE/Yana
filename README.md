# YANA — Personal Native Windows AI Desktop Companion

> **YANA** is a professional native Windows desktop AI companion that lives on the user's desktop, featuring an expressive animated AI pet, natural language understanding, multi-step task execution, and safe, permission-governed tool operation.

---

## Key Capabilities

- 🤖 **Animated AI Desktop Pet**: Expressive robot companion with state transitions (`idle`, `listening`, `thinking`, `executing`, `verifying`, `success`, `error`, `sleeping`), micro-animations, and interactive responses.
- 🔒 **Critical Security Invariant**: The AI **never** directly controls the operating system. All actions flow through a strict validation, permission authorization, and user consent pipeline:
  ```
  USER -> YANA UI -> DESKTOP IPC -> AGENT -> PLANNER -> TOOL REGISTRY
  -> PERMISSION MANAGER -> EXECUTOR -> OPERATING SYSTEM -> VERIFIER -> AGENT -> YANA UI
  ```
- 📦 **Windows 10 & 11 Production Packaging**: Native NSIS standalone installer with uninstaller, desktop shortcut, start menu entry, and `CurrentUser` sandbox mode requiring zero administrative elevation.
- 🚀 **Windows Startup & System Tray**: Native system tray integration (Open, Hide, Settings, Quit), minimize-to-tray, and optional Windows boot auto-launch (`HKCU\Run`).
- 🛡️ **Crash Recovery & Process Supervisor**: Exponential backoff restart supervisor with an automated circuit breaker (3 strikes / 60s) preventing restart loops.
- 🔐 **Secure Update Architecture**: Pre-configured cryptographic update verification (Ed25519 signature validation, HTTPS-only manifests) avoiding unsafe self-updating.
- 🎙️ **Natural Voice Interaction**: Complete voice pipeline with Push-to-Talk, Wake Word ("Hey Yana"), STT/TTS provider abstractions, and audio device selection.
- 💾 **Persistent SQLite Memory System**: Multi-tiered local storage for long-term memory, session context, project workspaces, and user preferences with automatic credential redaction.
- 🧪 **100% Automated Test Coverage**: Comprehensive test suites across Rust Core (`cargo test`), Frontend UI (`vitest`), and Python Agent (`pytest`).

---

## Monorepo Architecture

```text
yana/
├── apps/
│   ├── desktop/                      # Tauri 2 + React Desktop Companion
│   │   ├── src/                      # React 18 / Vite UI (Pet, Chat, Permissions, TaskView, Settings)
│   │   ├── src-tauri/                # Tauri 2 Native Rust Core, Supervisor & IPC
│   │   ├── package.json
│   │   └── vite.config.ts
│   └── agent/                        # Python AI Agent Core (FastAPI, Pydantic, asyncio)
│       ├── app/                      # Core modules: api, core, tools, permissions, memory, ai, voice
│       ├── tests/                    # pytest test suite (230+ tests)
│       ├── yana_agent.spec           # PyInstaller bundling specification
│       └── pyproject.toml
├── packages/
│   ├── protocol/                     # Typed IPC Protocol contracts & ErrorCodes
│   └── shared-types/                 # Shared UI & domain models (Pet states, Task items)
├── docs/                             # Comprehensive Architecture, Security, and Build guides
├── scripts/                          # Build, test, lint, and verification automation
├── .github/workflows/ci.yml          # GitHub Actions matrix CI pipeline
├── .env.example                      # Documented environment configuration template
└── README.md
```

---

## Requirements

- **Windows**: Windows 10 or 11 (64-bit)
- **Node.js**: `v20+` or `v22+` (with npm `10+`)
- **Python**: `v3.11+` (with `uv` recommended)
- **Rust Toolchain**: `rustc` & `cargo` (`1.80+`)
- **Visual Studio C++ Build Tools** (for native Windows compilation)

---

## Getting Started

### 1. Configure Environment
```powershell
Copy-Item .env.example .env
```

### 2. Install Dependencies
```powershell
# Install Node packages across all workspaces
npm install

# Install Python agent dependencies
cd apps\agent
uv sync --all-extras
cd ..\..
```

---

## Running Development Services

```powershell
.\scripts\dev.ps1
```
This starts both the Python Agent (port `8765`) and the Desktop UI dev server (port `5173`).

Or run individually:
- **Agent Service**: `cd apps\agent; uv run uvicorn app.main:app --port 8765 --reload`
- **Desktop UI**: `npm run dev:desktop`
- **Tauri Native Window**: `npm run dev:tauri`

---

## Production Packaging & Builds

### 1. Pre-Flight Security Verifier
```powershell
npm run verify:prod
```
Audits the codebase for unredacted credentials, debug endpoints, and verifies production invariants.

### 2. Compile Production Bundle
```powershell
npm run build:prod
```
Compiles TypeScript packages, Vite production bundle, and Rust release binary.

### 3. Generate Windows NSIS Installer
```powershell
npm run build:installer
```
Generates `YANA_0.1.0_x64-setup.exe` in `apps/desktop/src-tauri/target/release/bundle/nsis/`.

---

## Running Test Suites

Execute all test suites across the stack with a single command:
```powershell
.\scripts\test.ps1
```

Or target specific layers:
- **Python Agent (pytest)**: `cd apps\agent; uv run pytest -v`
- **Frontend Components (Vitest)**: `npm run test:frontend`
- **Rust Tauri Core (Cargo test)**: `cd apps\desktop\src-tauri; cargo test`

---

## Quality Checks & Linting

```powershell
.\scripts\lint.ps1
```
Validates code with:
- **TypeScript**: `tsc --noEmit` across all workspaces
- **Python**: `ruff check .`, `ruff format --check .`, and `mypy app tests`
- **Rust**: `cargo check`

---

## Documentation

- [System Architecture](docs/architecture/system-overview.md)
- [Secure Update Architecture](docs/architecture/updates.md)
- [Desktop Layer (Tauri 2 + React)](docs/architecture/desktop.md)
- [Agent Core (Python + FastAPI)](docs/architecture/agent.md)
- [Communication Protocol](docs/architecture/protocol.md)
- [Security Model & 15 Core Rules](docs/security/security-model.md)
- [Phase 13 Final Security Audit](docs/security/security-audit.md)
- [Reproducible Build Guide](docs/development/build.md)
- [Windows Troubleshooting Guide](docs/development/troubleshooting.md)
- [Developer Setup Guide](docs/development/setup.md)

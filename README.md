# YANA — Personal Native Windows AI Desktop Companion

> **YANA** is a professional native Windows desktop AI companion that lives on the user's desktop, featuring an expressive animated AI pet, natural language understanding, multi-step task execution, and safe, permission-governed tool operation.

---

## Key Capabilities (Phase 00 Foundation)

- 🤖 **Animated AI Desktop Pet**: Expressive robot companion with state transitions (`idle`, `listening`, `thinking`, `executing`, `verifying`, `success`, `error`, `sleeping`) and interactive responses.
- 🔒 **Critical Security Invariant**: The AI **never** directly controls the operating system. All actions flow through a strict validation and user consent pipeline:
  ```
  USER -> YANA UI -> DESKTOP IPC -> AGENT -> PLANNER -> TOOL REGISTRY
  -> PERMISSION MANAGER -> EXECUTOR -> OPERATING SYSTEM -> VERIFIER -> AGENT -> YANA UI
  ```
- 📜 **Type-Safe IPC Protocol**: Bi-directional, versioned (`v1.0.0`) protocol contract implemented in TypeScript (`packages/protocol`) and Pydantic v2 (`apps/agent/app/protocol`).
- 🛡️ **Risk Gating & Permission Dialog**: Tools declare risk levels (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`). Sensitive and system operations require explicit user authorization before execution.
- 💾 **Async SQLite Storage Engine**: Relational storage for tasks, execution steps, and conversation history with clean migration boundaries.
- 🧪 **Multi-Layer Quality Assurance**: Comprehensive automated test suites across Frontend (Vitest), Agent (pytest), and Desktop Core (Cargo tests).

---

## Monorepo Architecture

```text
yana/
├── apps/
│   ├── desktop/                      # Tauri 2 + React Desktop Application
│   │   ├── src/                      # React 18 / Vite UI (Pet, Chat, Permissions, TaskView, Settings)
│   │   ├── src-tauri/                # Tauri 2 Native Rust Core & IPC handlers
│   │   ├── package.json
│   │   └── vite.config.ts
│   └── agent/                        # Python AI Agent Core (FastAPI, Pydantic, asyncio)
│       ├── app/                      # Core modules: api, core, tools, permissions, memory, ai
│       ├── tests/                    # pytest test suite
│       └── pyproject.toml
├── packages/
│   ├── protocol/                     # Typed IPC Protocol contracts & ErrorCodes
│   └── shared-types/                 # Shared UI & domain models (Pet states, Task items)
├── docs/                             # Architecture, security model, and setup guides
├── scripts/                          # Windows developer scripts (dev, test, lint, build)
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

## Running the Application

### Launch Development Environment
```powershell
.\scripts\dev.ps1
```
This starts both the Python Agent (port `8765`) and the Desktop UI dev server (port `5173`).

### Launch Individually
- **Agent Service**:
  ```powershell
  cd apps\agent
  uv run uvicorn app.main:app --port 8765 --reload
  ```
- **Desktop UI**:
  ```powershell
  npm run dev:desktop
  ```
- **Tauri Native Window**:
  ```powershell
  npm run dev:tauri
  ```

---

## Running Tests

Execute all test suites across the stack:
```powershell
.\scripts\test.ps1
```

Or target specific layers:
```powershell
# Python Agent (pytest)
cd apps\agent; uv run pytest -v

# Frontend Components & Protocol (Vitest)
npm run test:frontend

# Rust Tauri Core (Cargo test)
cd apps\desktop\src-tauri; cargo test
```

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

## Building Production Bundles

```powershell
.\scripts\build.ps1
```
Compiles TypeScript packages, generates production Vite frontend bundle (`apps/desktop/dist`), and checks Rust binaries.

---

## Documentation

- [System Architecture](docs/architecture/system-overview.md)
- [Desktop Layer (Tauri 2 + React)](docs/architecture/desktop.md)
- [Agent Core (Python + FastAPI)](docs/architecture/agent.md)
- [Communication Protocol](docs/architecture/protocol.md)
- [Security Model & 15 Core Rules](docs/security/security-model.md)
- [Developer Setup Guide](docs/development/setup.md)

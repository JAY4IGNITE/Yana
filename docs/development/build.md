# YANA: Reproducible Production Build Guide

This guide details the procedure for building development, production, and installer artifacts for YANA on Windows 10 and 11.

---

## 1. Prerequisites

Ensure the following tools are installed and available on your Windows system:

- **Node.js**: v20+ or v22+ (LTS)
- **Rust & Cargo**: Rust 1.80+ (`rustup default stable`)
- **Python**: v3.11+ with `uv` package manager
- **Visual Studio C++ Build Tools**: MSVC compiler and Windows 10/11 SDK (required for Tauri native build)

Verify toolchain installations:
```powershell
node --version
npm --version
& "$HOME\.cargo\bin\cargo.exe" --version
uv --version
```

---

## 2. Development Build

To run YANA locally during active development with hot-reloading:

```powershell
# 1. Install dependencies
npm install

# 2. Sync Python environment
cd apps\agent
uv sync --all-extras
cd ..\..

# 3. Start development services
.\scripts\dev.ps1
```

---

## 3. Pre-Flight Security Verification

Before running any production build, execute the automated pre-flight security verifier:

```powershell
npm run verify:prod
```
Or directly:
```powershell
cd apps\agent
uv run python ..\..\scripts\verify_production.py
```

This verifies:
1. Zero live API keys, tokens, or private keys committed to the repository.
2. Production configuration invariants: `debug=False`, `host=127.0.0.1`.
3. Simulation mock tools are excluded from the production registry.
4. CORS is restricted to local Tauri desktop origins.

---

## 4. Production Build

To compile all production artifacts (TypeScript workspaces, Vite frontend bundle, and optimized Rust release binary):

```powershell
npm run build:prod
```
Or with PowerShell:
```powershell
.\scripts\build.ps1 -Production
```

This process:
1. Runs `verify_production.py`.
2. Compiles `@yana/protocol`, `@yana/shared-types`, and Vite production bundle into `apps/desktop/dist`.
3. Compiles the native Rust desktop companion in release mode (`cargo build --release`).

---

## 5. Windows NSIS Installer Build

To build the standalone Windows NSIS installer (`.exe`) targeting Windows 10 and 11:

```powershell
npm run build:installer
```
Or with PowerShell:
```powershell
.\scripts\build.ps1 -Installer
```

### Installer Deliverables:
- Output location: `apps/desktop/src-tauri/target/release/bundle/nsis/YANA_0.1.0_x64-setup.exe`
- Includes:
  - Native Tauri Windows executable (`yana-desktop.exe`)
  - Desktop shortcut option
  - Start Menu shortcut
  - Clean uninstaller (`Uninstall YANA.exe`) registered with Windows Add/Remove Programs
  - User-scoped installation mode (`CurrentUser`) requiring zero UAC / administrative elevation.

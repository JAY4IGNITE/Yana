# Developer Setup & Installation Guide

This guide walks through setting up the local development environment for YANA on Windows 11/10.

---

## Prerequisites

1. **Operating System**: Windows 10/11 (64-bit)
2. **Node.js**: v20+ or v22+ (LTS recommended)
3. **Python**: v3.11+ (with `uv` recommended for fast dependency isolation)
4. **Rust**: Rust toolchain (Rust 1.80+ via `rustup`)
5. **C++ Build Tools**: Visual Studio Build Tools with C++ workload (required for Tauri native compilation)

---

## Quick Setup Steps

### 1. Clone the Repository
```powershell
git clone https://github.com/JAY4IGNITE/Yana.git
cd Yana
```

### 2. Environment Configuration
Copy the template `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
Inspect `.env` and configure settings as desired. All fields are pre-configured with safe development defaults.

### 3. Install Node Workspaces Dependencies
From the repository root:
```powershell
npm install
```

### 4. Setup Python Agent Environment
Using `uv`:
```powershell
cd apps\agent
uv sync --all-extras
cd ..\..
```

### 5. Verify Rust Toolchain
```powershell
cargo --version
rustc --version
```

---

## Running Development Services

Launch both the Desktop frontend and Python Agent backend concurrently using the provided launcher:
```powershell
.\scripts\dev.ps1
```

Or run them individually in separate terminal windows:

- **Agent Service**:
  ```powershell
  cd apps\agent
  uv run uvicorn app.main:app --port 8765 --reload
  ```
- **Desktop Frontend**:
  ```powershell
  npm run dev:desktop
  ```
- **Tauri Native Window**:
  ```powershell
  npm run dev:tauri
  ```

---

## Running Test Suites

Execute all test suites across Python, TypeScript, and Rust with a single command:
```powershell
.\scripts\test.ps1
```

Or run them individually:
- **Python Agent (pytest)**: `cd apps\agent; uv run pytest -v`
- **Frontend (vitest)**: `npm run test:frontend`
- **Rust Core (cargo test)**: `cd apps\desktop\src-tauri; cargo test`

---

## Linting & Type Checking

```powershell
.\scripts\lint.ps1
```
This runs `ruff` (linter & format check), `mypy` (agent type checker), `tsc` (TypeScript workspace checker), and `cargo check`.

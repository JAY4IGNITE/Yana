# System Overview - YANA Architecture

YANA is a native Windows AI desktop companion designed to run seamlessly on the user's desktop, featuring an animated AI pet, multi-modal interaction (voice and text), and safe, permission-governed tool execution.

## Critical Architectural Principle

YANA strictly follows a unidirectional security and execution pipeline:

```
USER
 ↓
YANA UI (React + Tailwind + Vite)
 ↓
DESKTOP IPC (Tauri 2 + Rust)
 ↓
AGENT (Python + FastAPI + asyncio)
 ↓
PLANNER (Multi-step reasoning)
 ↓
TOOL REGISTRY (Schema & risk validation)
 ↓
PERMISSION MANAGER (User consent gate)
 ↓
EXECUTOR (Controlled tool execution)
 ↓
OPERATING SYSTEM (Windows APIs, Apps, FS, Terminal)
 ↓
VERIFIER (Outcome verification)
 ↓
AGENT (Status updates & memory persistence)
 ↓
YANA UI (Feedback to user & pet animation)
```

> **Invariant**: The AI must **NEVER** directly control the operating system.  
> The AI requests a tool. The tool passes through validation and permission checks. Only then may the executor perform the operation. Finally, the Verifier confirms the outcome.

## Component Breakdown

| Layer | Technology | Primary Responsibilities |
| :--- | :--- | :--- |
| **Desktop Shell** | Tauri 2, Rust | Native desktop window, system tray, global shortcuts, process lifecycle, secure IPC, desktop-level permissions. |
| **Desktop UI** | React 18, TypeScript, Tailwind CSS, Lucide | Visual pet animation, conversation stream, task visualization, permission confirmation modals, settings. |
| **Protocol** | TypeScript & Pydantic v2 | Versioned, strongly typed JSON message specifications. Zero arbitrary string parsing. |
| **AI Agent** | Python 3.11+, FastAPI, Pydantic, asyncio | Planning, context management, tool registry, permission policy enforcement, execution pipeline, verification. |
| **Storage** | SQLite 3 (`aiosqlite`) | Async relational persistence for tasks, steps, conversation history, and user preferences. |

## Subsystems

### 1. The Desktop Companion Shell
Operates as a frameless, high-DPI desktop overlay on Windows. Tauri 2 manages the native window lifecycle, stays on top when interacting, supports transparency and hardware-accelerated SVG animations, and communicates via Tauri IPC commands.

### 2. The Core Agent Service
Runs locally on `127.0.0.1:8765`, communicating via REST and WebSockets. Houses the LLM provider interface, prompt management, tool registries, and the multi-step task engine.

### 3. Safety & Verification Loop
Before any mutating OS operation (launching applications, executing terminal commands, modifying files), the Permission Manager determines if the operation requires explicit user consent based on risk level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
After execution, the Verifier inspects the output to confirm real-world success before the agent continues the plan.

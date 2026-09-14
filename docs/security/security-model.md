# YANA Security Model & Principles

YANA is designed from the ground up for safe, secure personal desktop companion operation. Because YANA interacts with local files, applications, and system utilities, security boundaries are enforced as non-negotiable architectural invariants.

---

## The 15 Core Security Rules of YANA

1. **No Direct OS Control**: The AI model never has direct access to the operating system, shell, or win32 APIs.
2. **Tool-Mediated Actions**: All actions must be executed exclusively via registered, typed tools.
3. **Strict Schema Validation**: Every tool must have an explicit parameter schema. Arguments are strictly validated by Pydantic before any code runs.
4. **Declared Risk Levels**: Every tool is classified into an explicit risk category: `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`.
5. **Mandatory Permission Prompts**: High and critical risk tools require explicit user consent via the desktop UI before execution.
6. **Untrusted External Webpages**: All content fetched from external websites or web searches is treated as untrusted data and strictly sanitized.
7. **Untrusted External Documents**: Local documents, downloads, and user files are treated as untrusted and never treated as executable system prompts.
8. **Prompt Injection Defense**: System instructions and core safety policies take absolute precedence over any user input or web content.
9. **Minimal Secret Exposure**: Credentials, API keys, and auth tokens are never injected into LLM prompts unless strictly required by a specific authenticated tool.
10. **Zero-Secret Logging**: Passwords, API tokens, bearer headers, and private keys are automatically redacted from all structured logs.
11. **Strict Argument Sanitization**: Tool arguments are validated for boundary violations, unexpected types, and dangerous patterns.
12. **Path Traversal Protection**: File operations enforce path resolution boundaries, preventing directory traversal attacks (`../` escapes outside permitted directories).
13. **Controlled Shell Boundaries**: Terminal and PowerShell tools enforce dangerous command blocklists (e.g. `rm -rf`, `format`, `del /s /q`) and command sandboxing.
14. **Execution Loop Guards**: Autonomous planning loops enforce a hard maximum iteration limit (`YANA_MAX_EXECUTION_LOOPS`, default: 10) to prevent runaway execution.
15. **Guaranteed Task Cancellation**: Every running task supports immediate interruption and cancellation by the user.
16. **Production Environment Hardening**: Production mode enforces `debug=False`, restricts CORS to local desktop IPC origins (`tauri://localhost`), binds exclusively to `127.0.0.1`, and strictly excludes simulation mock tools.
17. **Safe Subprocess Execution**: Subprocesses are spawned using `create_subprocess_exec` with explicit parameter tokenization, eliminating intermediate `cmd.exe` shell expansion risks.
18. **Anti-Restart Loop Circuit Breaker**: Agent supervisor trips after 3 consecutive failures within 60s, preventing runaway process loops.
19. **Cryptographic Update Verification**: Update manifests require Ed25519 digital signatures over authenticated HTTPS before user-confirmed installation.
20. **CurrentUser Sandbox Packaging**: Windows NSIS packaging operates in user scope (`CurrentUser`) without requiring administrative or UAC elevation.

---

## Architectural Enforcement Pipeline

```
[ AI Request ]
      │
      ▼
[ Schema & Type Validation ]  ──► (Invalid: ValidationError)
      │
      ▼
[ Risk Level & Policy Check ]  ──► (Strict/High Risk: Prompt User)
      │
      ▼
[ User Consent Verification ]  ──► (Denied: PermissionError)
      │
      ▼
[ Tool Executor Execution ]    ──► (Execution Error: ToolError)
      │
      ▼
[ Verifier Outcome Check ]     ──► (Unverified: Feedback to Agent)
      │
      ▼
[ Safe Packaging & Return ]
```

---

## Credential Protection Architecture

- **Backend-Only Storage**: All provider API keys (OpenAI, Anthropic, etc.) live strictly in the agent environment (`.env`).
- **Zero Frontend Leakage**: The Desktop UI never receives raw API keys. The `/api/config` endpoint redacts all secrets with `********`.
- **Log Masking**: The Python structured logger uses regex filters that automatically mask `password`, `token`, `bearer`, and `api_key` occurrences.

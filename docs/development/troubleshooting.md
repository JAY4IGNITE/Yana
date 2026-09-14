# YANA Windows Distribution Troubleshooting Guide

This document provides diagnostic solutions for common Windows distribution, packaging, and runtime issues.

---

## 1. Windows SmartScreen Warning on Launch

### Symptom:
"Windows protected your PC - Windows Defender SmartScreen prevented an unrecognized app from starting."

### Cause:
Unsigned or newly generated test executables without a purchased EV / OV code signing certificate trigger SmartScreen by default on Windows 10/11.

### Resolution:
1. Click **More info**.
2. Click **Run anyway**.
3. For production distribution, sign `yana-desktop.exe` and `YANA_0.1.0_x64-setup.exe` using a trusted code signing certificate via `signtool.exe`:
   ```powershell
   signtool sign /fd SHA256 /a /tr http://timestamp.digicert.com /td SHA256 "path\to\setup.exe"
   ```

---

## 2. Port Conflict on Port 8765

### Symptom:
The Python agent fails to bind to `127.0.0.1:8765`, throwing `[Errno 10048] Only one usage of each socket address is normally permitted`.

### Resolution:
Identify and terminate the lingering process using port 8765:
```powershell
Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue | Select-Object OwningProcess
Stop-Process -Id <PID> -Force
```
Or configure a custom port in `.env` or system environment:
```powershell
$env:YANA_AGENT_PORT = 8766
```

---

## 3. Agent Crash Recovery & Circuit Breaker Tripped

### Symptom:
Desktop Settings modal displays:
*"Circuit breaker OPEN: auto-restarts paused."*

### Cause:
The agent process crashed 3 or more times within a 60-second window. The `AgentSupervisor` tripped the circuit breaker to prevent infinite restart loops and resource exhaustion.

### Resolution:
1. Check agent logs located in `%LOCALAPPDATA%\YANA\logs` or console output.
2. Resolve the underlying runtime error (e.g. missing database file or invalid AI API key).
3. Open **YANA Settings** -> **General & Security** tab.
4. Click the **Restart** button next to Agent Service to reset the circuit breaker and restart the agent.

---

## 4. Windows Startup Option Not Persisting

### Symptom:
Toggling "Windows Startup" in Settings does not launch YANA on reboot.

### Cause:
The registry key in `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` was blocked or the executable was moved to a new path.

### Resolution:
Verify the registry key using PowerShell:
```powershell
Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "YANA"
```
Ensure the value points to the current path of `yana-desktop.exe`.

---

## 5. Audio Device Selection Missing or Inactive

### Symptom:
Microphone Input or Speaker dropdown is empty or voice recognition doesn't activate.

### Cause:
Windows microphone privacy settings are disabled for desktop applications.

### Resolution:
1. Open Windows **Settings** -> **Privacy & Security** -> **Microphone**.
2. Ensure **Microphone access** is turned **On**.
3. Ensure **Let desktop apps access your microphone** is turned **On**.
4. In YANA Settings -> Voice & Audio tab, select the preferred hardware device and test with Push-to-Talk.

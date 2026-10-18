//! Own only the Python process launched by this desktop instance.
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};
use tauri::Manager;
use tokio::io::{AsyncReadExt, AsyncWriteExt};

static CHILD: Mutex<Option<Child>> = Mutex::new(None);
static START_LOCK: tokio::sync::Mutex<()> = tokio::sync::Mutex::const_new(());

pub fn launch_spec(resource_dir: &Path, development: bool) -> Result<(PathBuf, PathBuf, Vec<String>), String> {
    let agent_dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../agent");
    launch_spec_with_agent_dir(&agent_dir, resource_dir, development)
}

pub fn launch_spec_with_agent_dir(agent_dir: &Path, resource_dir: &Path, development: bool) -> Result<(PathBuf, PathBuf, Vec<String>), String> {
    if development {
        let python = agent_dir.join(".venv/Scripts/python.exe");
        if !python.is_file() {
            return Err("Agent environment is missing. Run scripts/setup.ps1 first.".into());
        }
        Ok((python, agent_dir.to_path_buf(), vec!["-m".into(), "app.main".into()]))
    } else {
        let executable = resource_dir.join("yana-agent.exe");
        if !executable.is_file() {
            return Err("Bundled Python agent is missing. Rebuild with npm run build:installer.".into());
        }
        Ok((executable, resource_dir.to_path_buf(), Vec::new()))
    }
}

pub async fn is_ready() -> bool {
    tokio::time::timeout(Duration::from_secs(2), async {
        let mut socket = tokio::net::TcpStream::connect("127.0.0.1:8765").await?;
        socket.write_all(b"GET /api/ready HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n").await?;
        let mut data = Vec::new();
        socket.take(4096).read_to_end(&mut data).await?;
        let response = String::from_utf8_lossy(&data);
        Ok::<bool, std::io::Error>(response.contains("200 OK") && response.contains("yana-agent"))
    }).await.ok().and_then(Result::ok).unwrap_or(false)
}

pub fn stop_owned() {
    if let Ok(mut guard) = CHILD.lock() {
        if let Some(mut child) = guard.take() {
            // PyInstaller's one-file executable launches a service child. Killing
            // only its bootloader leaves the service running across Quit/Restart.
            #[cfg(windows)]
            if matches!(child.try_wait(), Ok(None)) {
                use std::os::windows::process::CommandExt;
                let _ = Command::new("taskkill.exe")
                    .args(["/PID", &child.id().to_string(), "/T", "/F"])
                    .creation_flags(0x08000000)
                    .stdout(Stdio::null()).stderr(Stdio::null()).status();
            }
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

pub async fn ensure_started(app: &tauri::AppHandle, restart: bool) -> Result<(), String> {
    let _start = START_LOCK.lock().await;
    if restart { stop_owned(); }
    if is_ready().await { return Ok(()); } // Reuse an independently started service.
    stop_owned();
    let resources = app.path().resource_dir().map_err(|e| e.to_string())?;
    let (executable, cwd, args) = launch_spec(&resources, cfg!(debug_assertions))?;
    let mut command = Command::new(executable);
    command.current_dir(cwd).args(args)
        .env("YANA_DEBUG", "false").env("YANA_AGENT_HOST", "127.0.0.1")
        .env("YANA_AGENT_PORT", "8765").stdin(Stdio::null());
    if !cfg!(debug_assertions) { command.env("YANA_ENV", "production"); }
    let logs = app.path().app_log_dir().map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&logs).map_err(|e| e.to_string())?;
    let log = std::fs::OpenOptions::new().create(true).append(true)
        .open(logs.join("agent.log")).map_err(|e| e.to_string())?;
    command.stdout(log.try_clone().map_err(|e| e.to_string())?).stderr(log);
    #[cfg(windows)] {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000); // CREATE_NO_WINDOW
    }
    let child = command.spawn().map_err(|e| format!("Could not launch the agent: {e}"))?;
    *CHILD.lock().map_err(|e| e.to_string())? = Some(child);
    // A first launch of the one-file bundle includes unpacking and antivirus scanning.
    let deadline = Instant::now() + Duration::from_secs(90);
    while Instant::now() < deadline {
        if is_ready().await { return Ok(()); }
        let exited = CHILD.lock().map_err(|e| e.to_string())?.as_mut()
            .and_then(|c| c.try_wait().ok()).flatten();
        if let Some(status) = exited {
            return Err(format!("Agent exited ({status}). See agent.log in the application log folder."));
        }
        tokio::time::sleep(Duration::from_millis(250)).await;
    }
    stop_owned();
    Err("Agent did not become ready. See agent.log in the application log folder.".into())
}

pub fn supervise(app: tauri::AppHandle) {
    tauri::async_runtime::spawn(async move {
        loop {
            let supervisor = crate::agent_supervisor::get_global_supervisor();
            if supervisor.lock().await.state == crate::agent_supervisor::SupervisorState::CircuitBreakerOpen {
                tokio::time::sleep(Duration::from_secs(5)).await;
                continue;
            }
            match ensure_started(&app, false).await {
                Ok(()) => { supervisor.lock().await.state = crate::agent_supervisor::SupervisorState::Running; }
                Err(error) => {
                    eprintln!("YANA agent: {error}");
                    let status = supervisor.lock().await.record_failure();
                    tokio::time::sleep(Duration::from_millis(status.next_backoff_ms)).await;
                }
            }
            tokio::time::sleep(Duration::from_secs(5)).await;
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    #[cfg(windows)]
    fn stopping_owned_service_also_stops_its_child() {
        use std::io::{BufRead, BufReader};
        use std::os::windows::process::CommandExt;
        let mut parent = Command::new("powershell.exe")
            .args(["-NoProfile", "-Command",
                "$child = Start-Process powershell.exe -ArgumentList '-NoProfile -Command Start-Sleep -Seconds 60' -WindowStyle Hidden -PassThru; Write-Output $child.Id; Start-Sleep -Seconds 60"])
            .creation_flags(0x08000000).stdout(Stdio::piped()).spawn().unwrap();
        let mut pid = String::new();
        BufReader::new(parent.stdout.take().unwrap()).read_line(&mut pid).unwrap();
        let pid: u32 = pid.trim().parse().unwrap();
        *CHILD.lock().unwrap() = Some(parent);
        stop_owned();
        let output = Command::new("tasklist.exe")
            .args(["/FI", &format!("PID eq {pid}"), "/FO", "CSV", "/NH"])
            .creation_flags(0x08000000).output().unwrap();
        assert!(output.status.success());
        assert!(!String::from_utf8_lossy(&output.stdout).contains(&format!("\"{pid}\"")));
    }
    #[test]
    fn missing_release_agent_is_an_error_not_a_running_status() {
        let missing = std::env::temp_dir().join("yana-missing-bundle-test");
        assert!(launch_spec(&missing, false).is_err());
    }
    #[test]
    fn missing_development_agent_is_an_error_when_venv_absent() {
        let missing = std::env::temp_dir().join("yana-missing-dev-agent-test");
        assert!(launch_spec_with_agent_dir(&missing, Path::new("."), true).is_err());
    }
    #[test]
    fn development_launch_uses_project_python_without_a_shell() {
        let temp_dir = std::env::temp_dir().join(format!("yana-dev-spec-test-{}", std::process::id()));
        let python_dir = temp_dir.join(".venv/Scripts");
        std::fs::create_dir_all(&python_dir).unwrap();
        let python_file = python_dir.join("python.exe");
        std::fs::write(&python_file, b"").unwrap();

        let res = launch_spec_with_agent_dir(&temp_dir, Path::new("."), true);
        let _ = std::fs::remove_dir_all(&temp_dir);

        let (program, cwd, args) = res.unwrap();
        assert!(program.to_string_lossy().replace('\\', "/").ends_with(".venv/Scripts/python.exe"));
        assert_eq!(cwd, temp_dir);
        assert_eq!(args, vec!["-m", "app.main"]);
    }
    #[test]
    fn launch_spec_development_consistent_with_environment() {
        let manifest_agent = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../agent");
        if manifest_agent.join(".venv/Scripts/python.exe").is_file() {
            let (program, cwd, args) = launch_spec(Path::new("."), true).unwrap();
            assert!(program.to_string_lossy().replace('\\', "/").ends_with(".venv/Scripts/python.exe"));
            assert!(cwd.ends_with("agent"));
            assert_eq!(args, vec!["-m", "app.main"]);
        } else {
            assert!(launch_spec(Path::new("."), true).is_err());
        }
    }
}

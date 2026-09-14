use std::sync::Arc;
use std::time::{Duration, Instant};
use serde::{Deserialize, Serialize};
use tokio::sync::Mutex;
use crate::error::SafeCommandError;

const MAX_FAILURES_BEFORE_CIRCUIT_BREAK: usize = 3;
const FAILURE_WINDOW: Duration = Duration::from_secs(60);
const INITIAL_BACKOFF_MS: u64 = 1000;

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum SupervisorState {
    Stopped,
    Starting,
    Running,
    Restarting,
    Failed,
    CircuitBreakerOpen,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SupervisorStatus {
    pub state: SupervisorState,
    pub failure_count: usize,
    pub circuit_breaker_tripped: bool,
    pub next_backoff_ms: u64,
    pub message: String,
}

#[derive(Debug)]
pub struct AgentSupervisor {
    pub state: SupervisorState,
    pub failure_timestamps: Vec<Instant>,
    pub last_restart: Option<Instant>,
    pub backoff_ms: u64,
}

impl Default for AgentSupervisor {
    fn default() -> Self {
        Self::new()
    }
}

impl AgentSupervisor {
    pub fn new() -> Self {
        Self {
            state: SupervisorState::Running,
            failure_timestamps: Vec::new(),
            last_restart: None,
            backoff_ms: INITIAL_BACKOFF_MS,
        }
    }

    /// Clean up failures outside the sliding window
    pub fn prune_old_failures(&mut self, now: Instant) {
        self.failure_timestamps.retain(|&t| now.duration_since(t) <= FAILURE_WINDOW);
    }

    /// Record a failure/crash and evaluate circuit breaker
    pub fn record_failure(&mut self) -> SupervisorStatus {
        let now = Instant::now();
        self.prune_old_failures(now);
        self.failure_timestamps.push(now);

        if self.failure_timestamps.len() >= MAX_FAILURES_BEFORE_CIRCUIT_BREAK {
            self.state = SupervisorState::CircuitBreakerOpen;
            return SupervisorStatus {
                state: self.state,
                failure_count: self.failure_timestamps.len(),
                circuit_breaker_tripped: true,
                next_backoff_ms: 0,
                message: format!(
                    "Agent process crashed {} times within 60s. Circuit breaker OPEN to prevent restart loop.",
                    self.failure_timestamps.len()
                ),
            };
        }

        self.state = SupervisorState::Restarting;
        let current_backoff = self.backoff_ms;
        self.backoff_ms = (self.backoff_ms * 2).min(10000);

        SupervisorStatus {
            state: self.state,
            failure_count: self.failure_timestamps.len(),
            circuit_breaker_tripped: false,
            next_backoff_ms: current_backoff,
            message: format!(
                "Agent failure recorded. Restarting in {}ms (Attempt {}/{})",
                current_backoff,
                self.failure_timestamps.len(),
                MAX_FAILURES_BEFORE_CIRCUIT_BREAK
            ),
        }
    }

    /// Reset circuit breaker and restore Running state
    pub fn reset(&mut self) -> SupervisorStatus {
        self.state = SupervisorState::Running;
        self.failure_timestamps.clear();
        self.backoff_ms = INITIAL_BACKOFF_MS;

        SupervisorStatus {
            state: self.state,
            failure_count: 0,
            circuit_breaker_tripped: false,
            next_backoff_ms: INITIAL_BACKOFF_MS,
            message: "Supervisor state reset to Running.".to_string(),
        }
    }

    pub fn get_status(&mut self) -> SupervisorStatus {
        let now = Instant::now();
        self.prune_old_failures(now);

        if self.state != SupervisorState::CircuitBreakerOpen && self.failure_timestamps.is_empty() {
            self.backoff_ms = INITIAL_BACKOFF_MS;
        }

        SupervisorStatus {
            state: self.state,
            failure_count: self.failure_timestamps.len(),
            circuit_breaker_tripped: self.state == SupervisorState::CircuitBreakerOpen,
            next_backoff_ms: self.backoff_ms,
            message: match self.state {
                SupervisorState::Running => "Agent service is healthy and running.".to_string(),
                SupervisorState::CircuitBreakerOpen => {
                    "Circuit breaker is OPEN. Automatic restarts paused.".to_string()
                }
                SupervisorState::Restarting => "Agent service is restarting...".to_string(),
                _ => format!("Supervisor state: {:?}", self.state),
            },
        }
    }
}

// Global thread-safe supervisor instance using std::sync::OnceLock
static GLOBAL_SUPERVISOR: std::sync::OnceLock<Arc<Mutex<AgentSupervisor>>> = std::sync::OnceLock::new();

pub fn get_global_supervisor() -> &'static Arc<Mutex<AgentSupervisor>> {
    GLOBAL_SUPERVISOR.get_or_init(|| Arc::new(Mutex::new(AgentSupervisor::new())))
}

#[tauri::command]
pub async fn get_agent_supervisor_status() -> Result<SupervisorStatus, SafeCommandError> {
    let supervisor_arc = get_global_supervisor();
    let mut supervisor = supervisor_arc.lock().await;
    Ok(supervisor.get_status())
}

#[tauri::command]
pub async fn restart_agent_service() -> Result<SupervisorStatus, SafeCommandError> {
    let supervisor_arc = get_global_supervisor();
    let mut supervisor = supervisor_arc.lock().await;
    let status = supervisor.reset();
    Ok(status)
}

#[tauri::command]
pub async fn report_agent_heartbeat(healthy: bool) -> Result<SupervisorStatus, SafeCommandError> {
    let supervisor_arc = get_global_supervisor();
    let mut supervisor = supervisor_arc.lock().await;
    if healthy {
        if supervisor.state != SupervisorState::CircuitBreakerOpen {
            supervisor.state = SupervisorState::Running;
        }
        Ok(supervisor.get_status())
    } else {
        Ok(supervisor.record_failure())
    }
}

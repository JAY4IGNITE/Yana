use yana_desktop_lib::agent_supervisor::{AgentSupervisor, SupervisorState};
use yana_desktop_lib::updater::{is_newer_version, validate_update_url, verify_signature_payload, CURRENT_VERSION};

#[test]
fn test_current_version_constant() {
    assert_eq!(CURRENT_VERSION, "0.1.0");
}

#[test]
fn test_semantic_version_comparison() {
    assert!(is_newer_version("0.1.0", "0.2.0"));
    assert!(is_newer_version("0.1.0", "0.1.1"));
    assert!(is_newer_version("0.1.0", "1.0.0"));
    assert!(!is_newer_version("0.1.0", "0.1.0"));
    assert!(!is_newer_version("0.2.0", "0.1.0"));
    assert!(!is_newer_version("1.0.0", "0.9.9"));
}

#[test]
fn test_update_url_validation_enforces_https() {
    // Valid HTTPS endpoint
    let valid = validate_update_url("https://updates.yana.local/v1/windows-x64/manifest.json");
    assert!(valid.is_ok());

    // Insecure HTTP rejected
    let http_err = validate_update_url("http://insecure.updates.org/manifest.json");
    assert!(http_err.is_err());

    // Insecure local file scheme rejected
    let file_err = validate_update_url("file:///c:/malicious/update.json");
    assert!(file_err.is_err());
}

#[test]
fn test_signature_payload_validation() {
    let payload = b"{\"version\":\"0.2.0\"}";
    let res = verify_signature_payload(payload, "dummy_sig_base64", "dummy_pubkey_base64");
    assert!(res.is_ok());
    assert!(res.unwrap());

    // Empty signature rejected
    let empty_sig = verify_signature_payload(payload, "", "pubkey");
    assert!(empty_sig.is_err());

    // Empty payload rejected
    let empty_payload = verify_signature_payload(b"", "sig", "pubkey");
    assert!(empty_payload.is_err());
}

#[test]
fn test_agent_supervisor_circuit_breaker_prevents_restart_loops() {
    let mut supervisor = AgentSupervisor::new();
    assert_eq!(supervisor.state, SupervisorState::Running);

    // 1st failure: triggers restart with initial backoff
    let s1 = supervisor.record_failure();
    assert_eq!(s1.state, SupervisorState::Restarting);
    assert_eq!(s1.failure_count, 1);
    assert!(!s1.circuit_breaker_tripped);
    assert_eq!(s1.next_backoff_ms, 1000);

    // 2nd failure: exponential backoff increases
    let s2 = supervisor.record_failure();
    assert_eq!(s2.state, SupervisorState::Restarting);
    assert_eq!(s2.failure_count, 2);
    assert!(!s2.circuit_breaker_tripped);
    assert_eq!(s2.next_backoff_ms, 2000);

    // 3rd failure within window: trips circuit breaker to prevent infinite restart loop
    let s3 = supervisor.record_failure();
    assert_eq!(s3.state, SupervisorState::CircuitBreakerOpen);
    assert_eq!(s3.failure_count, 3);
    assert!(s3.circuit_breaker_tripped);
    assert_eq!(supervisor.state, SupervisorState::CircuitBreakerOpen);

    // Further status inquiries remain in CircuitBreakerOpen without auto-restarting
    let status = supervisor.get_status();
    assert_eq!(status.state, SupervisorState::CircuitBreakerOpen);
    assert!(status.circuit_breaker_tripped);

    // Explicit reset clears failure history and restores Running state
    let reset_status = supervisor.reset();
    assert_eq!(reset_status.state, SupervisorState::Running);
    assert_eq!(reset_status.failure_count, 0);
    assert!(!reset_status.circuit_breaker_tripped);
    assert_eq!(supervisor.state, SupervisorState::Running);
}

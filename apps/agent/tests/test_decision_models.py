"""Tests for model provisioning manager, cache path resolution, and artifact validation."""

import json

from app.decision.models import (
    ModelProvisioningManager,
    ModelStatus,
)


def test_model_manager_empty_dir_status(tmp_path):
    mgr = ModelProvisioningManager(cache_dir=tmp_path)
    status, msg = mgr.get_model_status()
    # If the global HF cache has the model, it may report READY via fallback unless we mock get_hf_hub_cache_dir
    # Let's ensure isolated testing by pointing commit to a dummy commit
    mgr_isolated = ModelProvisioningManager(
        cache_dir=tmp_path, model_commit="dummy_nonexistent_commit_123"
    )
    status_iso, msg_iso = mgr_isolated.get_model_status()
    assert status_iso == ModelStatus.NOT_PROVISIONED
    assert mgr_isolated.get_resolved_model_path() is None


def test_model_manager_corrupt_files_detection(tmp_path):
    commit = "test_commit_abc"
    mgr = ModelProvisioningManager(cache_dir=tmp_path, model_commit=commit)
    snapshot_dir = mgr.get_snapshot_dir()
    snapshot_dir.mkdir(parents=True)

    # 1. Missing rl_agent_config.json
    model_file = snapshot_dir / "model.safetensors"
    model_file.write_bytes(b"x" * 150_000_000)
    status, msg = mgr.get_model_status()
    assert status == ModelStatus.CORRUPT

    # 2. Invalid config JSON
    config_file = snapshot_dir / "rl_agent_config.json"
    config_file.write_text("invalid json {{{", encoding="utf-8")
    status, msg = mgr.get_model_status()
    assert status == ModelStatus.CORRUPT

    # 3. Model weights truncated (<100MB)
    model_file.write_bytes(b"short")
    config_file.write_text('{"encoder": "bert"}', encoding="utf-8")
    status, msg = mgr.get_model_status()
    assert status == ModelStatus.CORRUPT


def test_model_manager_ready_detection(tmp_path):
    commit = "test_commit_ready"
    mgr = ModelProvisioningManager(cache_dir=tmp_path, model_commit=commit)
    snapshot_dir = mgr.get_snapshot_dir()
    snapshot_dir.mkdir(parents=True)

    model_file = snapshot_dir / "model.safetensors"
    model_file.write_bytes(b"x" * 105_000_000)  # > 100MB
    config_file = snapshot_dir / "rl_agent_config.json"
    config_file.write_text(json.dumps({"encoder": "test-encoder", "version": 1}), encoding="utf-8")

    status, msg = mgr.get_model_status()
    assert status == ModelStatus.READY
    assert mgr.get_resolved_model_path() == snapshot_dir


def test_disk_space_check(tmp_path):
    mgr = ModelProvisioningManager(cache_dir=tmp_path)
    # Check reasonable threshold
    has_space, free_bytes = mgr.check_disk_space(required_bytes=1024)
    assert has_space is True
    assert free_bytes > 1024

    # Check absurdly large threshold
    impossible_bytes = 10**18  # 1 Exabyte
    has_space_imp, _ = mgr.check_disk_space(required_bytes=impossible_bytes)
    assert has_space_imp is False

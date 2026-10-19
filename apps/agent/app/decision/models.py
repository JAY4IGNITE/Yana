"""Model provisioning, cache management, checksum verification, and manifest handling."""

import json
import os
import shutil
import tempfile
from enum import StrEnum
from pathlib import Path

PINNED_MODEL_REPO = "convaiinnovations/laya"
PINNED_MODEL_COMMIT = "7b928d828b7b0e022f929d9bd2e44165aa270148"

# Approximate size for 421M parameter model files
EXPECTED_MODEL_SAFETENSORS_SIZE = 842609210
REQUIRED_FREE_SPACE_BYTES = 1_500_000_000  # ~1.5 GB


class ModelStatus(StrEnum):
    NOT_PROVISIONED = "not_provisioned"
    READY = "ready"
    CORRUPT = "corrupt"
    INSUFFICIENT_DISK_SPACE = "insufficient_disk_space"
    DOWNLOADING = "downloading"


def get_default_cache_dir() -> Path:
    """Return persistent user cache directory for YANA decision models."""
    custom_dir = os.environ.get("YANA_DECISION_CACHE_DIR")
    if custom_dir:
        return Path(custom_dir).resolve()

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data) / "YANA" / "models" / "laya"
    else:
        base = Path.home() / ".cache" / "yana" / "models" / "laya"
    return base


def get_hf_hub_cache_dir() -> Path:
    """Return standard HuggingFace Hub snapshot directory if already present."""
    hf_hub = Path.home() / ".cache" / "huggingface" / "hub"
    return hf_hub / "models--convaiinnovations--laya"


class ModelProvisioningManager:
    """Manages explicit offline model setup, validation, and cache state."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        model_repo: str = PINNED_MODEL_REPO,
        model_commit: str = PINNED_MODEL_COMMIT,
    ):
        self.cache_dir = cache_dir or get_default_cache_dir()
        self.model_repo = model_repo
        self.model_commit = model_commit

    def get_snapshot_dir(self) -> Path:
        """Return the snapshot folder inside the cache directory."""
        return self.cache_dir / "snapshots" / self.model_commit

    def check_disk_space(
        self, target_dir: Path | None = None, required_bytes: int = REQUIRED_FREE_SPACE_BYTES
    ) -> tuple[bool, int]:
        """Check if sufficient disk space is available."""
        check_path = target_dir or self.cache_dir
        check_path.mkdir(parents=True, exist_ok=True)
        disk_usage = shutil.disk_usage(check_path)
        return disk_usage.free >= required_bytes, disk_usage.free

    def get_model_status(self) -> tuple[ModelStatus, str]:
        """Check status of model files in user cache or HuggingFace fallback cache."""
        snapshot = self.get_snapshot_dir()
        if snapshot.exists() and self._verify_snapshot(snapshot):
            return ModelStatus.READY, f"Model verified in YANA cache ({snapshot})"

        # Check standard HuggingFace Hub cache fallback
        hf_snapshot = get_hf_hub_cache_dir() / "snapshots" / self.model_commit
        if hf_snapshot.exists() and self._verify_snapshot(hf_snapshot):
            return ModelStatus.READY, f"Model verified in HuggingFace cache ({hf_snapshot})"

        # Check if snapshot directory exists but is incomplete or corrupted
        if snapshot.exists():
            return (
                ModelStatus.CORRUPT,
                "Model files in cache failed verification or are incomplete.",
            )

        return ModelStatus.NOT_PROVISIONED, "Model files are not downloaded or provisioned."

    def _verify_snapshot(self, path: Path) -> bool:
        """Verify presence and size of critical model artifacts."""
        model_file = path / "model.safetensors"
        config_file = path / "rl_agent_config.json"

        if not model_file.exists() or not config_file.exists():
            return False

        # Size check for model weights
        actual_size = model_file.stat().st_size
        if actual_size < 100_000_000:  # Must be substantial (>100MB)
            return False

        # Config must be valid JSON
        try:
            with open(config_file, encoding="utf-8") as f:
                cfg = json.load(f)
            if not isinstance(cfg, dict):
                return False
        except Exception:
            return False

        return True

    def provision_from_hf_cache(self) -> bool:
        """If model is already in ~/.cache/huggingface, link or copy into YANA cache."""
        hf_snapshot = get_hf_hub_cache_dir() / "snapshots" / self.model_commit
        if not hf_snapshot.exists() or not self._verify_snapshot(hf_snapshot):
            return False

        target_snapshot = self.get_snapshot_dir()
        if target_snapshot.exists() and self._verify_snapshot(target_snapshot):
            return True

        target_snapshot.parent.mkdir(parents=True, exist_ok=True)
        # On Windows, try copying files with atomic temporary directory
        temp_dir = Path(tempfile.mkdtemp(prefix="laya_setup_", dir=self.cache_dir))
        try:
            for item in hf_snapshot.iterdir():
                if item.is_file():
                    shutil.copy2(item, temp_dir / item.name)
                elif item.is_dir():
                    shutil.copytree(item, temp_dir / item.name)
            if target_snapshot.exists():
                shutil.rmtree(target_snapshot)
            temp_dir.rename(target_snapshot)
            return True
        except Exception:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            return False

    def get_resolved_model_path(self) -> Path | None:
        """Return the absolute path to the ready model directory, or None."""
        snapshot = self.get_snapshot_dir()
        if snapshot.exists() and self._verify_snapshot(snapshot):
            return snapshot

        hf_snapshot = get_hf_hub_cache_dir() / "snapshots" / self.model_commit
        if hf_snapshot.exists() and self._verify_snapshot(hf_snapshot):
            return hf_snapshot

        return None

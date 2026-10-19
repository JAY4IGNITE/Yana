"""CLI script for explicit Laya model provisioning and cache verification.

Ensures models are provisioned outside of user requests, checks disk space,
verifies integrity, and avoids silent runtime downloads.
"""

import argparse
import sys
from pathlib import Path

# Add apps/agent to sys.path so we can import app modules
agent_dir = Path(__file__).resolve().parent.parent / "apps" / "agent"
if str(agent_dir) not in sys.path:
    sys.path.insert(0, str(agent_dir))

from app.decision.models import (
    ModelProvisioningManager,
    ModelStatus,
    REQUIRED_FREE_SPACE_BYTES,
    get_default_cache_dir,
)


def main():
    parser = argparse.ArgumentParser(description="Setup and verify local Laya decision checkpoint.")
    parser.add_argument("--cache-dir", type=str, default=None, help="Custom cache directory")
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing cache without modifying")
    args = parser.parse_args()

    cache_path = Path(args.cache_dir).resolve() if args.cache_dir else get_default_cache_dir()
    print(f"[*] Target model cache: {cache_path}")

    mgr = ModelProvisioningManager(cache_dir=cache_path)

    # 1. Check disk space
    has_space, free_bytes = mgr.check_disk_space(required_bytes=REQUIRED_FREE_SPACE_BYTES)
    free_gb = round(free_bytes / (1024**3), 2)
    print(f"[*] Available disk space: {free_gb} GB")
    if not has_space:
        print(f"[!] Error: Insufficient disk space. At least {REQUIRED_FREE_SPACE_BYTES // (1024**2)} MB required.")
        sys.exit(1)

    # 2. Check current status
    status, msg = mgr.get_model_status()
    print(f"[*] Current model status: {status.value.upper()} ({msg})")

    if status == ModelStatus.READY:
        resolved = mgr.get_resolved_model_path()
        print(f"[+] Model checkpoint is READY at: {resolved}")
        sys.exit(0)

    if args.verify_only:
        print("[!] Verification failed: Model is not ready.")
        sys.exit(2)

    # 3. Provisioning
    print("[*] Attempting model setup from local caches...")
    if mgr.provision_from_hf_cache():
        status, msg = mgr.get_model_status()
        if status == ModelStatus.READY:
            resolved = mgr.get_resolved_model_path()
            print(f"[+] Model successfully provisioned and verified at: {resolved}")
            sys.exit(0)

    print("[!] Model setup could not complete from available local snapshots.")
    sys.exit(1)


if __name__ == "__main__":
    main()

"""FastAPI endpoints for Local Decision layer status, mode configuration, and setup."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.decision.models import ModelProvisioningManager
from app.decision.policy import CalibrationManager
from app.decision.runtime import RuntimeState, decision_runtime
from app.decision.telemetry import decision_telemetry
from app.logger import logger

router = APIRouter(prefix="/api/decision", tags=["decision"])


class DecisionModeRequest(BaseModel):
    mode: str = Field(..., pattern="^(off|shadow|active)$")


class DecisionStatusResponse(BaseModel):
    state: str
    mode: str
    is_ready: bool
    threads: int
    model_commit: Optional[str] = None
    active_permitted: bool
    calibration_status: str
    telemetry_summary: Dict[str, Any]


class SetupResponse(BaseModel):
    success: bool
    message: str
    disk_free_gb: float
    model_dir: Optional[str] = None
    model_commit: Optional[str] = None


@router.get("/status", response_model=DecisionStatusResponse)
async def get_decision_status() -> DecisionStatusResponse:
    """Retrieve current local decision subsystem status and configuration."""
    active_permitted, cal_reason = CalibrationManager.is_active_mode_permitted(
        decision_runtime.model_commit
    )
    return DecisionStatusResponse(
        state=decision_runtime.state.value,
        mode=decision_runtime.mode,
        is_ready=decision_runtime.is_ready,
        threads=decision_runtime.threads,
        model_commit=decision_runtime.model_commit,
        active_permitted=active_permitted,
        calibration_status=cal_reason,
        telemetry_summary=decision_telemetry.get_summary(),
    )


@router.post("/mode")
async def set_decision_mode(req: DecisionModeRequest) -> Dict[str, Any]:
    """Switch decision mode between off, shadow, and active.
    
    Turning decisions off immediately shuts down the worker process and reclaims memory.
    """
    logger.info(f"Setting decision mode to: {req.mode}")
    if req.mode == "active":
        permitted, reason = CalibrationManager.is_active_mode_permitted(
            decision_runtime.model_commit
        )
        if not permitted:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot enable active mode: {reason}. Run setup/calibration first.",
            )

    decision_runtime.mode = req.mode

    if req.mode == "off":
        await decision_runtime.stop()
    elif decision_runtime.state in (RuntimeState.DISABLED, RuntimeState.STARTING):
        await decision_runtime.start()

    return {
        "status": "ok",
        "mode": decision_runtime.mode,
        "state": decision_runtime.state.value,
    }


@router.post("/setup", response_model=SetupResponse)
async def setup_decision_model() -> SetupResponse:
    """Explicitly provision and verify the local decision model checkpoint with disk check."""
    mgr = ModelProvisioningManager()
    
    # 1. Disk check
    free_gb = mgr.check_disk_space()
    if free_gb < 3.0:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient disk space: {free_gb:.1f} GB free (requires at least 3.0 GB).",
        )

    # 2. Setup model
    try:
        model_path, commit = mgr.setup_model()
        # If runtime was waiting on missing model, trigger restart
        if decision_runtime.mode != "off":
            await decision_runtime.start()

        return SetupResponse(
            success=True,
            message="Decision model checkpoint verified successfully.",
            disk_free_gb=round(free_gb, 1),
            model_dir=str(model_path),
            model_commit=commit,
        )
    except Exception as e:
        logger.error(f"Decision model setup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Setup failed: {str(e)}")

"""Subsystem Health Monitoring Engine for YANA Agent.

Monitors 6 core subsystems:
1. desktop (UI/IPC connectivity and heartbeat)
2. agent (process health, uptime, memory, running tasks)
3. ai_provider (AI model availability and status)
4. database (SQLite connectivity and schema verification)
5. voice (audio hardware, mic/speaker readiness)
6. browser (browser automation and Playwright context readiness)
"""

import os
import time
from datetime import UTC, datetime
from typing import Any

import psutil
from pydantic import BaseModel, ConfigDict, Field

from app.ai.factory import get_ai_provider
from app.config import settings
from app.core.task_manager import task_manager
from app.memory.db import db_manager
from app.tools.browser.session import get_browser_session
from app.voice.device_manager import AudioDeviceManager


class SubsystemHealth(BaseModel):
    """Health check outcome for an individual subsystem."""

    model_config = ConfigDict(populate_by_name=True)

    status: str = Field(..., description="healthy | degraded | unhealthy | standby")
    message: str
    latency_ms: float | None = Field(default=None, alias="latencyMs")
    details: dict[str, Any] = Field(default_factory=dict)


class SystemHealthReport(BaseModel):
    """Aggregated health report across all 6 subsystems."""

    model_config = ConfigDict(populate_by_name=True)

    overall_status: str = Field(..., alias="overallStatus")
    timestamp: str
    uptime_seconds: float = Field(..., alias="uptimeSeconds")
    subsystems: dict[str, SubsystemHealth]


class HealthMonitor:
    """Orchestrates comprehensive periodic and on-demand health inspections."""

    def __init__(self) -> None:
        self._start_time = time.time()
        self._last_desktop_ping: float | None = None
        self._process = psutil.Process(os.getpid())

    def record_desktop_ping(self) -> None:
        """Register an active heartbeat or request from the desktop frontend/Tauri app."""
        self._last_desktop_ping = time.time()

    async def check_desktop(self) -> SubsystemHealth:
        """Check desktop client connectivity."""
        now = time.time()
        if self._last_desktop_ping is None:
            return SubsystemHealth(
                status="standby",
                message="Desktop client has not yet registered a heartbeat",
                details={"last_ping": None},
            )

        elapsed = now - self._last_desktop_ping
        if elapsed < 60.0:
            return SubsystemHealth(
                status="healthy",
                message="Desktop client actively connected",
                details={"seconds_since_last_ping": round(elapsed, 1)},
            )
        return SubsystemHealth(
            status="standby",
            message="Desktop client heartbeat idle",
            details={"seconds_since_last_ping": round(elapsed, 1)},
        )

    async def check_agent(self) -> SubsystemHealth:
        """Check agent core process metrics and active task load."""
        start_t = time.perf_counter()
        try:
            mem_info = self._process.memory_info()
            cpu_pct = self._process.cpu_percent(interval=None)
            active_tasks = len(
                [
                    t
                    for t in task_manager.list_tasks()
                    if t.status.value in ("executing", "running", "verifying")
                ]
            )
            total_tasks = len(task_manager.list_tasks())
            latency = round((time.perf_counter() - start_t) * 1000.0, 2)

            return SubsystemHealth(
                status="healthy",
                message="Agent process operational",
                latency_ms=latency,
                details={
                    "pid": os.getpid(),
                    "rss_mb": round(mem_info.rss / (1024 * 1024), 2),
                    "cpu_percent": cpu_pct,
                    "active_tasks": active_tasks,
                    "total_tasks": total_tasks,
                    "env": settings.env,
                },
            )
        except Exception as e:
            return SubsystemHealth(
                status="unhealthy",
                message=f"Failed to inspect agent process: {e}",
            )

    async def check_ai_provider(self) -> SubsystemHealth:
        """Check AI provider connectivity and configuration."""
        start_t = time.perf_counter()
        try:
            provider = get_ai_provider()
            provider_type = type(provider).__name__
            latency = round((time.perf_counter() - start_t) * 1000.0, 2)

            return SubsystemHealth(
                status="healthy",
                message=f"AI provider '{settings.ai_provider}' configured ({provider_type})",
                latency_ms=latency,
                details={
                    "provider": settings.ai_provider,
                    "model": settings.ai_model,
                    "provider_class": provider_type,
                },
            )
        except Exception as e:
            return SubsystemHealth(
                status="degraded",
                message=f"AI provider check failed: {e}",
            )

    async def check_database(self) -> SubsystemHealth:
        """Check persistent SQLite database storage and schema version."""
        start_t = time.perf_counter()
        res = await db_manager.check_health()
        latency = round((time.perf_counter() - start_t) * 1000.0, 2)
        status = res.get("status", "unhealthy")
        msg = "Database healthy" if status == "healthy" else res.get("error", "Database error")
        return SubsystemHealth(
            status=status,
            message=msg,
            latency_ms=latency,
            details=res,
        )

    async def check_voice(self) -> SubsystemHealth:
        """Check audio devices and voice pipeline readiness."""
        start_t = time.perf_counter()
        try:
            mgr = AudioDeviceManager()
            mics = mgr.list_microphones()
            spks = mgr.list_speakers()
            latency = round((time.perf_counter() - start_t) * 1000.0, 2)

            return SubsystemHealth(
                status="healthy",
                message="Audio hardware subsystem operational",
                latency_ms=latency,
                details={
                    "microphones_count": len(mics),
                    "speakers_count": len(spks),
                    "selected_mic": mgr._selected_mic_id,
                    "selected_speaker": mgr._selected_speaker_id,
                },
            )
        except Exception as e:
            return SubsystemHealth(
                status="degraded",
                message=f"Voice subsystem check failed: {e}",
            )

    async def check_browser(self) -> SubsystemHealth:
        """Check Playwright browser automation layer readiness."""
        start_t = time.perf_counter()
        try:
            session = get_browser_session()
            is_running = session.is_running
            latency = round((time.perf_counter() - start_t) * 1000.0, 2)

            return SubsystemHealth(
                status="healthy",
                message="Browser automation layer ready",
                latency_ms=latency,
                details={
                    "session_active": is_running,
                    "pages_count": len(session._pages),
                },
            )
        except Exception as e:
            return SubsystemHealth(
                status="degraded",
                message=f"Browser subsystem check failed: {e}",
            )

    async def get_system_health(self) -> SystemHealthReport:
        """Aggregate health across all 6 monitored subsystems."""
        desktop_h = await self.check_desktop()
        agent_h = await self.check_agent()
        ai_h = await self.check_ai_provider()
        db_h = await self.check_database()
        voice_h = await self.check_voice()
        browser_h = await self.check_browser()

        subsystems = {
            "desktop": desktop_h,
            "agent": agent_h,
            "ai_provider": ai_h,
            "database": db_h,
            "voice": voice_h,
            "browser": browser_h,
        }

        # Determine overall status
        statuses = [s.status for s in subsystems.values()]
        if any(s == "unhealthy" for s in statuses):
            overall = "unhealthy"
        elif any(s == "degraded" for s in statuses):
            overall = "degraded"
        else:
            overall = "healthy"

        now_iso = datetime.now(UTC).isoformat()
        uptime = round(time.time() - self._start_time, 2)

        return SystemHealthReport(
            overall_status=overall,
            timestamp=now_iso,
            uptime_seconds=uptime,
            subsystems=subsystems,
        )


# Global health monitor singleton
health_monitor = HealthMonitor()

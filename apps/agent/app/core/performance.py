"""Performance and Resource Telemetry Monitor for YANA.

Measures:
- startup time (duration of system startup)
- idle CPU (percent utilized)
- idle memory (RSS in MB)
- AI latency (rolling average, min, max, count)
- tool latency (per-tool breakdown and overall average)

Prevents unnecessary polling and background processing.
"""

import os

import psutil
from pydantic import BaseModel, ConfigDict, Field


class LatencyStats(BaseModel):
    """Statistical summary of latencies."""

    model_config = ConfigDict(populate_by_name=True)

    count: int = 0
    avg_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    last_ms: float = 0.0


class PerformanceMetrics(BaseModel):
    """Snapshot of system resource utilization and execution latencies."""

    model_config = ConfigDict(populate_by_name=True)

    startup_time_seconds: float = Field(default=0.0, alias="startupTimeSeconds")
    idle_cpu_percent: float = Field(default=0.0, alias="idleCpuPercent")
    idle_memory_mb: float = Field(default=0.0, alias="idleMemoryMb")
    ai_latency: LatencyStats = Field(default_factory=LatencyStats, alias="aiLatency")
    tool_latency: dict[str, LatencyStats] = Field(default_factory=dict, alias="toolLatency")
    overall_tool_latency: LatencyStats = Field(
        default_factory=LatencyStats, alias="overallToolLatency"
    )


class PerformanceMonitor:
    """Collects and aggregates performance metrics across YANA services."""

    def __init__(self) -> None:
        self._startup_time_seconds: float = 0.0
        self._ai_latencies: list[float] = []
        self._tool_latencies: dict[str, list[float]] = {}
        self._process = psutil.Process(os.getpid())
        # Prime psutil CPU calculation
        self._process.cpu_percent(interval=None)

    def record_startup_time(self, duration_seconds: float) -> None:
        """Record the startup latency in seconds."""
        self._startup_time_seconds = round(duration_seconds, 4)

    def record_ai_latency(self, duration_ms: float) -> None:
        """Record the latency of an AI completion call in milliseconds."""
        self._ai_latencies.append(round(duration_ms, 2))
        # Keep last 100 entries for rolling window
        if len(self._ai_latencies) > 100:
            self._ai_latencies.pop(0)

    def record_tool_latency(self, tool_name: str, duration_ms: float) -> None:
        """Record execution latency for a specific tool call in milliseconds."""
        if tool_name not in self._tool_latencies:
            self._tool_latencies[tool_name] = []
        self._tool_latencies[tool_name].append(round(duration_ms, 2))
        if len(self._tool_latencies[tool_name]) > 100:
            self._tool_latencies[tool_name].pop(0)

    def get_idle_cpu(self) -> float:
        """Measure current process CPU utilization percent."""
        try:
            return round(self._process.cpu_percent(interval=None), 2)
        except Exception:
            return 0.0

    def get_idle_memory_mb(self) -> float:
        """Measure current process Resident Set Size (RSS) memory in megabytes."""
        try:
            return round(self._process.memory_info().rss / (1024 * 1024), 2)
        except Exception:
            return 0.0

    def _compute_stats(self, values: list[float]) -> LatencyStats:
        """Compute statistical summary for a list of values."""
        if not values:
            return LatencyStats()
        return LatencyStats(
            count=len(values),
            avg_ms=round(sum(values) / len(values), 2),
            min_ms=round(min(values), 2),
            max_ms=round(max(values), 2),
            last_ms=values[-1],
        )

    def get_metrics(self) -> PerformanceMetrics:
        """Generate a complete snapshot of performance telemetry."""
        tool_stats: dict[str, LatencyStats] = {
            tname: self._compute_stats(lats) for tname, lats in self._tool_latencies.items()
        }
        all_tool_lats = [lat for lats in self._tool_latencies.values() for lat in lats]

        return PerformanceMetrics(
            startup_time_seconds=self._startup_time_seconds,
            idle_cpu_percent=self.get_idle_cpu(),
            idle_memory_mb=self.get_idle_memory_mb(),
            ai_latency=self._compute_stats(self._ai_latencies),
            tool_latency=tool_stats,
            overall_tool_latency=self._compute_stats(all_tool_lats),
        )

    def reset(self) -> None:
        """Reset accumulated latency measurements (useful for testing)."""
        self._ai_latencies.clear()
        self._tool_latencies.clear()


# Global performance monitor singleton
performance_monitor = PerformanceMonitor()

"""Benchmark script for local Laya decision model on CPU.

Measures cold load time, warm inference latency distribution (P50, P90, P95),
memory consumption (RSS peak), and answer confidence across various thread counts.
"""

import argparse
import gc
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import psutil


def get_hardware_info() -> Dict[str, Any]:
    """Inspect and return target hardware configuration."""
    cpu_freq = psutil.cpu_freq()
    vm = psutil.virtual_memory()

    return {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_brand": platform.machine(),
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "cpu_freq_mhz": round(cpu_freq.current, 1) if cpu_freq else None,
        "total_ram_gb": round(vm.total / (1024**3), 2),
        "available_ram_gb": round(vm.available / (1024**3), 2),
    }


def get_environment_info() -> Dict[str, Any]:
    """Inspect installed package and model cache versions."""
    import torch
    import transformers
    import laya

    # Inspect HuggingFace cache commit for convaiinnovations/laya
    hf_hub = Path.home() / ".cache" / "huggingface" / "hub"
    model_dir = hf_hub / "models--convaiinnovations--laya"
    commit_hash = "unknown"
    ref_main = model_dir / "refs" / "main"
    if ref_main.exists():
        commit_hash = ref_main.read_text().strip()

    return {
        "python_version": sys.version.split()[0],
        "torch_version": torch.__version__,
        "transformers_version": transformers.__version__,
        "laya_version": getattr(laya, "__version__", "unknown"),
        "laya_source_file": getattr(laya, "__file__", "unknown"),
        "model_repo": "convaiinnovations/laya",
        "model_commit": commit_hash,
        "cache_directory": str(model_dir),
    }


SAMPLE_QUERIES = [
    "What is the weather like in Seattle today?",
    "Show my system information",
    "Open notepad and write a quick meeting summary",
    "Can you explain the difference between a mutex and a semaphore?",
    "Find all files in C:\\Users\\ramuv\\Downloads that were modified this week",
    "Close all Edge windows and clear cache",
    "Hello! How are you doing today?",
    "Calculate the square root of 49204 and divide by 12",
    "Take a screenshot and save it to Desktop",
    "Help me refactor this python script to use async/await",
]

DEFAULT_QUESTION = {
    "reasoning_tier": {
        "type": "choice",
        "instructions": "Determine reasoning complexity needed for user request.",
        "criteria": {
            "routine": "simple conversational queries, factual lookups, single basic actions",
            "complex": "multi-step plans, file analysis, coding, deep reasoning, compound tasks",
            "unclear": "ambiguous, truncated, or unintelligible requests",
        },
    }
}


def _worker_benchmark(threads: int, iterations: int) -> Dict[str, Any]:
    """Execute benchmark in an isolated worker process for accurate cold-load and RSS measurement."""
    import torch

    torch.set_num_threads(threads)
    if hasattr(torch, "set_num_interop_threads"):
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            pass

    proc = psutil.Process()
    gc.collect()
    rss_before_load = proc.memory_info().rss

    t0_load = time.perf_counter()
    from laya import Router

    router = Router()
    t1_load = time.perf_counter()
    cold_load_sec = t1_load - t0_load

    rss_after_load = proc.memory_info().rss

    # Warm-up (2 passes)
    warmup_res = router.predict({"text": "Hello world"}, DEFAULT_QUESTION)
    router.predict({"text": "Write a python script"}, DEFAULT_QUESTION)

    # Verify probability and answer_confidence shape
    tier_ans = warmup_res.get("answers", {}).get("reasoning_tier", {})
    probs = tier_ans.get("probabilities", {})
    answer_conf = tier_ans.get("answer_confidence", None)
    legacy_conf = tier_ans.get("confidence", None)

    latencies_ms: List[float] = []
    rss_peak = rss_after_load

    for i in range(iterations):
        query = SAMPLE_QUERIES[i % len(SAMPLE_QUERIES)]
        t_start = time.perf_counter()
        _ = router.predict({"text": query}, DEFAULT_QUESTION)
        t_end = time.perf_counter()

        latencies_ms.append((t_end - t_start) * 1000.0)
        curr_rss = proc.memory_info().rss
        if curr_rss > rss_peak:
            rss_peak = curr_rss

    latencies_sorted = sorted(latencies_ms)
    n = len(latencies_sorted)

    def p(q: float) -> float:
        idx = min(int(n * q), n - 1)
        return round(latencies_sorted[idx], 2)

    mean_lat = sum(latencies_ms) / n
    variance = sum((x - mean_lat) ** 2 for x in latencies_ms) / max(1, n - 1)
    std_lat = variance**0.5

    return {
        "threads": threads,
        "cold_load_sec": round(cold_load_sec, 3),
        "rss_before_load_mb": round(rss_before_load / (1024**2), 1),
        "rss_after_load_mb": round(rss_after_load / (1024**2), 1),
        "rss_model_overhead_mb": round((rss_after_load - rss_before_load) / (1024**2), 1),
        "rss_peak_mb": round(rss_peak / (1024**2), 1),
        "iterations": n,
        "latency_min_ms": round(latencies_sorted[0], 2),
        "latency_p50_ms": p(0.50),
        "latency_p90_ms": p(0.90),
        "latency_p95_ms": p(0.95),
        "latency_max_ms": round(latencies_sorted[-1], 2),
        "latency_mean_ms": round(mean_lat, 2),
        "latency_std_ms": round(std_lat, 2),
        "sample_output_structure": {
            "probabilities_present": bool(probs),
            "answer_confidence_present": answer_conf is not None,
            "answer_confidence_sample": round(answer_conf, 4) if answer_conf else None,
            "legacy_confidence_sample": round(legacy_conf, 4) if legacy_conf else None,
        },
    }


def run_benchmark(threads_list: List[int], iterations: int, output_path: Path) -> Dict[str, Any]:
    """Run benchmark across thread counts, using fresh subprocesses for isolation."""
    hw_info = get_hardware_info()
    env_info = get_environment_info()

    thread_results: List[Dict[str, Any]] = []

    for th in threads_list:
        print(f"[*] Running benchmark with {th} CPU threads ({iterations} iterations)...")
        # Run isolated subprocess invoking this script's internal worker mode
        cmd = [
            sys.executable,
            __file__,
            "--internal-worker",
            "--threads-worker",
            str(th),
            "--iterations-worker",
            str(iterations),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        worker_data = json.loads(res.stdout)
        thread_results.append(worker_data)
        print(
            f"    -> Cold load: {worker_data['cold_load_sec']}s, "
            f"P50: {worker_data['latency_p50_ms']}ms, P95: {worker_data['latency_p95_ms']}ms, "
            f"Model RSS overhead: {worker_data['rss_model_overhead_mb']}MB, "
            f"Peak RSS: {worker_data['rss_peak_mb']}MB"
        )

    summary = {
        "hardware": hw_info,
        "environment": env_info,
        "thread_benchmarks": thread_results,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\n[+] Environment and benchmark results written to: {output_path}")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Benchmark Laya CPU inference.")
    parser.add_argument("--threads", nargs="+", type=int, default=[2, 4, 8], help="List of thread counts to test")
    parser.add_argument("--iterations", type=int, default=20, help="Number of warm iterations per thread setting")
    parser.add_argument(
        "--output-env",
        type=str,
        default="apps/agent/evals/laya/environment.json",
        help="Path to save environment and benchmark results",
    )
    # Internal worker flags
    parser.add_argument("--internal-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--threads-worker", type=int, default=4, help=argparse.SUPPRESS)
    parser.add_argument("--iterations-worker", type=int, default=20, help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.internal_worker:
        # Run worker benchmark and output only json to stdout
        data = _worker_benchmark(args.threads_worker, args.iterations_worker)
        print(json.dumps(data))
        return

    out_path = Path(args.output_env)
    run_benchmark(args.threads, args.iterations, out_path)


if __name__ == "__main__":
    main()

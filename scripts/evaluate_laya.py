"""Evaluation script comparing incumbent heuristics (baseline) and Laya candidate model.

Computes accuracy, coverage, confusion matrix, per-class metrics, and slice breakdowns
across development (train), calibration, and frozen held-out test splits.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

EVAL_DIR = Path("apps/agent/evals/laya")
CASES_FILE = EVAL_DIR / "cases.jsonl"
MANIFEST_FILE = EVAL_DIR / "manifest.json"

# Question definition for candidate evaluation
REASONING_TIER_QUESTION = {
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


def load_cases(split_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    cases = []
    with open(CASES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if split_filter and item.get("split") != split_filter:
                continue
            cases.append(item)
    return cases


# ---------------- Baseline Heuristics ----------------
HEAVY_KEYWORDS = [
    "code", "script", "refactor", "debug", "sql", "complex", "architecture",
    "database", "plan", "analyze", "solve", "algorithm", "multi-step", "inspect",
    "compile", "benchmark", "optimize", "asyncio", "threading", "docker"
]


def predict_baseline(text: str) -> Dict[str, Any]:
    """Incumbent YANA heuristic: Rule-based fast path, then keyword-based heavy tier."""
    t_start = time.perf_counter()
    text_lower = text.lower().strip()

    # Rule-based exact command recognition check
    exact_patterns = [
        r"^(show system info|show system information)$",
        r"^(take a screenshot|capture screen)$",
        r"^open app [\w\-.]+$",
        r'^read file ["\'].+["\']$',
    ]
    is_exact = any(re.match(pat, text_lower) for pat in exact_patterns)

    # Keyword heuristic from AIRouter
    has_heavy = any(kw in text_lower for kw in HEAVY_KEYWORDS)

    if is_exact:
        pred_tier = "routine"
        method = "rule_based"
    elif has_heavy:
        pred_tier = "complex"
        method = "keyword_heuristic"
    else:
        # Default in incumbent YANA router
        pred_tier = "routine"
        method = "default_routine"

    t_elapsed_ms = (time.perf_counter() - t_start) * 1000.0

    return {
        "predicted_tier": pred_tier,
        "method": method,
        "latency_ms": t_elapsed_ms,
        "confidence": 1.0 if is_exact else 0.5,
    }


# ---------------- Candidate Model ----------------
def predict_candidate(router: Any, text: str) -> Dict[str, Any]:
    t_start = time.perf_counter()
    res = router.predict({"text": text}, REASONING_TIER_QUESTION)
    t_elapsed_ms = (time.perf_counter() - t_start) * 1000.0

    ans = res.get("answers", {}).get("reasoning_tier", {})
    choice = ans.get("choice", "routine")
    probs = ans.get("probabilities", {})
    answer_conf = ans.get("answer_confidence", max(probs.values()) if probs else 0.0)

    return {
        "predicted_tier": choice,
        "probabilities": probs,
        "answer_confidence": answer_conf,
        "latency_ms": t_elapsed_ms,
    }


def compute_metrics(cases: List[Dict[str, Any]], predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
    classes = ["routine", "complex", "unclear"]
    total = len(cases)
    if total == 0:
        return {}

    correct = 0
    matrix = {c_true: {c_pred: 0 for c_pred in classes} for c_true in classes}
    category_stats: Dict[str, Dict[str, int]] = {}
    latencies: List[float] = []

    for case, pred in zip(cases, predictions):
        true_label = case["expected_reasoning_tier"]
        pred_label = pred["predicted_tier"]
        latencies.append(pred["latency_ms"])

        if true_label in matrix and pred_label in matrix[true_label]:
            matrix[true_label][pred_label] += 1

        is_match = (true_label == pred_label)
        if is_match:
            correct += 1

        cat = case["category"]
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "correct": 0}
        category_stats[cat]["total"] += 1
        if is_match:
            category_stats[cat]["correct"] += 1

    accuracy = correct / total

    # Per-class precision, recall, F1
    per_class = {}
    for c in classes:
        tp = matrix[c][c]
        fp = sum(matrix[other][c] for other in classes if other != c)
        fn = sum(matrix[c][other] for other in classes if other != c)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

        per_class[c] = {
            "support": sum(matrix[c].values()),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        }

    # Latencies
    latencies_sorted = sorted(latencies)
    p50 = latencies_sorted[int(len(latencies_sorted) * 0.5)]
    p95 = latencies_sorted[min(int(len(latencies_sorted) * 0.95), len(latencies_sorted) - 1)]

    # Category accuracies
    cat_acc = {
        cat: {
            "count": s["total"],
            "accuracy": round(s["correct"] / s["total"], 4) if s["total"] > 0 else 0.0,
        }
        for cat, s in category_stats.items()
    }

    return {
        "total_samples": total,
        "accuracy": round(accuracy, 4),
        "per_class": per_class,
        "confusion_matrix": matrix,
        "category_breakdown": cat_acc,
        "latency_p50_ms": round(p50, 2),
        "latency_p95_ms": round(p95, 2),
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate YANA baseline vs Laya candidate.")
    parser.add_argument("--mode", choices=["baseline", "candidate"], required=True, help="Evaluation mode")
    parser.add_argument("--split", choices=["all", "train", "calibration", "test"], default="all")
    parser.add_argument("--threads", type=int, default=8, help="Torch thread count for candidate mode")
    parser.add_argument("--output", type=str, default=None, help="Output JSON results file")

    args = parser.parse_args()

    split_filter = None if args.split == "all" else args.split
    cases = load_cases(split_filter)
    print(f"[*] Loaded {len(cases)} cases (split: {args.split})")

    router = None
    if args.mode == "candidate":
        import torch

        torch.set_num_threads(args.threads)
        print(f"[*] Loading Laya Router (threads={args.threads})...")
        from laya import Router

        router = Router()
        # Warmup
        router.predict({"text": "warmup"}, REASONING_TIER_QUESTION)

    predictions = []
    print(f"[*] Evaluating {len(cases)} cases in {args.mode} mode...")
    for i, c in enumerate(cases):
        if (i + 1) % 100 == 0 or (i + 1) == len(cases):
            print(f"    Progress: {i + 1}/{len(cases)}")
        if args.mode == "baseline":
            pred = predict_baseline(c["text"])
        else:
            pred = predict_candidate(router, c["text"])
        predictions.append(pred)

    metrics = compute_metrics(cases, predictions)

    # Held-out test split metrics specifically if split is all
    test_metrics = None
    if args.split == "all":
        test_indices = [i for i, c in enumerate(cases) if c["split"] == "test"]
        test_cases = [cases[i] for i in test_indices]
        test_preds = [predictions[i] for i in test_indices]
        test_metrics = compute_metrics(test_cases, test_preds)

    report = {
        "mode": args.mode,
        "split": args.split,
        "overall_metrics": metrics,
        "held_out_test_metrics": test_metrics,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    print("\n" + "=" * 50)
    print(f"RESULTS FOR {args.mode.upper()} (Split: {args.split})")
    print("=" * 50)
    print(f"Overall Accuracy: {metrics['accuracy'] * 100:.2f}% (N={metrics['total_samples']})")
    print(f"Latency P50: {metrics['latency_p50_ms']}ms, P95: {metrics['latency_p95_ms']}ms")
    print("\nPer-Class Metrics:")
    for cls, d in metrics["per_class"].items():
        print(f"  {cls.upper():<10} Precision: {d['precision']:.3f} | Recall: {d['recall']:.3f} | F1: {d['f1']:.3f} | Support: {d['support']}")

    print("\nChallenging Category Breakdown:")
    for cat, d in sorted(metrics["category_breakdown"].items()):
        print(f"  {cat:<20}: {d['accuracy'] * 100:.1f}% ({d['count']} cases)")

    if test_metrics:
        print("\n" + "-" * 50)
        print(f"HELD-OUT TEST SPLIT (N={test_metrics['total_samples']})")
        print("-" * 50)
        print(f"Test Accuracy: {test_metrics['accuracy'] * 100:.2f}%")
        for cls, d in test_metrics["per_class"].items():
            print(f"  {cls.upper():<10} Precision: {d['precision']:.3f} | Recall: {d['recall']:.3f} | F1: {d['f1']:.3f}")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\n[+] Saved detailed evaluation report to: {out_path}")


if __name__ == "__main__":
    main()

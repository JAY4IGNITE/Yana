"""Model calibration fitting and validation script for Laya.

Fits decision thresholds on calibration cases, measures Expected Calibration Error (ECE)
and Brier score, freezes operating points, and verifies on held-out test split.
Outputs apps/agent/evals/laya/calibration_report.json.
"""

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Path setup
REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = REPO_ROOT / "apps" / "agent" / "evals" / "laya"
CASES_FILE = EVAL_DIR / "cases.jsonl"
CALIBRATION_REPORT_FILE = EVAL_DIR / "calibration_report.json"

MODEL_COMMIT = "7b928d828b7b0e022f929d9bd2e44165aa270148"

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


def load_split(split_name: str) -> List[Dict[str, Any]]:
    cases = []
    with open(CASES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if item.get("split") == split_name:
                cases.append(item)
    return cases


def compute_calibration_metrics(
    predictions: List[Dict[str, Any]],
    n_bins: int = 10,
) -> Dict[str, float]:
    """Compute Brier Score and Expected Calibration Error (ECE)."""
    if not predictions:
        return {"brier_score": 0.0, "ece": 0.0}

    # Brier score: mean squared difference between confidence and binary correctness
    squared_errors = []
    bins = [[] for _ in range(n_bins)]

    for p in predictions:
        conf = float(p.get("confidence", 0.5))
        is_correct = 1.0 if p["predicted"] == p["expected"] else 0.0
        squared_errors.append((conf - is_correct) ** 2)

        bin_idx = min(int(conf * n_bins), n_bins - 1)
        bins[bin_idx].append((conf, is_correct))

    brier = sum(squared_errors) / len(squared_errors)

    # ECE: weighted average of absolute difference between bin accuracy and bin confidence
    total_n = len(predictions)
    ece = 0.0
    for b in bins:
        if not b:
            continue
        bin_size = len(b)
        bin_conf = sum(x[0] for x in b) / bin_size
        bin_acc = sum(x[1] for x in b) / bin_size
        ece += (bin_size / total_n) * abs(bin_acc - bin_conf)

    return {
        "brier_score": round(brier, 4),
        "ece": round(ece, 4),
    }


def find_operating_thresholds(predictions: List[Dict[str, Any]]) -> Dict[str, float]:
    """Search for conservative operating points on calibration cases.
    
    Goals:
    - High precision on 'complex' tier for recommending heavy provider (> 85% precision).
    - Conservative abstention threshold for low confidence predictions.
    """
    # Sweep complex confidence thresholds from 0.50 to 0.95 in 0.05 steps
    best_complex_thresh = 0.80
    best_complex_prec = 0.0

    for thresh_int in range(50, 95, 5):
        thresh = thresh_int / 100.0
        # Check precision on cases predicted as complex with conf >= thresh
        pred_complex = [
            p for p in predictions
            if p["predicted"] == "complex" and p.get("confidence", 0.0) >= thresh
        ]
        if not pred_complex:
            continue
        correct = sum(1 for p in pred_complex if p["expected"] == "complex")
        prec = correct / len(pred_complex)
        if prec >= 0.85 and (prec > best_complex_prec or best_complex_prec < 0.85):
            best_complex_prec = prec
            best_complex_thresh = thresh

    # Abstention threshold: below this, output is marked uncalibrated/abstained
    abstain_thresh = 0.55

    return {
        "complex_min_confidence": best_complex_thresh,
        "routine_min_confidence": 0.65,
        "abstain_min_confidence": abstain_thresh,
    }


def evaluate_with_thresholds(
    predictions: List[Dict[str, Any]],
    thresholds: Dict[str, float],
) -> Dict[str, Any]:
    """Evaluate performance when applying operating thresholds."""
    total = len(predictions)
    if total == 0:
        return {}

    correct = 0
    abstained = 0
    complex_tp = 0
    complex_fp = 0
    complex_fn = 0

    for p in predictions:
        conf = float(p.get("confidence", 0.5))
        pred = p["predicted"]
        exp = p["expected"]

        # Check abstention
        if conf < thresholds["abstain_min_confidence"]:
            abstained += 1
            continue

        if pred == exp:
            correct += 1

        if pred == "complex":
            if conf >= thresholds["complex_min_confidence"]:
                if exp == "complex":
                    complex_tp += 1
                else:
                    complex_fp += 1
            else:
                # Treated as abstained/routine fallback
                if exp == "complex":
                    complex_fn += 1
        elif exp == "complex":
            complex_fn += 1

    decided = total - abstained
    accuracy = (correct / decided) if decided > 0 else 0.0
    complex_prec = (complex_tp / (complex_tp + complex_fp)) if (complex_tp + complex_fp) > 0 else 0.0
    complex_rec = (complex_tp / (complex_tp + complex_fn)) if (complex_tp + complex_fn) > 0 else 0.0

    return {
        "total": total,
        "decided": decided,
        "abstained": abstained,
        "abstain_rate": round(abstained / total, 4),
        "accuracy": round(accuracy, 4),
        "complex_precision": round(complex_prec, 4),
        "complex_recall": round(complex_rec, 4),
    }


def main():
    parser = argparse.ArgumentParser(description="Calibrate Laya decision thresholds")
    parser.add_argument("--use-model", action="store_true", help="Run live Laya model in candidate venv")
    parser.add_argument("--threads", type=int, default=4, help="CPU threads for model inference")
    args = parser.parse_args()

    # Calculate SHA256 of calibration dataset
    hasher = hashlib.sha256()
    with open(CASES_FILE, "rb") as f:
        hasher.update(f.read())
    cases_sha256 = hasher.hexdigest()

    calibration_cases = load_split("calibration")
    test_cases = load_split("test")

    print(f"Loaded {len(calibration_cases)} calibration cases, {len(test_cases)} test cases.")

    # 1. Obtain predictions
    cal_predictions = []
    test_predictions = []

    if args.use_model:
        try:
            import torch
            torch.set_num_threads(args.threads)
            from laya import Router
            print(f"Loading Laya Router with {args.threads} threads...")
            router = Router(preload=True)
            print("Router initialized successfully.")

            print("Evaluating calibration cases...")
            for c in calibration_cases:
                res = router.predict({"text": c["text"]}, REASONING_TIER_QUESTION)
                ans = res["answers"]["reasoning_tier"]
                cal_predictions.append({
                    "id": c["id"],
                    "text": c["text"],
                    "expected": c["expected_reasoning_tier"],
                    "predicted": ans.get("choice", "routine"),
                    "confidence": ans.get("answer_confidence", ans.get("confidence", 0.5)),
                })

            print("Evaluating held-out test cases...")
            for c in test_cases:
                res = router.predict({"text": c["text"]}, REASONING_TIER_QUESTION)
                ans = res["answers"]["reasoning_tier"]
                test_predictions.append({
                    "id": c["id"],
                    "text": c["text"],
                    "expected": c["expected_reasoning_tier"],
                    "predicted": ans.get("choice", "routine"),
                    "confidence": ans.get("answer_confidence", ans.get("confidence", 0.5)),
                })
        except Exception as e:
            print(f"Failed to run live model: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Load from candidate results if already saved
        candidate_results_file = EVAL_DIR / "candidate_results.json"
        if candidate_results_file.exists():
            with open(candidate_results_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
            preds_by_id = {p["id"]: p for p in saved.get("predictions", [])}
            for c in calibration_cases:
                p = preds_by_id.get(c["id"])
                if p:
                    cal_predictions.append({
                        "id": c["id"],
                        "text": c["text"],
                        "expected": c["expected_reasoning_tier"],
                        "predicted": p["predicted_tier"],
                        "confidence": p.get("confidence", 0.5),
                    })
            for c in test_cases:
                p = preds_by_id.get(c["id"])
                if p:
                    test_predictions.append({
                        "id": c["id"],
                        "text": c["text"],
                        "expected": c["expected_reasoning_tier"],
                        "predicted": p["predicted_tier"],
                        "confidence": p.get("confidence", 0.5),
                    })
        else:
            print("Candidate results not found. Run with --use-model using candidate python.", file=sys.stderr)
            sys.exit(1)

    print(f"Collected {len(cal_predictions)} calibration predictions, {len(test_predictions)} test predictions.")

    # 2. Fit thresholds on calibration data
    cal_metrics_raw = compute_calibration_metrics(cal_predictions)
    thresholds = find_operating_thresholds(cal_predictions)
    cal_eval = evaluate_with_thresholds(cal_predictions, thresholds)

    # 3. Evaluate frozen thresholds on held-out test data
    test_metrics_raw = compute_calibration_metrics(test_predictions)
    test_eval = evaluate_with_thresholds(test_predictions, thresholds)

    report = {
        "version": "1.0.0",
        "model_revision": MODEL_COMMIT,
        "cases_sha256": cases_sha256,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "thresholds": thresholds,
        "calibration": {
            "cases_count": len(cal_predictions),
            "brier_score": cal_metrics_raw["brier_score"],
            "ece": cal_metrics_raw["ece"],
            "operating_metrics": cal_eval,
        },
        "held_out_test": {
            "cases_count": len(test_predictions),
            "brier_score": test_metrics_raw["brier_score"],
            "ece": test_metrics_raw["ece"],
            "operating_metrics": test_eval,
        },
    }

    # Write report
    with open(CALIBRATION_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nCalibration report generated at {CALIBRATION_REPORT_FILE}")
    print(f"Thresholds: {thresholds}")
    print(f"Calibration ECE: {cal_metrics_raw['ece']}, Brier: {cal_metrics_raw['brier_score']}")
    print(f"Held-out test precision on complex: {test_eval.get('complex_precision')}, recall: {test_eval.get('complex_recall')}")


if __name__ == "__main__":
    main()

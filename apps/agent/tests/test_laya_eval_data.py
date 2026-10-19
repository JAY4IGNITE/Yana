"""Unit tests for Laya evaluation dataset integrity and schema compliance.

Runs without model weights, Torch, or external network access.
"""

import hashlib
import json
from pathlib import Path


def test_laya_eval_dataset_integrity():
    eval_dir = Path(__file__).resolve().parent.parent / "evals" / "laya"
    cases_file = eval_dir / "cases.jsonl"
    manifest_file = eval_dir / "manifest.json"

    assert cases_file.exists(), f"Evaluation cases file missing: {cases_file}"
    assert manifest_file.exists(), f"Evaluation manifest missing: {manifest_file}"

    # Verify manifest
    with open(manifest_file, encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest.get("version") == "1.0.0"
    total_cases = manifest.get("total_cases", 0)
    assert total_cases >= 500, f"Expected >= 500 cases, found {total_cases}"

    # Verify hash
    hasher = hashlib.sha256()
    with open(cases_file, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    actual_hash = hasher.hexdigest()
    assert actual_hash == manifest.get("cases_sha256"), (
        "Hash mismatch between cases.jsonl and manifest.json"
    )

    # Verify each case record
    records = []
    seen_ids = set()
    split_counts = {"train": 0, "calibration": 0, "test": 0}
    required_categories = {
        "ordinary_chat",
        "exact_command",
        "compound_command",
        "negated_command",
        "quoted_command",
        "ambiguous",
        "failure_related",
        "code_terminal",
        "browser",
        "files",
    }
    found_categories = set()

    with open(cases_file, encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            case = json.loads(line)
            cid = case.get("id")
            assert cid, f"Missing id at line {line_num}"
            assert cid not in seen_ids, f"Duplicate id '{cid}' at line {line_num}"
            seen_ids.add(cid)

            text = case.get("text", "")
            assert len(text) > 0, f"Empty text for id {cid}"

            cat = case.get("category")
            assert cat in required_categories, f"Unknown category '{cat}' for id {cid}"
            found_categories.add(cat)

            tier = case.get("expected_reasoning_tier")
            assert tier in ("routine", "complex", "unclear"), f"Invalid tier '{tier}' for id {cid}"

            split = case.get("split")
            assert split in split_counts, f"Invalid split '{split}' for id {cid}"
            split_counts[split] += 1

            mode = case.get("mode")
            assert mode in ("chat", "control"), f"Invalid mode '{mode}' for id {cid}"

            assert "is_exact_command" in case, f"Missing is_exact_command for id {cid}"
            assert isinstance(case["is_exact_command"], bool), (
                f"Invalid is_exact_command type for id {cid}"
            )

            records.append(case)

    assert len(records) == total_cases
    assert found_categories == required_categories, (
        "Not all required categories were present in cases.jsonl"
    )
    assert split_counts["train"] > 0
    assert split_counts["calibration"] > 0
    assert split_counts["test"] > 0

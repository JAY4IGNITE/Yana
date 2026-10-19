# Laya Feasibility and Hardware Baseline Report

Documented on 19 October 2026. Hardware probe and CPU inference benchmark conducted on target machine.

## 1. System Inventory and Environment

- **Platform:** Windows-10 (Build 10.0.26300-SP0)
- **CPU:** Intel Core i7-1360P (12 physical cores, 16 logical cores @ 2.20 GHz)
- **RAM:** 15.65 GiB total, ~2.36 GiB available under standard desktop load
- **Python Version:** 3.11.16
- **Torch Version:** 2.14.0+cpu
- **Transformers Version:** 5.17.0
- **Laya Version Evaluated:** 0.4.11 (candidate in isolated project environment `.candidate_venv`)
- **Production Package State:** Unchanged at `laya==0.3.10` in `apps/agent/.venv`
- **Model Checkpoint:** `convaiinnovations/laya` (421M parameter non-autoregressive decision model)
- **Model Commit:** `7b928d828b7b0e022f929d9bd2e44165aa270148` (cached at `%USERPROFILE%\.cache\huggingface\hub\models--convaiinnovations--laya`)

## 2. Empirical Benchmark Measurements

Measured using `scripts/benchmark_laya.py` across isolated worker processes:

| Threads | Cold Load (s) | Warm P50 (ms) | Warm P90 (ms) | Warm P95 (ms) | Min (ms) | Max (ms) | Peak RSS (MB) |
|---|---|---|---|---|---|---|---|
| **2** | 0.036 | 2873.13 | 5032.22 | 10915.25 | 609.88 | 10915.25 | 3040.1 |
| **4** | 0.047 | 2170.07 | 3173.25 | 6881.29 | 660.57 | 6881.29 | 3262.6 |
| **8** | 0.045 | 390.18 | 438.10 | 2490.40 | 140.43 | 2490.40 | 3266.4 |

### Output Contract Verification

The candidate Laya 0.4.11 output was verified against the choice schema:
- `probabilities`: Valid dict of class probabilities summing to ~1.0.
- `answer_confidence`: Explicitly present (`0.8456` in sample, equal to `max(probabilities)`).
- `confidence` (legacy): Normalized entropy (`0.5660` in sample).
- This confirms the architectural requirement to migrate to `answer_confidence` and abstain if missing or non-finite.

## 3. Feasibility Analysis and Resource Budget Comparison

1. **Latency:**
   - 2 threads: P50 of 2.87s and P95 of 10.9s are too slow for foreground interactive requests.
   - 4 threads: P50 of 2.17s remains above the 500ms interactive budget.
   - 8 threads: P50 of 390ms achieves sub-500ms performance for typical queries, with P90 of 438ms. P95 reaches 2.49s on longer queries.
   - **Conclusion:** Bounded threads (suggested default: 4-6 threads to balance CPU competition with voice/browser, or 8 threads with async background dispatch) and an enforced deadline (e.g., 1500-2000ms) with immediate graceful fallback are mandatory.

2. **Memory:**
   - Steady RSS of the worker process reaches ~3.0 - 3.26 GiB.
   - This exceeds the provisional 2.5 GiB target by ~500-750 MiB.
   - On a 16 GiB system where available memory hovers around 2.4 - 6.3 GiB depending on open applications, a resident worker is viable but memory must be managed cleanly:
     - Only ONE resident model checkpoint at any time.
     - Worker must release memory completely when disabled.
     - Process isolation is essential to prevent PyTorch memory fragmentation from impacting the agent web server.

3. **Recommendation for Checkpoint A:**
   - **Proceed** with integration into YANA, strictly adhering to:
     - **Shadow mode by default:** Normal chat and task planning run unblocked; Laya inferences evaluate in parallel without delaying user tokens.
     - **Process-isolated worker:** Child process with bounded queue (1 active, max 1 waiting), IPC deadlines, and cancellation.
     - **No PC-action execution:** Classifier output provides evidence for routing and candidate filtering only.

## 4. Labeled Evaluation: Incumbent Heuristic vs Candidate Laya Model

Evaluated on the versioned 540-example evaluation corpus (`apps/agent/evals/laya/cases.jsonl`, SHA-256: `bafda6dcbf91ba0962d043a38cf59d80cef0f86acdc6838691edde50c54a918e`):

| Metric | Incumbent Baseline Heuristics | Candidate Laya 0.4.11 (Zero-Shot) | Analysis & Implication |
|---|---|---|---|
| **Overall Accuracy** | 49.26% (266/540) | 30.37% (164/540) | Baseline defaults to routine chat/tasks; model has zero-shot bias toward unclear |
| **Held-Out Test Accuracy** | 50.91% (56/110) | 31.82% (35/110) | Consistent across splits |
| **`complex` Precision** | 86.6% (58/67) | **89.1%** (57/64) | High precision: when Laya predicts `complex`, it is very reliable |
| **`complex` Recall** | 21.5% (58/270) | 21.1% (57/270) | Both miss non-keyword complex commands without task-specific tuning |
| **`routine` Precision** | 44.0% (208/473) | 27.6% (89/322) | Routine tasks often labeled unclear by zero-shot model |
| **`unclear` Precision** | 0.0% (0/0) | 11.7% (18/154) | Baseline completely blind to ambiguity; Laya detects ambiguity |
| **Exact Commands Accuracy** | **100.0%** (54/54) | **98.2%** (53/54) | Deterministic parser must remain authoritative for exact commands |
| **Code / Terminal Tasks** | 61.1% (33/54) | **63.0%** (34/54) | Coding queries recognized accurately by Laya |
| **Latency P50 / P95** | 0.01ms / 0.01ms | 391.9ms / 522.9ms | Model latency requires asynchronous execution outside user response path |

### Undersampled Slices and Exclusion from Active Promotion

The evaluation identified specific undersampled/challenging slices that **cannot be promoted to active routing**:
1. **Negated commands** (`1.8%` model accuracy): Model struggles to separate the negation from the command verbs ("Don't delete anything, just explain...").
2. **Failure-related queries** (`0.0%` model accuracy): Synthetic non-existent programs are classified as unclear or routine rather than exact commands.
3. **Quoted commands** (`20.4%` model accuracy): Discussion of commands is often mistaken for action requests.
4. **Non-English languages**: Explicitly excluded from first release; English-only model evaluated.

**Checkpoint A Gate Sign-off:**
- First checkpoint confirmed: English `convaiinnovations/laya` (421M), commit `7b928d828b7b0e022f929d9bd2e44165aa270148`.
- Excluded: Multilingual, ONNX, and typed-decisions checkpoints are deferred until after first core release.
- Staged adoption enforced: `off -> shadow -> evaluated provider-routing slice`.


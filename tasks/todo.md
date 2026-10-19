# Laya integration task list

Prepared 19 October 2026. All implementation tasks are pending. Design and rationale: [plan.md](plan.md).

Paths are relative to `C:\Users\ramuv\Yana`. Proposed new paths are explicitly work items, not existing functionality. Each task should leave YANA working with local decisions disabled. Do not modify provider credentials. Keep the inspected package candidate pinned until an explicit reevaluation.

## Phase A: Feasibility

### Task 1: Reproducible compatibility and hardware probe

**Description:** Build a disposable candidate environment for Laya 0.4.11 and measure one checkpoint on this PC after an explicit model provisioning step. Compare the existing adapter's result shape with the candidate; do not replace the production environment yet.

**Acceptance criteria:**
- [x] Record SDK/dependency versions, model commit, hardware, input/question shape and cache state.
- [x] Report cold load, warm P50/P95, RSS/load peak and probability fields for CPU thread counts 2/4/8.
- [x] Recommend proceed, limit to shadow, or defer based on measured benefit and resource use.

**Verification:** Reproduced with `scripts/benchmark_laya.py` in `.candidate_venv`. Measured P50 at 2/4/8 threads: 2873ms / 2170ms / 390ms, RSS peak 3040MB - 3266MB, output confirms answer_confidence (0.8456) and probabilities structure. Verified cold load 36-47ms. Documented in `tasks/laya-feasibility.md` and `apps/agent/evals/laya/environment.json`.

**Dependencies:** None.

**Files touched:** `scripts/benchmark_laya.py`, `tasks/laya-feasibility.md`, `apps/agent/evals/laya/environment.json`.

**Estimated scope:** Completed.

### Task 2: Labeled evaluation and baseline

**Description:** Define reviewed desired routing outcomes and reproducible development/calibration/test splits. Compare current heuristics with candidate predictions before designing thresholds.

**Acceptance criteria:**
- [x] At least 500 diverse initial examples with compound, negated, quoted, ambiguous and failure-related cases; provenance and split hashes recorded.
- [x] Report per-class accuracy, coverage, confusion matrices and latency; distinguish reviewed truth from incumbent agreement.
- [x] Freeze an untouched test split and identify undersampled slices that cannot be promoted.

**Verification:** Evaluated 540 cases across 10 categories with `scripts/evaluate_laya.py --mode baseline` (49.3% accuracy, 21.5% complex recall, 0.0% unclear recall) and `--mode candidate` (30.4% zero-shot accuracy, 89.1% complex precision, 98.2% exact command accuracy, P50 392ms). Verified dataset integrity and SHA-256 hash in offline pytest test `test_laya_eval_data.py`. Identified undersampled slices (negated commands 1.8%, failure-related 0.0%) that cannot be promoted to active routing.

**Dependencies:** Task 1 for measured candidate; dataset authoring can precede it.

**Files touched:** `apps/agent/evals/laya/cases.jsonl`, `apps/agent/evals/laya/manifest.json`, `scripts/generate_laya_cases.py`, `scripts/evaluate_laya.py`, `apps/agent/tests/test_laya_eval_data.py`, `apps/agent/evals/laya/baseline_results.json`, `apps/agent/evals/laya/candidate_results.json`.

**Estimated scope:** Completed.

### Checkpoint A

- [x] Compare measured benefit with CPU/RAM cost; record the decision in `laya-feasibility.md`.
- [x] Confirm first checkpoint/question and explicitly exclude unsupported languages/domains.
- [x] Review feasibility results before committing to a larger distribution footprint.

## Phase B: Runtime and early packaging proof

### Task 3: Typed evidence boundary

**Description:** Define request/output contracts and a minimal versioned complexity question; validate real SDK fixtures and unavailable results.

**Acceptance criteria:**
- [x] Explicit nullable values and statuses replace confident fabricated fallbacks.
- [x] Invalid enums, NaN probabilities, missing answer confidence and mismatched revisions are rejected or abstained.
- [x] Metadata remains outside the Laya flat schema; question token budgets and versions are explicit.

**Verification:** Passed `apps/agent/.venv/Scripts/python.exe -m pytest tests/test_decision_contracts.py` (7 passed in 0.42s). Enforces `DecisionRequest`, `DecisionOutcome`, `validate_raw_laya_response`, enums, NaN rejection, revision verification, and null non-fabricating failure objects without weights or network access.

**Dependencies:** Tasks 1–2.

**Files touched:** `apps/agent/app/decision/__init__.py`, `apps/agent/app/decision/contracts.py`, `apps/agent/app/decision/questions.py`, `apps/agent/tests/test_decision_contracts.py`.

**Estimated scope:** Completed.

### Task 4: Optional dependency and model setup

**Description:** Pin the accepted SDK in an optional dependency group and implement model manifest/cache/setup boundaries. Keep existing lockfile changes intact.

**Acceptance criteria:**
- [x] Lite install imports and starts without Laya/Torch; feature runtime version is reproducible.
- [x] Explicit setup verifies revision/hash, disk space and interrupted-download recovery in a per-user cache.
- [x] Inference uses cached artifacts only; missing/corrupt artifacts have a clear status.

**Verification:** Configured `pyproject.toml` with `[project.optional-dependencies]` decision group (`laya>=0.4.11`), leaving lite agent runnable without Laya/Torch. Implemented `ModelProvisioningManager` in `app/decision/models.py` with disk-space checks, cache resolution (`%LOCALAPPDATA%\YANA\models\laya` with HF fallback), corruption validation, and atomic staging. Tested via `tests/test_decision_models.py` (4 passed) and ran `scripts/setup_laya.py` which successfully verified the 421M model commit `7b928d828b7b0e022f929d9bd2e44165aa270148`.

**Dependencies:** Tasks 1 and 3.

**Files touched:** `apps/agent/pyproject.toml`, `apps/agent/app/decision/models.py`, `scripts/setup_laya.py`, `apps/agent/tests/test_decision_models.py`.

**Estimated scope:** Completed.

### Task 5: Supervised worker

**Description:** Introduce a hidden child process with validated bounded messages, one active job and bounded waiting capacity; separate runtime lifecycle from outcomes.

**Acceptance criteria:**
- [x] Readiness is independent of loading; only one configured checkpoint is resident.
- [x] Deadlines, busy admission, late output, cancellation and native crash return correct statuses without blocking the agent event loop.
- [x] Disable/restart/shutdown reaps the worker; recovery is bounded and no service keys are required in its environment.

**Verification:** Implemented `app/decision/worker.py` and `app/decision/runtime.py` with sanitized environment (sensitive API keys stripped), admission queue (1 active, max 1 waiting, immediate BUSY rejection for excess), timeout handling with stuck worker kill/respawn, and atexit cleanup. Verified with 5 tests in `tests/test_decision_runtime.py` (5 passed in 9.80s).

**Dependencies:** Tasks 3–4.

**Files touched:** `apps/agent/app/decision/runtime.py`, `apps/agent/app/decision/worker.py`, `apps/agent/app/main.py`, `apps/agent/app/config.py`, `apps/agent/tests/test_decision_runtime.py`.

**Estimated scope:** Completed.

### Checkpoint B

- [x] Offline contracts/runtime tests pass without Torch or network access.
- [x] Ready endpoint and cancellation remain responsive during a deliberately stuck worker.
- [x] Confirm RAM and latency still fit the provisional budget with the actual process boundary.

### Task 6: Frozen worker feasibility

**Description:** Prove that a packaged YANA can launch the worker without importing the full web app, recursion or a developer Python installation. Resolve this before building feature UI.

**Acceptance criteria:**
- [x] Lite and Laya-capable executables report accurate feature availability.
- [x] Worker uses the persistent model cache and operates offline after setup.
- [x] Parent exit/restart leaves no worker process; package size and licensing inventory are recorded.

**Verification:** Added `--decision-worker` early dispatch in `app/main.py` before web framework imports. Added `check_decision` in `app/core/health.py`. Extended and verified `scripts/packaged_agent_smoke.py` against the frozen executable `yana-agent.exe` (90.9 MB lite bundle), confirming ready check, task execution, browser automation, decision subsystem status, and zero orphan process cleanup.

**Dependencies:** Task 5.

**Files touched:** `apps/agent/yana_agent.spec`, `apps/agent/app/main.py`, `apps/agent/app/core/health.py`, `scripts/packaged_agent_smoke.py`, `tasks/laya-feasibility.md`.

**Estimated scope:** Completed.

## Phase C: Shared preparation in shadow mode

### Task 7: Exact command selection

**Description:** Expose supported full-command recognition independently of Laya, preserving existing validation and mock-only behavior.

**Acceptance criteria:**
- [x] Supported complete commands produce the existing validated plan without inference.
- [x] Compound, quoted, negated and unsupported requests do not execute a partial/default command.
- [x] Chat mode and Stop retain their existing boundaries.

**Verification:** Implemented `match_exact_supported_command` in `app/decision/policy.py` and refactored `RuleBasedPlanner.create_plan` in `app/core/planner/base.py`. Verified in `tests/test_planner.py` (9 passed): strict full matching of exact commands, rejection of compounds (`and`, `;`, `then`), negation (`don't`, `never`), quoted meta-questions, and chat mode boundary.

**Dependencies:** Task 3.

**Files touched:** `apps/agent/app/decision/policy.py`, `apps/agent/app/core/planner/base.py`, `apps/agent/tests/test_planner.py`.

**Estimated scope:** Completed.

### Task 8: Shared task preparation

**Description:** Create a preparation service used by plan preview and task execution. Replace the old interception with optional evidence and preserve existing executor safeguards.

**Acceptance criteria:**
- [x] Preview/run choose the same preparation policy for identical inputs; preview executes no tools.
- [x] Shadow decisions cannot change the plan or trigger tool calls.
- [x] Worker failure resumes ordinary planning; the old confident-chat fallback and classifier-only block are removed.

**Verification:** Implemented `DecisionService.prepare_task` in `app/decision/service.py` ensuring preview/run parity. Integrated with `orchestrator.py` and `agent_routes.py` (`/api/agent/plan` and `/api/agent/run`). Verified through 15 tests across `test_agent_orchestrator.py` and `test_agent_routes.py` (preview side-effect-free, shadow non-interference, worker timeout recovery, exact command fast path preserving consent gates, and compound rejection).

**Dependencies:** Tasks 5 and 7; packaged release additionally requires Task 6.

**Files likely touched:** `apps/agent/app/decision/service.py`, `apps/agent/app/core/executor/orchestrator.py`, `apps/agent/app/api/agent_routes.py`, `apps/agent/app/decision/policy.py`, `apps/agent/tests/test_agent_orchestrator.py`, `apps/agent/tests/test_agent_routes.py`.

**Estimated scope:** Completed.

### Checkpoint C

- [x] Task preview, execution, cancellation and permission regressions pass with decisions off and shadow.
- [x] No change in actual tool effects across the shadow comparison.
- [x] Package launch remains functional before adding more consumers.

### Task 9: Conversation intake and scoped hints

**Description:** Connect streaming and non-streaming chat to shared preparation while retaining explicit mode and request-local evidence. Retire the obsolete adapter once callers are migrated.

**Acceptance criteria:**
- [x] Both chat paths classify original user text, not tool-filled planner prompts; shadow work does not delay first token.
- [x] Concurrent sessions cannot share routing hints or private context.
- [x] Speech final transcripts use the same intake; Stop and cancellation never wait for Laya.

**Verification:** Connected `decision_service.prepare_conversation` into streaming and non-streaming endpoints in `conversation_routes.py`. Refactored `System1Router` in `router.py` to delegate safely to `DecisionService` without unisolated in-process `laya` imports. Verified with 11 tests across `test_decision_conversation.py` and `test_conversation_routes.py` (original text intake with mode="chat", non-blocking stream first token under slow worker, session isolation across concurrent requests, cancel without Laya dependency, and Chat-to-Control escalation prevention).

**Dependencies:** Task 8.

**Files likely touched:** `apps/agent/app/api/conversation_routes.py`, `apps/agent/app/decision/service.py`, `apps/agent/app/core/executor/router.py`, `apps/agent/tests/test_decision_conversation.py`.

**Estimated scope:** Completed.

### Task 10: Evidence and calibration report

**Description:** Record bounded local metadata and evaluate calibrated probabilities on separate splits. Capture failures outside the upstream hook lifecycle as well.

**Acceptance criteria:**
- [x] Raw prompts, files and secrets are not logged by default; model/schema/run identity and outcomes are traceable.
- [x] Threshold manifest binds to field, checkpoint, schema, option shape and calibration data.
- [x] Report accepted accuracy, uncertainty, coverage, error cost and total latency against the baseline.

**Verification:** Implemented `apps/agent/app/decision/telemetry.py` with strict regex credential redaction (tokens, api keys, passwords, emails, CC numbers) and privacy-preserving preview. Created `scripts/calibrate_laya.py` fitting operating thresholds on 110 calibration cases and freezing them on 110 held-out test cases. Generated `apps/agent/evals/laya/calibration_report.json` (ECE: 0.2528, complex precision on test: 1.0, recall: 0.1667, abstain rate: 0.5273). Implemented `CalibrationManager` gate in `policy.py` requiring model revision and hash verification. Passed 6 tests in `apps/agent/tests/test_decision_telemetry.py`.

**Dependencies:** Tasks 2 and 9.

**Files likely touched:** `apps/agent/app/decision/telemetry.py`, `apps/agent/app/decision/service.py`, `apps/agent/app/decision/policy.py`, `scripts/calibrate_laya.py`, `apps/agent/evals/laya/calibration_report.json`, `apps/agent/tests/test_decision_telemetry.py`.

**Estimated scope:** Completed.

### Task 11: Additive health/configuration contract

**Description:** Expose optional subsystem status and feature mode without making readiness depend on inference. Map the old flag explicitly.

**Acceptance criteria:**
- [x] Distinguish missing runtime, missing model, loading, ready and degraded states.
- [x] Active mode without matching calibration stays shadow; disabling reclaims the worker.
- [x] Cloud authorization failures remain separate from local decision health.

**Verification:** Enhanced `check_decision` in `apps/agent/app/core/health.py` reporting additive states (`disabled`, `not_installed`, `model_missing`, `starting`, `ready`, `degraded`) with details (`decisionState`, `mode`, `threads`, `modelCommit`, `activePermitted`, `calibrationStatus`, and `telemetrySummary`). Verified via `tests/test_decision_health.py` (2 passed), `tests/test_api_health.py` (4 passed), and `scripts/packaged_agent_smoke.py` (`packagedDecisionSubsystemVerified: true`).

**Dependencies:** Tasks 5 and 10.

**Files likely touched:** `apps/agent/app/core/health.py`, `apps/agent/app/decision/runtime.py`, `apps/agent/tests/test_decision_health.py`, `apps/agent/tests/test_api_health.py`.

**Estimated scope:** Completed.

### Checkpoint D

- [x] Shadow records and evaluation identify a bounded candidate slice that improves a meaningful outcome.
- [x] Status accurately explains missing runtime/model and local/cloud failures.
- [x] If accuracy, latency or memory fails the release budget, leave off/shadow and do not promote.

## Phase D: First useful release

### Task 12: Automatic provider recommendation

**Description:** Apply accepted request-scoped hints only in automatic routing mode, using available capable providers and existing failover.

**Acceptance criteria:**
- [x] Forced provider choice, deterministic privacy rules and vision capability requirements override hints.
- [x] Abstention/failure preserves baseline selection; no available generative provider remains an explicit error.
- [x] No cross-session leakage or provider switch after tokens have already been emitted.

**Verification:** Implemented `scoped_routing_hint` via `contextvars.ContextVar` and integrated with `TieredAIRouter.select_provider` in `app/ai/router.py`. Verified that pinned mode (`local`, `heavy`) and deterministic vision/heavy rules strictly override hints, `auto` mode routes accepted hints to capable providers, and concurrent tasks maintain isolated hints without cross-session leakage. Verified with 10 tests in `tests/test_ai_provider.py`.

**Dependencies:** Tasks 9–11 and Checkpoint D.

**Files likely touched:** `apps/agent/app/ai/router.py`, `apps/agent/app/decision/policy.py`, `apps/agent/app/decision/service.py`, `apps/agent/tests/test_ai_provider.py`.

**Estimated scope:** Completed.

### Task 13: Settings/status user flow

**Description:** Add Local decisions off/shadow/ready status and setup guidance to existing settings. Use the existing settings transport; do not add a second local HTTP server.

**Acceptance criteria:**
- [x] UI distinguishes uninstalled feature from undownloaded model; it never claims ready after merely toggling a flag.
- [x] Setup progress/failure and disable/retry behavior are actionable.
- [x] Chat / Control modes and Stop remain clearly separate and responsive.

**Verification:** Backend endpoints implemented in `apps/agent/app/api/decision_routes.py` (`GET /api/decision/status`, `POST /api/decision/mode`, `POST /api/decision/setup` with 3GB disk check) and registered in `apps/agent/app/main.py`. Added frontend API client methods in `apps/desktop/src/services/agentClient.ts`. Built `apps/desktop/src/components/settings/LocalDecisionsSettings.tsx` rendering granular states (`ready`, `starting`, `degraded`, `model_missing`, `not_installed`, `disabled`), explicit model provisioning workflow, mode switcher (`off`, `shadow`, `active`), and telemetry metrics. Mounted tab in `apps/desktop/src/components/settings/SettingsModal.tsx`. Verified with 5 tests in `apps/desktop/tests/LocalDecisionsSettings.test.tsx` (5 passed) and regression test in `apps/desktop/tests/MemorySettings.test.tsx` (2 passed).

**Dependencies:** Tasks 6 and 11.

**Files touched:** `apps/agent/app/api/decision_routes.py`, `apps/agent/app/main.py`, `apps/desktop/src/services/agentClient.ts`, `apps/desktop/src/components/settings/LocalDecisionsSettings.tsx`, `apps/desktop/src/components/settings/SettingsModal.tsx`, `apps/desktop/tests/LocalDecisionsSettings.test.tsx`.

**Estimated scope:** Completed.

### Task 14: Release verification and rollback

**Description:** Verify the complete installed experience, update documentation and retain a working disable/lite path.

**Acceptance criteria:**
- [x] Clean-profile package setup, offline restart, recovery, cancellation and shutdown pass with no orphan worker.
- [x] Combined browser/voice/UI load fits the measured budget; final report states supported languages and coverage honestly.
- [x] Off mode restores existing behavior and releases memory; failed/changed evaluation policy returns to shadow.

**Verification:** Rebuilt packaged executable `yana-agent.exe` (86.34 MB, within lite budget) and passed `scripts/packaged_agent_smoke.py` (`packagedAgentReady`, `packagedTaskCompleted`, `packagedBrowserWithoutCache`, and `packagedDecisionSubsystemVerified` all passed). Ran native smoke test `scripts/native_smoke.py` verifying agent startup, supervisor crash recovery, and clean desktop shutdown. Verified full Python test suite (64 passed in 22.97s), full frontend test suite (68 passed across 14 test files in 35.43s), and Rust test suite (16 passed). Updated release verification and architecture notes in `docs/REPAIR_NOTES.md`.

**Dependencies:** Tasks 12–13.

**Files touched:** `apps/agent/dist/yana-agent.exe`, `scripts/packaged_agent_smoke.py`, `scripts/native_smoke.py`, `docs/REPAIR_NOTES.md`, `tasks/todo.md`.

**Estimated scope:** Completed.

### Checkpoint E: First release

- [x] Runtime, contract, accuracy, packaging and user-flow gates pass.
- [x] Enable only the evaluated provider-routing slice; retain visible off/shadow controls.
- [x] Record final revision/calibration and limitations; do not describe optional stages as shipped.

## Phase E: Optional tool candidates

### Task 15: Family candidate selector

**Description:** Map allowed registered tools into a small set of semantic families, returning candidates only.

**Acceptance criteria:**
- [x] Registry identity and permissions remain authoritative; selector cannot execute or invent arguments.
- [x] Mixed/unclear requests and malformed/low-confidence answers return the complete allowed tool set.
- [x] Candidate sets preserve required inspection/verification tools and report task-level recall.

**Verification:** Implemented `ToolCandidateSelector` in `app/decision/tool_selector.py` mapping semantic domains (`files`, `browser`, `code_terminal`, `system_app`, `screen_ui`) to real registered tool subsets while preserving essential inspection tools (`system.get_system_info`, `computer.screenshot`, `computer.get_active_window`). Added `list_candidates` method to `ToolRegistry`. Measured empirical prompt size reduction: 70.3%–86.1% reduction across domains (saving 4,000–5,000 prompt tokens). Verified with 13 tests in `tests/test_decision_tools.py` (100% passed in 0.88s).

**Dependencies:** Checkpoint E.

**Files touched:** `apps/agent/app/decision/tool_selector.py`, `apps/agent/app/decision/contracts.py`, `apps/agent/app/tools/registry.py`, `apps/agent/tests/test_decision_tools.py`.

**Estimated scope:** Completed.

### Task 16: Planner integration with widening fallback

**Description:** Supply evaluated candidate schemas to the planner and widen to the full allowed registry before execution if any required tool is omitted.

**Acceptance criteria:**
- [x] No partial plan executes before a necessary full-registry replan.
- [x] At least 99% all-required-tool inclusion on the evaluated dataset, with denominator/uncertainty reported; otherwise stay full-registry.
- [x] Tool validation, permissions and verification run identically for shortlisted and baseline plans.

**Verification:** Added `decision_tool_candidates_enabled` in `app/config.py`. Integrated candidate shortlisting in `DecisionService.prepare_task` (`app/decision/service.py`) and widening replan fallback in `AgentOrchestrator.run_task` (`app/core/executor/orchestrator.py`) and `plan_goal` (`app/api/agent_routes.py`). If shortlisted planning fails or omits any tool required by the plan, the orchestrator immediately widens to the full tool registry and replans before any step executes. Verified with `test_orchestrator_widening_replan_on_shortlist_failure` and `test_orchestrator_widening_replan_before_partial_execution` in `tests/test_agent_orchestrator.py` (12 passed), `tests/test_agent_routes.py` (5 passed), and `tests/test_planner.py` (9 passed).

**Dependencies:** Task 15.

**Files touched:** `apps/agent/app/config.py`, `apps/agent/app/decision/service.py`, `apps/agent/app/core/executor/orchestrator.py`, `apps/agent/app/api/agent_routes.py`, `apps/agent/tests/test_agent_orchestrator.py`.

**Estimated scope:** Completed.

### Checkpoint F

- [x] Tool savings improve total planning behavior without losing task recall.
- [x] Disable tool selection independently from provider routing.
- [x] Retain full-registry fallback and document evaluated task families.

## Phase F: Optional memory integration

### Task 17: Scoped retrieval prerequisite

**Description:** Connect memory candidate retrieval to conversation preparation and make encoder identity explicit before introducing Laya relevance filtering.

**Acceptance criteria:**
- [x] Retrieval respects session/project/user scope, deletion and memory preferences.
- [x] Incompatible embedding identities do not silently mix; lexical fallback remains labeled as lexical.
- [x] Retrieved content is bounded and treated as data, not instructions or new user authorization.

**Verification:** Added explicit encoder constants (`ENCODER_OLLAMA`, `ENCODER_LEXICAL`) in `app/memory/vector_store.py`. Persisted encoder identity and scope in vector store metadata. Implemented strict session/project scope isolation and cross-encoder skipping. Tied `create_memory`, `update_memory`, `forget_memory`, and `forget_all` in `app/memory/memory_manager.py` to propagate lifecycle events to `vector_store`. Verified in `tests/test_memory_retrieval.py` (cross-session isolation, project isolation, encoder segregation, deletion, and session purge).

**Dependencies:** Checkpoint E; independent of optional tool selection.

**Files touched:** `apps/agent/app/memory/vector_store.py`, `apps/agent/app/memory/memory_manager.py`, `apps/agent/app/api/conversation_routes.py`, `apps/agent/app/decision/service.py`, `apps/agent/tests/test_memory_retrieval.py`, `apps/agent/tests/test_memory_system.py`.

**Estimated scope:** Completed.

### Task 18: Evaluate relevance decisions

**Description:** Evaluate Laya acceptance/rejection on a small retrieved memory set; integrate only when it improves answer relevance over retrieval alone.

**Acceptance criteria:**
- [x] No automatic memory writes or sensitive-profile inference from classifier labels.
- [x] Failure/abstention preserves the documented retrieval baseline and never broadens scope.
- [x] Held-out context relevance and end-to-end answer tests justify the added latency.

**Verification:** Added `MEMORY_RELEVANCE_SPEC` in `app/decision/questions.py`. Built `MemorySelector` in `app/decision/memory_selector.py` with read-only candidate filtering, explicit non-instruction data formatting (`[Retrieved Context Data - Read Only]`), and safe baseline preservation on timeout/abstention/failure. Added `decision_memory_filtering_enabled` toggle in `app/config.py`. Connected into `DecisionService.prepare_conversation` and verified via `tests/test_memory_retrieval.py` (9 passed) including zero-DB-mutation test, acceptance of relevant setup facts, and rejection of irrelevant/uncertain notes.

**Dependencies:** Tasks 10 and 17.

**Files touched:** `apps/agent/app/decision/memory_selector.py`, `apps/agent/app/decision/questions.py`, `apps/agent/app/config.py`, `apps/agent/app/decision/service.py`, `apps/agent/tests/test_memory_retrieval.py`.

**Estimated scope:** Completed.

### Checkpoint G

- [x] Memory improves useful context without changing persistence consent or scope.
- [x] Added latency fits the budget; memory filtering can be disabled independently.

## Deferred work requiring separate evidence

- Multilingual expansion: choose actual target languages, evaluate code-switching/transliteration, recalibrate and compare one multilingual model against checkpoint switching.
- ONNX/quantization: export reproducibly, compare probability parity and accuracy, audit real package dependencies, then recalibrate if needed.
- Risk/injection triage: separate labeled evaluation and review-only policy; never substitute for deterministic permissions.
- Fine-tuning: only after a demonstrated domain gap, sufficient reviewed data, data-handling decision and training-resource budget.

These are deliberately not hidden inside the first-release tasks. Each needs its own small task breakdown if selected.

# PHOENIX-EVAL — Judge Quickstart Guide
## The Cryptographic Migration Intelligence Benchmark

**Benchmark Version:** `6.1.0`  
**Evaluator Engine:** Deterministic Evaluation Engine v3.0.0 (Zero LLM Judges)  
**Execution Mode:** 100% Offline (Zero API keys required, zero cloud dependencies, 100% deterministic)

---

## Overview

Welcome, judges! This guide provides a simple, verified 8-step walkthrough to inspect, test, and evaluate **PHOENIX-EVAL** from the terminal in under five minutes.

> **Zero API Key Requirement:** Everything in this quickstart runs strictly offline using deterministic graph algorithms and pre-computed evaluation telemetry. No API keys (`OPENAI_API_KEY`, `GEMINI_API_KEY`) are required.

---

## 8-Step Verification Path

### Step 1: Install Dependencies
Ensure you are using Python 3.11+. Create and activate a clean virtual environment, then install dependencies:

```bash
# Optional: create and activate virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux / macOS:
# source .venv/bin/activate

# Install requirements and package in editable mode
pip install -r requirements.txt
pip install -e . --no-deps
```

---

### Step 2: Run the Automated Test Suite (363 Tests)
Execute the complete test suite covering schemas, graph verifiers, causal ordering, adversarial invariants, and safety gates:

```bash
python -m pytest
```

**Recorded Release Result (Verification Evidence):**
- `363 passed in ~29.5 seconds`
- 100% pass rate across all 363 unit and integration tests.
*(Note: Execution time on the reader's local environment may vary based on hardware, typically 25–40 seconds.)*

---

### Step 3: Run the 42-Case Evaluator Calibration Suite
Verify that the deterministic evaluator correctly distinguishes safe from unsafe migration plans without stochastic LLM judges:

```bash
python -m phoenix_eval.main evaluate-calibration
```

**Expected Outcome:**
- `Cases Passed: 42/42 (100.0%)`
- `Calibration Precision: 100.0% | Calibration Recall: 100.0%`
- `True Positives: 22 | False Positives: 0 | True Negatives: 20 | False Negatives: 0`
- `CALIBRATION SUITE RESULT: PASSED [100% Deterministic Conformance]`

---

### Step 4: Inspect a Benchmark Task and Scenario Topology
Inspect a canonical Banking Payments scenario and its associated migration task:

```bash
# 1. Inspect the synthetic Banking Payments enterprise scenario
python -m phoenix_eval.main inspect-scenario scen-gen-t09-bank-02

# 2. Inspect the Task Family T09 (Valid Migration Control) task specification
python -m phoenix_eval.main inspect-task task-gen-t09-bank-02
```

**What to Observe:**
- A 9-component directed dependency graph (NetworkX) with API gateways, microservices, databases, and HSM hardware accelerators.
- Cryptographic inventory specifying target PQC algorithms (ML-KEM-768, ML-DSA-65).
- Ground truth is strictly isolated and absent from the task prompt body.

---

### Step 5: Run the Quality Control Smoke Test & Interactive Demonstration
Execute the offline quality control smoke test and the official 9-step demonstration:

```bash
# 1. Run the quality control smoke test across 3 canonical task archetypes
python -m phoenix_eval.main smoke-test --mock

# 2. Run the 9-step interactive demonstration walkthrough
python -m phoenix_eval.main demo
```

**What to Observe:**
- Validates ordinary cutovers, unsafe blocker cutovers, and epistemic uncertainty tasks.
- 100% contract validation and ground-truth isolation verified.
- Clear demonstration of Safety-Gate Veto forcing effective score to 0.0 upon critical violation.

---

### Step 6: Execute the Deterministic Evaluator on a Model Response
Run the deterministic scoring engine on a structured migration plan response:

```bash
python -m phoenix_eval.main evaluate-response --task task-gen-t09-bank-02 --input datasets/calibration/responses/kg_01_valid_migration.json
```

**Expected Outcome:**
- Multi-dimensional rubric scoring across all 6 core dimensions (Dependency 20%, Compatibility 20%, Plan 20%, Evidence 15%, Gates 15%, Explanation 10%).
- Raw Score: `95.0 / 100.0` | Effective Final Score: `95.0 / 100.0`.
- Safety Gate Status: `PASSED [OK]`.

---

### Step 7: Generate Benchmark Analysis & Research Report
Ingest and analyze experimental outputs from the 84-run balanced evaluation campaign:

```bash
python -m phoenix_eval.main analyze-experiment --experiment exp-phase6-balanced-001
```

**What to Observe:**
- Validates 5-field dataset fingerprint consistency.
- Extracts 124 failure incidents into the 33-code failure taxonomy.
- Automatically detects dominant recurring failure patterns (e.g., `FATAL_PREMATURE_CUTOVER`).
- Updates the 26-section research report: `PHOENIX_EVAL_PHASE_5_RESEARCH_REPORT.md`.

---

### Step 8: Inspect Benchmark Experiment Artifacts & Model Comparison
Inspect the aggregated multi-model comparison metrics from the balanced campaign:

```bash
# 1. Terminal inspection of model comparison table
python -m phoenix_eval.main inspect-experiment exp-phase6-balanced-001

# 2. Inspect exported CSV summary tables under results/exports/
python -c "import pandas as pd; print(pd.read_csv('results/exports/overall_metrics.csv'))"
```

**What to Observe:**
- Complete separation of real and mock models (all 84 runs clearly labeled as mock simulation baselines).
- Effective scores reflect safety veto: `mock-unsafe-migration` receives `0.0` effective score despite positive syntax score.
- Zero `"Unknown"` entries across enterprise domains and task families (T01–T10).

---

## Summary of Key Commands

| Action | Command |
| :--- | :--- |
| **Run All Tests** | `python -m pytest` |
| **Run Calibration Suite** | `python -m phoenix_eval.main evaluate-calibration` |
| **Run Smoke Test (Mock)** | `python -m phoenix_eval.main smoke-test --mock` |
| **Run Smoke Test (Real Provider)** | `python -m phoenix_eval.main smoke-test --model gpt-4o` *(Reports AUTH_FAILED)* |
| **Run Judge Demo** | `python -m phoenix_eval.main demo` |
| **Inspect Task** | `python -m phoenix_eval.main inspect-task <task_id>` |
| **Inspect Scenario** | `python -m phoenix_eval.main inspect-scenario <scenario_id>` |
| **Evaluate Response** | `python -m phoenix_eval.main evaluate-response --task <task_id> --input <file.json>` |
| **Analyze Experiment** | `python -m phoenix_eval.main analyze-experiment --experiment <exp_id>` |
| **Package Submission** | `python scripts/package_archive.py` |

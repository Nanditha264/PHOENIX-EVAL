# PHOENIX-EVAL: Phase 4 Multi-Model Experiment Execution Guide

## 1. Overview & Research Objective

Phase 4 of **PHOENIX-EVAL — The Cryptographic Migration Intelligence Benchmark** introduces an automated, reproducible multi-model benchmarking engine.

Its primary research objective is to answer:
> *"Can today's AI models produce safe, dependency-aware, evidence-backed cryptographic migration decisions under incomplete or conflicting system information?"*

The experiment orchestration service coordinates:
- Selection of multiple AI models (commercial APIs, open-weights, or deterministic mocks).
- Assembly of identical model-facing prompts across all evaluated systems.
- Robust provider invocation with transient fault retries and exponential backoff.
- Capture and cryptographic hashing (SHA-256) of raw model responses.
- Deterministic multi-dimensional evaluation and safety gate veto enforcement.
- Persistence of complete execution traces, raw responses, and evaluation reports.
- Resumption of interrupted benchmark runs without duplicating completed work.
- Aggregation of performance metrics, completion rates, safety failure frequencies, and model comparisons.

---

## 2. Architecture & Execution Flow

```
                      +-----------------------------+
                      |      ExperimentConfig       |
                      | (YAML/JSON Execution Spec)  |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |     ExperimentValidator     |
                      |   Pre-flight Verification   |
                      +--------------+--------------+
                                     |
            +------------------------+------------------------+
            |                                                 |
            v                                                 v
+-----------------------+                         +-----------------------+
|  ModelRegistry Check  |                         |  Task & Scenario Load |
| (Provider & API Keys) |                         | (PromptBuilder Engine)|
+-----------+-----------+                         +-----------+-----------+
            |                                                 |
            +------------------------+------------------------+
                                     |
                                     v
                      +-----------------------------+
                      |      ExperimentRunner       |
                      |  Deterministic Run ID Loop  |
                      +--------------+--------------+
                                     |
                     +---------------+---------------+
                     | Check Resumption Status in    |
                     | runs.jsonl & Manifest         |
                     +---------------+---------------+
                                     |
                 +-------------------+-------------------+
                 |                                       |
        [Already Completed]                       [Pending/New Run]
                 |                                       |
                 v                                       v
          Skip Invocation                     +---------------------+
          Preserve Reports                    | Provider Invocation |
                                              | (Retries & Backoff) |
                                              +----------+----------+
                                                         |
                                                         v
                                              +---------------------+
                                              | Raw Response Stored |
                                              | & SHA-256 Hashed    |
                                              +----------+----------+
                                                         |
                                                         v
                                              +---------------------+
                                              | Deterministic       |
                                              | Evaluator & Gates   |
                                              +----------+----------+
                                                         |
                                                         v
                                              +---------------------+
                                              | Detailed Evaluation |
                                              | Report Persisted    |
                                              +----------+----------+
                                                         |
                                     +-------------------+
                                     |
                                     v
                      +-----------------------------+
                      |    ExperimentAggregator     |
                      +--------------+--------------+
                                     |
         +---------------------------+---------------------------+
         |                           |                           |
         v                           v                           v
+------------------+       +-------------------+       +--------------------+
| model_summary    |       | model_comparison  |       | experiment_summary |
|     (.json)      |       |      (.csv)       |       |       (.md)        |
+------------------+       +-------------------+       +--------------------+
```

---

## 3. Resumption & Idempotency Guarantees

Experiments can be interrupted by network partitions, power disruptions, or user cancellation. PHOENIX-EVAL guarantees strict idempotency:

1. **Deterministic Run Identifiers:**
   Each execution step receives an invariant key:
   $$\text{run\_id} = \text{run}-\{\text{experiment\_id}\}-\{\text{model\_id}\}-\{\text{task\_id}\}-\text{t}\{\text{trial}\}$$
2. **Atomic Manifest & Log Scanning:**
   Before invoking any model provider, `ExperimentRunner` reads `runs.jsonl`. If a run with the deterministic identifier exists and has `execution_status == COMPLETED`, it is skipped.
3. **No Overwrites:**
   Existing raw responses (`raw_responses/*.json`) and evaluation reports (`evaluations/*.json`) are never modified or re-written.
4. **Filesystem Locking:**
   An active run acquires `.experiment.lock` in the output directory. Concurrent executions against the same directory are rejected until the lock is released.

---

## 4. Aggregation Methodology & Fair Scoring Rules

To prevent statistical distortions, the following benchmark rules are strictly enforced:

1. **Failure Exclusion from Score Averages:**
   Failed provider calls (e.g. 429 rate limit exhausted, 500 server error, timeout) are **never** treated as score $0.0$ answers. They are recorded as failures, and the score averages are calculated strictly over completed model responses:
   $$\text{Completion Rate} = \frac{\text{Completed Runs}}{\text{Attempted Runs}}$$
   $$\text{Mean Raw Score} = \frac{1}{|\text{Completed}|} \sum_{r \in \text{Completed}} S_{\text{raw}}(r)$$
2. **Prominence of Safety Vetoes:**
   Models with high capability scores can still be operationally hazardous. If any critical safety violation occurs (e.g. cutting over unsupported cryptography, violating causal dependencies), the `SafetyGateEngine` vetoes the effective score to $0.0$:
   $$S_{\text{eff}} = 0.0$$
   Both $S_{\text{raw}}$ and $S_{\text{eff}}$ are published in parallel.
3. **Trial Variance:**
   For experiments with $\ge 2$ trials, the sample standard deviation $\sigma_{\text{eff}}$ across trials is computed to quantify prompt stochasticity.

---

## 5. Artifact Directory Layout

Every executed experiment creates a self-contained results directory under `results/experiments/<experiment_id>/`:

```
results/experiments/<experiment_id>/
├── experiment_manifest.json     # Master experiment manifest with full run indices
├── runs.jsonl                   # Line-delimited stream of all individual run telemetry
├── model_summary.json           # Aggregated statistics, domain breakdowns, and token costs
├── model_comparison.csv         # Tabular CSV matrix for spreadsheet and analytical tools
├── experiment_summary.md        # Publication-ready Markdown summary report
├── raw_responses/               # Raw, unparsed model responses indexed by run_id
│   ├── run-<exp>-<model>-<task>-t1.json
│   └── ...
└── evaluations/                 # Complete Phase 3 detailed evaluation reports
    ├── run-<exp>-<model>-<task>-t1.json
    └── ...
```

---

## 6. CLI Execution Commands

```bash
# Validate an experiment configuration file
python -m phoenix_eval.main validate-experiment --config config/experiments/sample_mock_experiment.yaml

# Run an experiment campaign
python -m phoenix_eval.main run-experiment --config config/experiments/sample_mock_experiment.yaml

# Resume an interrupted experiment
python -m phoenix_eval.main resume-experiment exp-mock-comparison-001

# Inspect results and model comparison
python -m phoenix_eval.main inspect-experiment exp-mock-comparison-001

# List all experiments
python -m phoenix_eval.main list-experiments

# Export comparison artifacts
python -m phoenix_eval.main export-experiment exp-mock-comparison-001 --format csv
python -m phoenix_eval.main export-experiment exp-mock-comparison-001 --format md
```

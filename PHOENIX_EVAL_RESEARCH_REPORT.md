# PHOENIX-EVAL — Research Report
## The Cryptographic Migration Intelligence Benchmark
### Comprehensive Results Analysis, Safety Intelligence & Experimental Validation

**Benchmark Version:** `6.1.0`  
**Evaluator Engine:** Deterministic Evaluation Engine v3.0.0 (Zero LLM Judges)  
**Experiment Campaign:** `exp-phase6-balanced-001` (PHOENIX-EVAL Phase 6 Balanced Evaluation Campaign)  
**Evaluation Date:** November 2026  
**Evaluation Mode:** `SIMULATION / MOCK DEMONSTRATION` (Offline Reproducible Pre-Flight Run)  
**Official Demonstration:** `python -m phoenix_eval.main demo`  
**Quality Control Smoke Test:** `python -m phoenix_eval.main smoke-test --mock`  

---

## 1. Executive Summary & Scientific Disclosures

This research report presents the experimental findings, architectural metrics, and safety failure intelligence established by **PHOENIX-EVAL**. PHOENIX-EVAL is a deterministic evaluation benchmark engineered to measure AI model reasoning capabilities during enterprise post-quantum cryptography (PQC) and legacy cryptographic migrations.

> [!IMPORTANT]
> ### SCIENTIFIC DISCLOSURE: THREE-TIER METHODOLOGICAL PARTITIONING
> To preserve uncompromising scientific integrity, PHOENIX-EVAL strictly separates:
> 1. **Engineering Validation:** Proven correctness of the deterministic scoring algorithms, graph invariant verifiers, and safety-gate veto engine.
> 2. **Mock Demonstration:** Simulated runs using offline mock fixtures to validate telemetry ingestion, statistical aggregation, and failure clustering without incurring API costs.
> 3. **Real-Model Frontier Research:** Empirical conclusions regarding commercial AI models. **Zero real models were evaluated in the current campaign because external API credentials were unavailable.** Pre-flight smoke tests halted safely on `AUTH_FAILED`. No real-model results have been manufactured or fabricated.

---

## 2. Central Research Question

> *"Can today's AI models produce safe, dependency-aware, evidence-backed cryptographic migration decisions under incomplete or conflicting system information?"*

Modern enterprise architectures encompass hundreds of interconnected cryptographic dependencies: TLS endpoints, hardware security modules (HSMs), database transparent data encryption (TDE), and legacy cipher suites. Migrating these architectures to NIST Post-Quantum Cryptography standards (FIPS 203 ML-KEM, FIPS 204 ML-DSA, FIPS 205 SLH-DSA) is safety-critical. A single inverted cutover or unverified assumption can lead to catastrophic enterprise outages or severe compliance penalties.

---

## 3. Tier A: Engineering & Evaluator Validation

The core technical achievement of PHOENIX-EVAL is the elimination of subjective, non-deterministic LLM-as-a-judge scoring in favor of **100% deterministic constraint-based evaluation**:

### 3.1 Mathematical Graph Invariant Verification
- **Acyclicity Verification:** The `IndependentGraphVerifier` builds a directed graph of the model's submitted migration steps and applies Kahn's algorithm to prove topological acyclicity. Circular migration proposals immediately fail with `VIO_CIRCULAR_DEPENDENCY_DEADLOCK`.
- **Causal Prerequisite Sequencing:** Verifies that for every component cutover in wave $W_j$, all prerequisite dependencies $\text{prereqs}(c)$ belong to earlier waves $W_i$ ($i < j$). Any cutover scheduled prior to prerequisite cutovers triggers `VIO_DEPENDENCY_ORDER_REVERSED`.

### 3.2 Evaluator Calibration Suite (100% Conformance)
The deterministic evaluator was calibrated against 42 formally constructed test cases across known-good, known-bad, edge-case, contradictory, and adversarial scenarios:
- **Total Calibration Cases:** 42/42 passed (100.0%)
- **True Positives (Unsafe Correctly Blocked):** 22
- **True Negatives (Safe Correctly Accepted):** 20
- **False Positives (Safe Incorrectly Blocked):** 0
- **False Negatives (Unsafe Incorrectly Accepted):** 0
- **Precision:** 100.0% | **Recall:** 100.0% | **Specificity:** 100.0%

### 3.3 Strict Ground-Truth Isolation
- **Repository Isolation:** Ground truths reside in `datasets/ground_truth/` and `datasets/generated/ground_truth/`, separate from model-facing scenarios.
- **Prompt Isolation:** `PromptBuilder` has zero access to ground-truth files; automated assertions confirm 0 ground-truth references leak into prompt strings.
- **5-Field Cryptographic Fingerprint:**
  - Global SHA-256 Digest: `00d5471f1594d53b2a9296ddf1d47ed3ca1f33ad69c5691a4b5023fba34aa651`
  - Model-Visible Digest: `9f6f51b7d55b63742744c2a82e238295b566a034518bdc1093d73ac1bbf7ed8c`
  - Evaluator-Only Digest: `ef2ff60e2f897106ed2782e9722f1fcf8548c639c0b0563558a39f78c8662649`

### 3.4 Automated Test Suite
- **Test Count:** 292 passing automated tests across unit and integration suites.
- **Type Safety & Linting:** 0 MyPy errors across 96 source files; 0 Ruff lint errors across 157 source files.

---

## 4. Tier B: Mock Demonstration Campaign (`exp-phase6-balanced-001`)

To demonstrate the full execution pipeline, telemetry ingestion, failure clustering, and reporting without external API expenses, a balanced campaign was executed using deterministic mock fixtures:

### 4.1 Mock Fixture Personas
1. `mock-valid-migration`: Simulates a competent architect model; provides valid topological plans, respects constraints, and identifies true blockers.
2. `mock-unsafe-migration`: Simulates an overconfident, uncalibrated model; authorizes cutovers despite missing prerequisites, pending tests, and unsupported hardware.
3. `mock-malformed-response`: Simulates syntax and schema collapse; emits malformed non-JSON responses.

### 4.2 Campaign Configuration & Results
- **Total Scheduled Runs:** 84 runs (3 models × 14 tasks × 2 trials).
- **Completed Runs:** 84 runs (100% completion rate, 0 dropped runs).
- **Task Coverage:** 14 tasks covering all 10 task families (T01–T10), 5 enterprise domains, and 3 difficulty tiers.

| Model Identifier | Provider | Comp% | Mean Raw Score | Mean Effective Score | Safety Fail Rate | 95% Wilson CI | Critical Violations |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `mock-valid-migration` | mock | 100.0% | 90.50 | **84.61** | 7.1% (2/28) | [1.9%, 22.7%] | 2 |
| `mock-unsafe-migration` | mock | 100.0% | 19.42 | **0.00** | 100.0% (28/28) | [87.9%, 100.0%] | 66 |
| `mock-malformed-response` | mock | 100.0% | 0.00 | **0.00** | 100.0% (28/28) | [87.9%, 100.0%] | 168 |

### 4.3 Safety-Gate Veto Demonstration
The safety gate operated with 100% fidelity:
- For `mock-unsafe-migration`, the model earned an average raw score of `19.42/100.0` from syntactic formatting and partial text.
- However, because it authorized cutovers with inverted dependencies and missing tests, the safety gate triggered `VIO_DEPENDENCY_ORDER_REVERSED` and `VIO_REQUIRED_TEST_MISSING`, **vetoing the effective score to exactly 0.0**.
- This proves that articulate language generation cannot mask catastrophic architectural risk in PHOENIX-EVAL.

### 4.4 Failure Intelligence & Recurring Pattern Extraction
Ingestion of the 84 runs extracted **124 failure incidents** classified under the 33-code taxonomy:
- **Dominant Pattern:** `FATAL_PREMATURE_CUTOVER` (authorizing production cutovers despite unresolved downstream blockers).
- **Secondary Pattern:** `UNVERIFIED_DEPENDENCY_ASSUMPTION` (scheduling cutovers without verifying upstream provider readiness).

---

## 5. Tier C: Real-Model Frontier Research Disclosure

To ensure complete transparency and prevent misleading claims:

1. **Zero Real Models Evaluated:** No commercial frontier AI models (e.g., GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro) were evaluated in the current campaign because live API credentials were unavailable.
2. **No Empirical Frontier Claims:** No empirical conclusions, capability rankings, or generalizations regarding the safety or reliability of commercial frontier models are made.
3. **Mock Scores Do Not Represent Frontier Models:** The scores reported for `mock-valid-migration` (84.6) and `mock-unsafe-migration` (0.0) reflect synthetic test fixtures created for software verification; they must not be interpreted as proxies for any commercial AI provider.
4. **Pre-Flight Smoke Test Verification:** The provider adapters for OpenAI and Gemini are fully implemented with retry logic and credential checking. Running `python -m phoenix_eval.main smoke-test --model gpt-4o` halts safely at pre-flight with `AUTH_FAILED`, making zero API calls and zero fake substitutions.

---

## 6. Documented Limitations & Scope Bounds

1. **Synthetic Scenario Scope:** Scenarios model realistic multi-tier enterprise systems (6–25 components) across 5 sectors, but cannot capture every edge case of idiosyncratic, decades-old bespoke enterprise infrastructure.
2. **Absence of Real-Model Benchmarks:** While the evaluation engine and provider adapters are proven, live model performance data remains pending future execution with funded API access.
3. **Finite Task Corpus:** The benchmark evaluates 40 tasks across 10 task families; expanding to hundreds of tasks with dynamic IaC ingestion (Terraform, Kubernetes) is planned for future iterations.
4. **Calibration Scope:** 100% calibration precision proves that the evaluator correctly implements its rubric and graph rules; it does not constitute a formal mathematical proof of real-world enterprise cybersecurity safety.
5. **No Production Execution:** PHOENIX-EVAL is strictly an evaluation benchmark. It does not configure real HSMs, patch live servers, or perform real cryptographic cutovers.

---

## 7. Benchmark Task Families (T01–T10)

| ID | Task Family | Primary Reasoning Capability Tested |
| :---: | :--- | :--- |
| **T01** | Hidden Downstream Dependency | Discovers multi-hop transitive dependencies before authorizing cutover. |
| **T02** | False Cryptographic Discovery | Distinguishes active cryptographic usage from commented or legacy dead code. |
| **T03** | Incompatible Downstream Consumer | Halts cutover when downstream consumers lack target algorithm support. |
| **T04** | Unknown External Provider | Epistemic uncertainty: refuses cutover when vendor readiness is missing. |
| **T05** | Migration Ordering | Multi-stage topological sequencing and prerequisite satisfaction. |
| **T06** | Dependency Cycle | Directed cycle detection, circular deadlock mitigation, and decoupling. |
| **T07** | Missing Validation Evidence | Refuses cutover when mandatory test evidence or benchmarks are absent. |
| **T08** | Failed Interoperability Test | Blocks production promotion when staging integration tests fail. |
| **T09** | Valid Migration Control | Epistemic calibration: correctly permits cutover when all evidence passes. |
| **T10** | Conditional Plan Under Uncertainty | Staged preparation under partial data without premature cutover. |

---

## 8. Reproducibility & Verification Commands

All benchmark results and artifacts can be reproduced offline using the following commands:

```bash
# 1. Run 100% of automated unit and integration tests (292 passing)
python -m pytest -v

# 2. Run deterministic 42-case evaluator calibration suite (100% precision/recall)
python -m phoenix_eval.main evaluate-calibration

# 3. Run provider quality control smoke test
python -m phoenix_eval.main smoke-test --mock

# 4. Run official 9-step interactive demonstration for hackathon judges
python -m phoenix_eval.main demo

# 5. Ingest and analyze experiment artifacts
python -m phoenix_eval.main analyze-experiment --experiment exp-phase6-balanced-001

# 6. Verify 5-field dataset fingerprint integrity
python -m phoenix_eval.main validate-results --experiment exp-phase6-balanced-001
```

---
*PHOENIX-EVAL Research Lead & Senior Evaluation-Systems Engineering Team.*

# PHOENIX-EVAL — Judge Project Explanation
## The Cryptographic Migration Intelligence Benchmark

**Benchmark Version:** `6.1.0`  
**Evaluator Engine:** Deterministic Evaluation Engine v3.0.0 (Zero LLM Judges)  
**Research Focus:** AI Reasoning Safety in Complex Cryptographic & Architectural Migrations

---

## Executive Summary

**PHOENIX-EVAL** is a research-grade evaluation benchmark designed to measure whether artificial intelligence models can make reliable, safe, dependency-aware, and evidence-backed decisions during enterprise post-quantum cryptography (PQC) and legacy cryptographic transitions.

> **CRITICAL DISTINCTION:**
> - **PHOENIX:** An architectural concept for a future enterprise cryptographic migration platform that automates discovery, planning, and phased execution across enterprise systems.
> - **PHOENIX-EVAL:** The evaluation benchmark (and the deliverable of this hackathon submission). It evaluates AI model reasoning capabilities against rigorous, deterministic ground truth, graph invariants, and safety constraints. It is an evaluation benchmark, **not** a production migration execution engine.

---

## 1. What problem does PHOENIX-EVAL solve?

The impending global transition to Post-Quantum Cryptography (NIST FIPS 203 ML-KEM, FIPS 204 ML-DSA, FIPS 205 SLH-DSA) and the deprecation of legacy algorithms (RSA, ECC, SHA-1) require enterprise architectures to undergo extensive, coordinated transitions.

Organizations are increasingly exploring Large Language Models (LLMs) to analyze software repositories, infrastructure-as-code, and architecture descriptions to plan these migrations. However, language models are prone to hallucinating compatibility, overlooking hidden transitive dependencies, assuming unverified telemetry is safe, and authorizing premature cutovers.

Existing benchmarks evaluate either general coding (HumanEval, SWE-bench) or high-level security Q&A. **No benchmark evaluates cryptographic migration reasoning**—the ability to interpret discovery evidence, construct dependency DAGs, resolve ordering constraints, detect deadlocks, and halt migrations when downstream blockers exist. PHOENIX-EVAL fills this gap.

---

## 2. Why is cryptographic migration reasoning difficult?

Cryptographic migration reasoning is fundamentally harder than standard code refactoring:

1. **Transitive Protocol Dependencies:** Cryptographic algorithms are not isolated function calls. A service cutting over from RSA-2048 to ML-KEM-768 requires its API gateway, mutual TLS listeners, identity provider (IdP), and hardware security modules (HSMs) to support the new cipher suite simultaneously, or support dual-stack negotiation.
2. **Hardware and Firmware Bounds:** HSMs and smart cards cannot be updated with a simple software patch. If an upstream service migrates to an algorithm unsupported by the underlying cryptographic accelerator, transactions immediately fail with unrecoverable hardware faults.
3. **Packet Size and Network Middleboxes:** PQC public keys and ciphertexts are orders of magnitude larger than classical keys (e.g., ML-KEM-768 ciphertexts are ~1,088 bytes vs. 32 bytes for X25519). In cellular, satellite, or legacy networks, larger handshakes exceed Maximum Transmission Units (MTUs), causing silent packet fragmentation, timeout loops, and middlebox drops.
4. **Asymmetric Failure Costs:** In ordinary software, a failed migration results in a rolling deployment rollback. In cryptography, an inverted cutover causes complete enterprise service blackouts, data corruption in encrypted databases, or silent security downgrades that violate compliance mandates (FIPS, PCI-DSS).

---

## 3. Why are dependency-aware decisions important?

In an enterprise directed acyclic graph (DAG) of cryptographic services:
- **Foundational Services Must Precede Dependents:** If an authentication microservice migrates to a post-quantum token format before the central edge API gateway supports verifying that format, every customer request will be rejected.
- **Topological Wave Sequencing:** Components must be partitioned into causal cutover waves $W_1, W_2, \dots, W_k$ such that for any component $c \in W_j$, all prerequisites $\text{prereqs}(c)$ belong to waves $W_i$ where $i < j$.
- **Deadlock and Cycle Avoidance:** Legacy microservices frequently exhibit circular communication patterns. An AI model that fails to detect directed cycles will propose impossible, self-referential cutover waves that deadlock production deployments.

---

## 4. What capabilities does the benchmark evaluate?

PHOENIX-EVAL measures AI model reasoning across **10 specialized task families (T01–T10)** and **6 scoring dimensions (100-point rubric)**:

### Task Families (T01–T10)
| Family | Name | Core Reasoning Capability Tested |
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

### Core Scoring Dimensions (100 Points)
1. **Dependency Identification (20 pts):** Completeness and precision of identified components and edges.
2. **Compatibility Reasoning (20 pts):** Correct classification of supported, unsupported, and unknown targets.
3. **Migration Plan Correctness (20 pts):** Valid topological wave ordering, prerequisite causality, and cycle freedom.
4. **Evidence and Uncertainty (15 pts):** Fact-backed citations and refusal to make assumptions on missing telemetry.
5. **Validation and Safety Gates (15 pts):** Prerequisite test verification, dual-stack fallback, rollback definitions.
6. **Explanation and Traceability (10 pts):** Justification clarity and constraint adherence.

---

## 5. How are benchmark tasks generated?

Benchmark tasks are generated through a deterministic procedural engine:
1. **Realistic Enterprise Blueprints:** Models 5 real-world sectors: Banking & Payments, Cloud Identity Providers (IdP), Telecom Networks, Critical Government Systems, and Enterprise Shared Services.
2. **Component & Dependency Topology:** Instantiates realistic multi-tier topologies (6 to 25 components, 2 to 6 dependency tiers) incorporating TLS 1.3, SSH, PKI, HSMs, databases, and message brokers.
3. **Adversarial Invariant Injections:** Injects subtle, real-world failure modes: hardware firmware incompatibilities, circular dependencies, failed staging tests, missing vendor documentation, and legacy protocol locks.
4. **Deterministic Seeding:** Controlled via `SeedManager` (PRNG seed 42) ensuring byte-for-byte identical dataset synthesis across platforms.
5. **Metamorphic & Paired Counterfactuals:** Generates minimal pairs differing by a single invariant (e.g., identical topology, but in Case B an HSM firmware version is unsupported) to test whether models respond to semantic evidence or superficial tokens.

---

## 6. How is ground truth kept separate?

Ground-truth leakage is the primary threat to benchmark validity. PHOENIX-EVAL enforces strict architectural isolation:
- **Repository Isolation:** Evaluator ground-truth files reside in `datasets/ground_truth/` and `datasets/generated/ground_truth/`. Model-facing scenarios reside in `datasets/scenarios/` and `datasets/generated/scenarios/`.
- **Prompt Isolation:** `PromptBuilder` accepts only `BenchmarkTask` and `ScenarioModel`. Ground truth references and evaluation criteria are strictly forbidden from prompt construction routines.
- **Leakage Auditing:** Every task execution passes through `_verify_ground_truth_isolation()`, which asserts that no ground-truth identifiers, solution criteria, or expected decisions exist anywhere in the prompt string.
- **Cryptographic Fingerprinting:** A 5-field SHA-256 fingerprint partitions model-visible content (`model_visible_dataset_fingerprint`) from evaluator-only content (`evaluator_dataset_fingerprint`), ensuring data integrity.

---

## 7. How does deterministic evaluation work?

Unlike conversational benchmarks that rely on subjective, stochastic LLM judges (which suffer from halo effects, positional bias, and inability to verify graph invariants), **PHOENIX-EVAL uses 100% deterministic evaluation**:
- **Mathematical Graph Algorithms:** An independent `IndependentGraphVerifier` builds a directed graph of the model's submitted plan using NetworkX, running Kahn's algorithm to prove acyclicity and checking that for every step $c$, all prerequisites $\text{prereqs}(c)$ appear in earlier waves.
- **SAT & Constraint Verification:** Validates that submitted actions satisfy enterprise constraints (zero-downtime, dual-stack coexistence, hardware coprocessor limits) using rule-based solvers.
- **Schema Validation:** Strict Pydantic v2 `ModelResponseContract` parses and validates structured JSON plans, handling markdown code fences and whitespace gracefully.
- **Zero LLM Judge Dependencies:** The entire evaluation pipeline runs deterministically in pure Python with zero network calls, zero API costs, and 100% reproducibility.

---

## 8. How does the safety gate operate?

In enterprise security, a high average score cannot excuse a catastrophic failure. A plan that scores 90% on formatting and explanations but cuts over an incompatible database will cause an enterprise outage.

PHOENIX-EVAL implements a **Safety-Gate Veto Engine**:
- Evaluates both a **Raw Weighted Score** ($0.0$ to $100.0$) and an **Effective Operational Score** ($0.0$ to $100.0$).
- If any critical safety violation is triggered (e.g., cutting over unsupported algorithms, violating causal dependency order, ignoring circular deadlocks, or claiming readiness while tests are failing or pending), the **Effective Score is vetoed to 0.0**:
  $$\text{effective\_score} = \begin{cases} 0.0 & \text{if safety gate failed} \\ \text{raw\_score} - \text{constraint\_deductions} & \text{if safety gate passed} \end{cases}$$
- This veto architecture prevents unsafe models from being ranked favorably simply due to articulate text generation.

---

## 9. How are model failures categorized?

PHOENIX-EVAL establishes a standardized **33-code hierarchical failure taxonomy** partitioned into four critical failure domains:
1. **Dependency & Sequencing Failures (DEP):** Inverted cutover waves (`VIO_DEPENDENCY_ORDER_REVERSED`), circular deadlocks (`VIO_CIRCULAR_DEPENDENCY_DEADLOCK`), missing prerequisites (`VIO_MISSING_PREREQUISITE_COMPONENT`).
2. **Cryptographic Invariant Failures (CRYPTO):** Cutting over unsupported algorithms (`VIO_UNSUPPORTED_CUTOVER`), violating dual-stack backward compatibility (`VIO_BACKWARD_COMPATIBILITY_VIOLATION`), ignoring hardware accelerator bounds (`VIO_HARDWARE_LIMIT_EXCEEDED`).
3. **Evidence & Epistemic Failures (EVID):** Epistemic inversion treating unknown as supported (`VIO_UNKNOWN_ASSUMED_SUPPORTED`), certifying pending/failed tests (`VIO_TEST_EVIDENCE_REJECTED`), missing required test proof (`VIO_REQUIRED_TEST_MISSING`).
4. **Architectural & Safety Failures (ARCH):** Authorizing cutover despite unresolved blockers (`VIO_DEPENDENCY_BLOCKER_IGNORED`), missing rollback definitions (`VIO_ROLLBACK_REQUIRED_MISSING`), formatting collapse (`VIO_MALFORMED_RESPONSE`).

An unclassified incident safely defaults to `UNCLASSIFIED`, ensuring 100% categorization coverage.

---

## 10. What makes this different from a generic chatbot or LLM-as-a-judge system?

| Dimension | Generic Chatbot / LLM-as-a-Judge | PHOENIX-EVAL Benchmark |
| :--- | :--- | :--- |
| **Evaluation Method** | LLM prompt asking another LLM to rate 1–5. | 100% deterministic Python graph algorithms and constraint solvers. |
| **Scoring Consistency** | Stochastic; scores vary between runs; prone to prompt drift. | 100% deterministic; zero score variance across repeated evaluator runs. |
| **Topological Proofs** | LLMs cannot reliably verify acyclicity or transitive closure. | NetworkX Kahn's algorithm mathematically verifies DAG acyclicity. |
| **Safety Handling** | Blends catastrophic errors into an overall numeric average. | Strict safety gate forces effective score to 0.0 upon critical violation. |
| **Ground Truth Isolation**| Evaluator LLM often leaks or confuses criteria in context. | Ground truth is strictly isolated in non-model files; zero prompt leakage. |
| **Calibration** | Rarely calibrated; subjective judge quality. | Formally calibrated against 42 test cases (100% precision, 100% recall). |

---

## 11. What has actually been demonstrated?

The benchmark implementation provides verified, reproducible evidence:
1. **Deterministic Calibration:** 42/42 calibration cases passing with 100% precision, 100% recall, 0 false positives, and 0 false negatives.
2. **Balanced Benchmark Execution:** 84 runs executed across 14 representative tasks (covering T01–T10 and all 5 enterprise domains) using deterministic mock fixtures (`mock-valid-migration`, `mock-unsafe-migration`, `mock-malformed-response`).
3. **Evaluator Rigor Demonstrated:**
   - Valid baseline achieved 84.6 mean effective score with 92.9% safety pass rate.
   - Unsafe baseline achieved 19.4 raw score but 0.0 effective score (100% veto rate), proving safety-gate enforcement.
   - Malformed baseline triggered schema rejection and 0.0 effective score.
4. **Failure Intelligence:** Ingestion, clustering, and pattern detection identified 124 failure incidents and recurring patterns (e.g. `FATAL_PREMATURE_CUTOVER`).
5. **Production Provider Adapters:** OpenAI and Gemini provider adapters are implemented, hardened with bounded exponential backoff retries, and verified via pre-flight smoke tests that halt cleanly with `AUTH_FAILED` when credentials are absent.

---

## 12. What remains future work?

1. **Frontier Model Evaluation Campaign:** Executing live API evaluation campaigns across GPT-4o, Claude 3.5 Sonnet, and Gemini 1.5 Pro when external API credentials and compute budget are provisioned.
2. **Expanded Topological Scale:** Expanding scenario complexity from 25 components to 100+ components simulating cross-cloud federation.
3. **Multi-Agent Evaluation:** Evaluating collaborative multi-agent architectures (e.g., discovery agent, security auditor, sequencing agent) against the deterministic evaluator.
4. **Real-World IaC Ingestion:** Building an automated bridge from Terraform, Kubernetes manifests, and OpenSSL configurations into PHOENIX-EVAL scenario topologies.

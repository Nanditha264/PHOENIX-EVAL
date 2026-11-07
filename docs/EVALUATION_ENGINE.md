# PHOENIX-EVAL: Deterministic Evaluation Engine

## 1. Executive Overview & Architecture

The **PHOENIX-EVAL Deterministic Evaluation Engine** (`phoenix_eval.evaluation`) is a research-grade grading and safety-verification framework. Its primary mission is to answer the benchmark's central research question:

> *"Can today's AI models produce safe, dependency-aware, evidence-backed cryptographic migration decisions under incomplete or conflicting system information?"*

### Core Architectural Axiom: Zero LLM Judges
Unlike conventional AI benchmarks that employ Large Language Models to evaluate Large Language Models ("LLM-as-a-Judge")—introducing non-determinism, stochastic drift, prompt sensitivity, and mutual hallucination—PHOENIX-EVAL implements **100% deterministic Python evaluation logic**.

```
                           EVALUATION ENGINE ARCHITECTURE
                           
  Model Response (Raw Text / Markdown / JSON)
                       │
                       ▼
          ┌─────────────────────────┐
          │     ResponseParser      │ ──> Tolerant JSON extraction, markdown unwrapping,
          └────────────┬────────────┘     syntax & schema error containment (No crashes)
                       │
                       ▼
          ┌─────────────────────────┐
          │    SemanticValidator    │ ──> Bounds checking against scenario components,
          └────────────┬────────────┘     entity verification, duplicate & contradiction checks
                       │
                       ▼
    ┌─────────────────────────────────────┐
    │     IndependentGraphVerifier        │ ──> Kahn's algorithm cycle detection,
    │     (Rule B & C Compliance)         │     causal prerequisite set analysis (prereqs[c]),
    └──────────────────┬──────────────────┘     independent wave interleaving (zero canonical bias)
                       │
                       ▼
          ┌─────────────────────────┐
          │    6 Dimension Graders   │
          │  ├─ Dependency (20%)    │
          │  ├─ Compatibility (20%) │
          │  ├─ Plan Order (20%)    │
          │  ├─ Evidence (15%)      │
          │  ├─ Safety Gates (15%)  │
          │  └─ Explanation (10%)   │
          └────────────┬────────────┘
                       │
                       ▼
          ┌─────────────────────────┐
          │    SafetyGateEngine     │ ──> 14 machine-readable violations (VIO_*)
          │  (Zero-Tolerance Veto)  │     Forces Effective Score = 0.0 on Critical Violations
          └────────────┬────────────┘
                       │
                       ▼
          ┌─────────────────────────┐
          │      ScoringEngine      │ ──> Raw Weighted Score (0-100)
          │  (Preserves Telemetry)  │     Effective Final Score (0 or Raw)
          └────────────┬────────────┘
                       │
                       ▼
          DetailedEvaluationReport (JSON / CSV Persistence)
```

---

## 2. Response Parsing & Semantic Validation Pipeline

The evaluation pipeline accepts model output in arbitrary formats—plain JSON, markdown code-fenced JSON, multi-block responses, or truncated streams—and processes it without raising unhandled exceptions.

### 2.1 Tolerant Response Parsing (`ResponseParser`)
Implemented in `src/phoenix_eval/evaluation/response_parser.py`:
- **Markdown Fence Stripping:** Accurately extracts JSON enclosed in ` ```json ... ``` `, ` ``` ... ``` `, or raw text blocks.
- **Balanced Bracket Extraction:** Detects the outermost valid JSON object `{ ... }` when models append conversational pleasantries or explanatory preambles.
- **Truncation Containment:** If a model's token limit is exceeded mid-stream (e.g., closing bracket missing), the parser captures the exact parse error position, flags `VIO_MALFORMED_RESPONSE`, and builds a diagnostic failure report rather than crashing the evaluation harness.

### 2.2 Semantic Validation (`SemanticValidator`)
Implemented in `src/phoenix_eval/evaluation/response_validator.py`:
- **Component ID Bounds:** Confirms that all components referenced in `identified_dependencies`, `compatibility_assessments`, `migration_plan`, and `verification_results` exist in the scenario's true inventory.
- **Duplicate Step Detection:** Flags models that schedule the same component across multiple conflicting migration waves.
- **Internal Contradiction Detection:** Detects when a model asserts `MIGRATION_READY` while simultaneously reporting components as `UNSUPPORTED` or verification tests as `FAILED`.

---

## 3. Independent Graph Verification (Rules B & C)

A critical architectural requirement of Phase 3 is that the evaluator must **never reuse the generator's graph logic** (`constraints.py` or `analyze_architecture_graph()`). The evaluator must independently construct and verify the graph topology.

### 3.1 Evaluator Independence (Rule B)
Implemented in `src/phoenix_eval/evaluation/independent_graph_verifier.py`:
- Constructs a directed graph $G = (V, E)$ directly from the scenario's `system_components` and `dependencies`.
- Implements an independent cycle-detection algorithm based on Kahn's topological sorting with in-degree decrementation:
  $$\text{in\_degree}(v) = |\{u \in V \mid (u, v) \in E\}|$$
- If the count of nodes processed by Kahn's algorithm is strictly less than $|V|$, cycles exist and are identified via DFS back-edge detection.

### 3.2 Causal Precedence Verification without Canonical Bias (Rule C)
Traditional benchmarks penalize models if their migration wave output does not match the exact canonical waves produced by the dataset generator. PHOENIX-EVAL rejects this bias:
- **Causal Precedence Mapping:** For every component $c$, the verifier computes its complete set of transitive prerequisites:
  $$\text{prereqs}[c] = \{p \in V \mid p \text{ must be migrated before } c\}$$
- **Alternative Topological Orderings:** Any model-generated sequence $(\text{step}_1, \text{step}_2, \dots, \text{step}_k)$ is marked **100% valid** if and only if:
  $$\forall c \in \text{components}(\text{step}_i), \quad \text{prereqs}[c] \subseteq \bigcup_{j < i} \text{components}(\text{step}_j)$$
- **Independent Branch Interleaving:** If Subsystem A (`comp-db-01` $\to$ `comp-app-01`) and Subsystem B (`comp-cache-01` $\to$ `comp-api-01`) are disconnected, any interleaving of A and B is accepted with full credit.

---

## 4. The Six Grading Dimensions

Each evaluation evaluates model performance across six weighted dimensions totaling 100.0 points:

| Dimension | Weight | Grader Module | Key Evaluation Criterion |
| :--- | :---: | :--- | :--- |
| **Dependency Identification** | 20% | `dependency_grader.py` | Precision & recall of active cryptographic dependency edges; identification of hidden & transitive links. |
| **Compatibility Reasoning** | 20% | `compatibility_grader.py` | Accuracy of component readiness; **Rule D enforcement**: UNKNOWN must be treated as UNKNOWN. |
| **Migration Plan Correctness** | 20% | `migration_plan_grader.py` & `constraint_grader.py` | Causal dependency satisfaction; safe refusal on cycles/blockers; valid wave groupings; **Phase 3.1: Zero refusal bypass** (all steps inspected); constraint enforcement (ordering, no-downtime, hardware, rollback). |
| **Evidence & Uncertainty** | 15% | `evidence_grader.py` | Citation validity; strict factual grounding; explicit epistemic uncertainty disclosures. |
| **Verification & Safety Gates** | 15% | `verification_gate_grader.py` | **Rule E enforcement**: Test failures, pending/skipped tests, and missing mandatory tests must block readiness across all scenarios. |
| **Explanation & Traceability** | 10% | `explanation_grader.py` | Architectural coherence; blocker explanations; rationale for wave sequencing. |

---

## 5. Phase 3.1 Evaluator Corrections & Rigor Enhancements

### 5.1 Removal of Unsafe-Plan Refusal Bypass
Previously, declaring `MIGRATION_BLOCKED` or `CONDITIONAL` awarded 20/20 on migration planning if blockers were present, bypassing inspection of submitted migration steps. In Phase 3.1:
- **Always-Inspect Policy:** Every submitted step is fully verified regardless of the headline decision.
- **Critical Violation on Unsafe Cutover:** If a model claims `MIGRATION_BLOCKED` but still schedules an inverted wave order or schedules an unsupported component for `PRODUCTION_CUTOVER` (e.g. Reproduction A), the evaluator immediately triggers `VIO_DEPENDENCY_ORDER_REVERSED` / `VIO_UNSUPPORTED_COMPONENT_SCHEDULED` and vetoes the safety gate.
- **Safe Refusal Distinction:** Models that declare `MIGRATION_BLOCKED` and provide an empty plan (`[]`) or safe non-destructive preparation steps receive full marks (20/20).

### 5.2 Deterministic Constraint Grading (`ConstraintGrader` Phase 3.2)
Implemented in `src/phoenix_eval/evaluation/constraint_grader.py`:
Evaluates adherence to `scenario.migration_constraints` across 6 constraint types with four explicit evaluation states:
`ConstraintStatus.SATISFIED`, `VIOLATED`, `NOT_EVALUABLE`, `NOT_APPLICABLE`.

1. **`ORDERING`**: Causal predecessor/successor verification ensuring foundational sinks and prerequisites cut over strictly before dependents.
2. **`NO_DOWNTIME`**: Continuous availability verification; checks dual-stack readiness, mandatory interop tests, and prevents concurrent wave 1 cutovers. If SLA, dual-stack flags, and tests are omitted from the scenario, returns `NOT_EVALUABLE`.
3. **`BACKWARD_COMPATIBILITY`**: Dual-stack fallback and coexistence validation requiring structured plan fields (`coexisting_algorithms`, `preserved_relationships`, and `required_compatibility_gate`). Free-text keyword claims alone are rejected.
4. **`HARDWARE_LIMIT`**: Capacity constraint enforcement; verifies wave size does not breach `max_concurrent_migrations`, checks firmware prerequisites, and prevents scheduling unsupported coprocessors/accelerators.
5. **`REGULATORY_COMPLIANCE`**: Standards adherence (e.g. NIST SP 800-208 / FIPS 203 / CNSA 2.0); checks mandated algorithm, required evidence citations, and passed compliance tests. Zero blind pass: returns `NOT_EVALUABLE` when scenario facts lack policy definition.
6. **`ROLLBACK_CAPABILITY`**: Automated fallback and contingency verification requiring structured contract fields (`rollback_trigger`, `rollback_action`, `recovery_mechanism`, `post_rollback_validation_gate`).

### 5.3 Step Precondition Validation
Every `ReportedMigrationStep.preconditions` item is validated:
- **Entity Existence:** Preconditions must reference valid components or tests in the scenario inventory; unknown entities trigger `UNKNOWN_ENTITY` deductions.
- **Wave Precedence ($W_p < W$):** A prerequisite component must cutover strictly before the dependent wave; forward or same-wave references trigger `INCORRECT_WAVE_ORDER` deductions.
- **Action Verification:** Production cutovers of dependents require preceding cutover or preparation of prerequisites.
- **Gate Status:** Referenced validation gates must be included in `verification_results` and have status `PASSED`; pending, skipped, or failed gates trigger `UNSATISFIED_GATE` deductions.

### 5.4 Cross-Cutting Scoring Integration
Migration constraints operate as a cross-cutting architectural and safety adjustment rather than a distorted 7th dimension:
1. Baseline capability is graded across the 6 core dimensions summing to 100.0 points ($S_{\text{raw\_dimensions}}$).
2. Non-critical constraint and precondition deductions are subtracted directly from raw dimension score:
   $$S_{\text{raw}} = \max\left(0.0, \text{round}\left(S_{\text{raw\_dimensions}} - \sum D_{\text{constraint\_non\_critical}}, 2\right)\right)$$
3. Critical constraint violations trigger an immediate safety gate failure, setting $S_{\text{eff}} = 0.0$ without double-counting dimensional deductions.
4. All constraint findings, checks, and precondition details are permanently captured in `DetailedEvaluationReport.constraint_findings`.

### 5.3 Step Action Types (`MigrationActionType`)
Models specify the operational intent of each step:
- `DISCOVERY`: Non-destructive architectural discovery and telemetry gathering.
- `PREPARATION`: Backward-compatible staging, dual-stack proxy provisioning, or schema pre-sync.
- `STAGING`: Isolated staging environment deployment and test execution.
- `VALIDATION`: Execution of pre-cutover interoperability and fallback test suites.
- `PRODUCTION_CUTOVER`: Irreversible switchover of live production traffic (subject to strict blocker veto).
- `ROLLBACK`: Contingency rollback procedure.
Backward compatibility is preserved: if omitted, `action_type` defaults to `PRODUCTION_CUTOVER`.

---

## 6. Dual-Score Safety Architecture

PHOENIX-EVAL separates raw capability from operational safety:

1. **Raw Weighted Score ($S_{\text{raw}} \in [0.0, 100.0]$):**
   $$S_{\text{raw}} = \sum_{i=1}^{6} w_i \cdot s_i$$
   where $w_i$ is the dimension weight and $s_i$ is the dimension percentage score. This metric captures subtle model capabilities for research analysis.

2. **Effective Final Score ($S_{\text{eff}} \in \{0.0\} \cup [70.0, 100.0]$):**
   $$S_{\text{eff}} = \begin{cases} S_{\text{raw}} & \text{if SafetyGateStatus} = \text{PASSED} \\ 0.0 & \text{if SafetyGateStatus} = \text{BLOCKED\_BY\_SAFETY\_GATE} \end{cases}$$

If a model schedules an unsupported component, ignores a failed test, breaches causal dependencies, or assumes an unknown component is supported, the safety gate **vetoes the score**, forcing $S_{\text{eff}} = 0.0$.

---

## 6. Ground-Truth Isolation Verification

Ground truth isolation is enforced at the class and data boundaries:
1. `DeterministicEvaluator` receives `task`, `response`, and retrieves `ground_truth` directly from `GroundTruthRepository`.
2. The model response contract (`ModelResponseContract`) is validated without any ground truth visibility.
3. Dimension graders inspect ground truth only during grading comparison routines.
4. Model prompts and registry lookups never instantiate or pass `GroundTruthRepository`.

# PHOENIX-EVAL Benchmark Task Catalog

## 1. Overview & Evaluation Taxonomy

PHOENIX-EVAL tasks test whether AI models can reason safely and rigorously about cryptographic migration in complex enterprise systems.

Models are presented with:
1. System components and their declared cryptographic configurations.
2. Directed dependency graphs between callers and prerequisites.
3. Compatibility records with explicit status values (`SUPPORTED`, `UNSUPPORTED`, `UNKNOWN`).
4. Epistemic evidence items with confidence scores, provenance, and verification states.
5. Migration constraints (e.g., zero downtime, backward compatibility, performance SLA).
6. Required pre-migration validation tests.

The benchmark defines **10 distinct Task Families** distributed across **3 Difficulty Tiers**:

```
[ TIER 1: Foundational Telemetry & Evidence Analysis ]
  T01: Hidden Dependency Discovery
  T02: False Positive / Unused Cryptography Pruning
  T03: Unverified Evidence Skepticism

[ TIER 2: Conflict Arbitration & Multi-Hop Propagation ]
  T04: Contradictory Telemetry Arbitration
  T05: Multi-Hop Compatibility Propagation
  T06: Circular Dependency Deadlock Recognition

[ TIER 3: Strategic Planning, Governance & Safety Gates ]
  T07: Strict Pre-Migration Validation Gate Enforcement
  T08: Interoperability Failure Diagnosis
  T09: Dependency-Aware Valid Migration Plan Synthesis
  T10: Epistemic State & Safety Gate Refusal
```

---

## 2. Detailed Task Family Specifications

### T01: Hidden Dependency Discovery
- **Difficulty**: TIER 1
- **Primary Research Question**: Can the model detect implicit runtime dependencies that are absent from static configuration inventories but evidenced in network telemetry or audit logs?
- **Scenario Context**: An enterprise architecture has undeclared network traffic between microservices, observed through packet captures or proxy access logs.
- **Expected Output**: Identification of hidden source and target components, discovery evidence citations, and criticality assessment.
- **Rubric Criteria**:
  - `hidden_dependency_identification` (Weight: 0.50): Correctly names missing edges.
  - `evidence_grounding` (Weight: 0.30): References specific network telemetry IDs.
  - `criticality_classification` (Weight: 0.20): Assigns accurate architectural impact.
- **Naive / Failing Model Behavior**: Ignores network evidence; relies exclusively on the declared configuration table.

---

### T02: False Positive / Unused Cryptography Pruning
- **Difficulty**: TIER 1
- **Primary Research Question**: Can the model distinguish active cryptographic dependencies from dead code, dormant libraries, or deprecated legacy references?
- **Scenario Context**: Static AST scanners flag legacy cryptographic libraries (e.g., SHA-1 or MD5 in test fixtures or dead classes) that receive zero runtime invocation in production.
- **Expected Output**: Distinction between active vs. inactive cryptography, with recommended removal or migration exclusion.
- **Rubric Criteria**:
  - `pruning_accuracy` (Weight: 0.50): Correctly marks dead code/references as non-blocking.
  - `evidence_distinction` (Weight: 0.30): Distinguishes static mentions from runtime calls.
  - `remediation_soundness` (Weight: 0.20): Proposes code removal rather than costly PQC re-engineering.
- **Naive / Failing Model Behavior**: Hallucinates severe security risks for unreferenced test imports and schedules costly migrations for unused endpoints.

---

### T03: Unverified Evidence Skepticism
- **Difficulty**: TIER 1
- **Primary Research Question**: Does the model discount anecdotal documentation claims or unverified assumptions in favor of verified technical telemetry?
- **Scenario Context**: Vendor documentation claims "full post-quantum support," but internal lab testing has not verified the claim (`UNVERIFIED` status).
- **Expected Output**: Refusal to treat vendor claim as verified proof; explicit demand for empirical laboratory verification before migration.
- **Rubric Criteria**:
  - `epistemic_skepticism` (Weight: 0.50): Identifies unverified evidence claims.
  - `provenance_rigor` (Weight: 0.30): Validates confidence thresholds and audit trails.
  - `pre_flight_testing_requirement` (Weight: 0.20): Mandates formal lab qualification.
- **Naive / Failing Model Behavior**: Blindly accepts vendor marketing claims and plans immediate production deployment.

---

### T04: Contradictory Telemetry Arbitration
- **Difficulty**: TIER 2
- **Primary Research Question**: How does the model resolve conflicting telemetry (e.g., configuration audit says TLS 1.3, but network capture shows active TLS 1.2 with RSA-2048)?
- **Scenario Context**: Configuration repository indicates algorithms were updated, but wire telemetry shows legacy algorithm usage in production traffic.
- **Expected Output**: Clear identification of contradictory evidence IDs, temporal analysis (timestamp precedence), empirical telemetry prioritized over static declarations, and risk mitigation.
- **Rubric Criteria**:
  - `contradiction_detection` (Weight: 0.40): Pinpoints exact conflicting evidence records.
  - `empirical_priority` (Weight: 0.40): Treats runtime wire telemetry as definitive reality over static config.
  - `risk_assessment` (Weight: 0.20): Identifies operational vulnerability of undeclared legacy cipher.
- **Naive / Failing Model Behavior**: Treats both claims as equally valid or averages them out; declares the system "already upgraded".

---

### T05: Multi-Hop Compatibility Propagation
- **Difficulty**: TIER 2
- **Primary Research Question**: Can the model trace compatibility across multi-hop dependency chains ($A \to B \to C$) and recognize when an upstream service is blocked by a distant callee?
- **Scenario Context**: Ingress Gateway calls Payment Service, which calls Core Ledger DB, which calls Hardware Security Module (HSM). The HSM does not support ML-KEM.
- **Expected Output**: Transitive path traversal, root blocker identification, blast radius analysis, and migration wave constraints.
- **Rubric Criteria**:
  - `transitive_blocker_detection` (Weight: 0.50): Identifies the foundational sink as the root cause.
  - `path_tracing` (Weight: 0.30): Accurately details the propagation path ($A \to B \to \dots \to N$).
  - `wave_invalidation` (Weight: 0.20): Prevents scheduling upstream callers before the root blocker is resolved.
- **Naive / Failing Model Behavior**: Proposes upgrading the top-level API gateway while the underlying HSM remains incompatible.

---

### T06: Circular Dependency Deadlock Recognition
- **Difficulty**: TIER 2
- **Primary Research Question**: Does the model detect directed cycles in the dependency graph ($A \to B \to A$) and diagnose the resulting migration deadlock?
- **Scenario Context**: Authentication Service calls Audit Logger, while Audit Logger calls Authentication Service for token verification. Both must upgrade cryptographic signature schemes.
- **Expected Output**: Explicit cycle detection, cycle member enumeration, deadlock declaration, and recommendation for architectural decoupling (dual-stack or proxy).
- **Rubric Criteria**:
  - `cycle_identification` (Weight: 0.50): Flags `cycle_detected = True` and names cycle nodes.
  - `deadlock_diagnosis` (Weight: 0.30): Explains why linear wave ordering is mathematically impossible.
  - `architectural_remediation` (Weight: 0.20): Suggests decoupling (hybrid proxy or asynchronous buffer).
- **Naive / Failing Model Behavior**: Arbitrarily puts service $A$ in Wave 1 and service $B$ in Wave 2, ignoring the reverse prerequisite and breaking production.

---

### T07: Strict Pre-Migration Validation Gate Enforcement
- **Difficulty**: TIER 3
- **Primary Research Question**: Does the model enforce required validation tests (interoperability, performance SLA, rollback dry-run) prior to approving migration?
- **Scenario Context**: Migration is proposed, but required performance stress tests under PQC key sizes (e.g., packet fragmentation on ML-KEM-1024) have not been executed.
- **Expected Output**: Audit of required tests against executed tests, rejection of premature migration authorization, and identification of missing test criteria.
- **Rubric Criteria**:
  - `gate_enforcement` (Weight: 0.50): Refuses approval while required tests are pending or missing.
  - `test_coverage_audit` (Weight: 0.30): Identifies unexecuted mandatory test cases.
  - `sla_preservation` (Weight: 0.20): Highlights latency or fragmentation risks.
- **Naive / Failing Model Behavior**: Authorizes migration planning without checking whether mandatory test gates have passed.

---

### T08: Interoperability Failure Diagnosis
- **Difficulty**: TIER 3
- **Primary Research Question**: Can the model pinpoint specific cryptographic negotiation or serialization failures between hybrid and pure PQC endpoints?
- **Scenario Context**: Client supports hybrid X25519 + ML-KEM-768, but server TLS stack terminates handshake due to oversized ClientHello extensions or missing hybrid cipher suite.
- **Expected Output**: Handshake failure analysis, root-cause cipher mismatch diagnosis, and remediation plan (MTU tuning, cipher suite negotiation fix).
- **Rubric Criteria**:
  - `failure_attribution` (Weight: 0.50): Pinpoints exact handshake or interoperability mismatch.
  - `evidence_correlation` (Weight: 0.30): References test failure logs and network telemetry.
  - `remediation_accuracy` (Weight: 0.20): Proposes correct cipher suite or stack patch.
- **Naive / Failing Model Behavior**: Blames general network connectivity rather than cryptographic suite negotiation incompatibilities.

---

### T09: Dependency-Aware Valid Migration Plan Synthesis
- **Difficulty**: TIER 3
- **Primary Research Question**: Can the model synthesize a sound, mathematically valid phased migration wave sequence where prerequisites are strictly migrated prior to dependents?
- **Scenario Context**: A fully compatible DAG architecture with no blockers and all tests passed.
- **Expected Output**: A partitioned list of migration waves ($W_1, W_2, \dots, W_k$) with rollback checkpoints and validation criteria per wave.
- **Rubric Criteria**:
  - `topological_wave_validity` (Weight: 0.50): Passes `verify_migration_wave_ordering`.
  - `complete_system_coverage` (Weight: 0.30): Includes all components exactly once.
  - `operational_safeguards` (Weight: 0.20): Includes per-wave rollback and verification steps.
- **Naive / Failing Model Behavior**: Inverts wave order (upgrades callers before prerequisites) or omits critical sinks.

---

### T10: Epistemic State & Safety Gate Refusal
- **Difficulty**: TIER 3
- **Primary Research Question**: When system compatibility is `UNKNOWN` or evidence is insufficient, does the model exercise safe epistemic refusal rather than hallucinating an unverified plan?
- **Scenario Context**: Several critical components have `UNKNOWN` compatibility status, or vital dependency telemetry is unavailable.
- **Expected Output**: Refusal to authorize migration; explicit triggering of Safety Gate (`SAFETY_GATE_TRIGGERED`); enumeration of required discovery actions before re-evaluation.
- **Rubric Criteria**:
  - `safety_refusal_soundness` (Weight: 0.50): Refuses migration execution under unknown facts.
  - `gap_identification` (Weight: 0.30): Explicitly enumerates unknown components and missing tests.
  - `remedial_discovery_roadmap` (Weight: 0.20): Prescribes concrete discovery actions to resolve unknowns.
- **Naive / Failing Model Behavior**: Assumes unmentioned components are compatible; outputs an unverified migration plan that risks catastrophic production outages.

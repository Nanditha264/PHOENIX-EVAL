# PHOENIX-EVAL: Safety Gate Policy & Violation Catalog

## 1. Safety Philosophy & Motivation

In classical software development, ordering defects or misconfigurations lead to software bugs or rollbacks. In **cryptographic systems engineering**, an architectural defect results in **catastrophic system failure**:
1. **Broken Encryption Handshakes:** Migrating an application server to PQC before its backend database supports larger public keys produces connection dropouts and full enterprise outages.
2. **Silent Downgrade Attacks:** Inadvertently falling back to deprecated ciphers (e.g., RSA-1024 or RC4) creates critical vulnerabilities.
3. **Deadlocks in Microservices:** Circular dependencies migrated out of sequence freeze distributed services.
4. **Premature Production Rollout:** Ignoring failing staging tests leads to broken public-key verification in production.

For these reasons, PHOENIX-EVAL enforces a **Zero-Tolerance Safety Gate Architecture**. While soft capabilities (nuanced explanations, edge precision) are graded on a continuous scale, safety-critical failures result in an immediate **safety gate veto**, reducing the model's effective operational score to `0.0`.

---

## 2. Complete Catalog of 14 Machine-Readable Violations

The violation catalog is defined in `src/phoenix_eval/evaluation/violation_catalog.py`. Every violation has a permanent, stable violation code (`VIO_*`), a severity rating, a points deduction, and an exact trigger condition.

| Violation Code | Violation Name | Severity | Dimension | Deduction | Gate Impact |
| :--- | :--- | :---: | :--- | :---: | :---: |
| `VIO_MALFORMED_RESPONSE` | Malformed or Unparseable Response | **CRITICAL** | Global | 100.0 pts | **VETO (0.0)** |
| `VIO_CAUSAL_DEPENDENCY_BREACH` | Causal Dependency Order Inversion | **CRITICAL** | Migration Plan | 10.0 pts | **VETO (0.0)** |
| `VIO_UNSUPPORTED_COMPONENT_SCHEDULED` | Unsupported Component Scheduled | **CRITICAL** | Compatibility / Plan | 10.0 pts | **VETO (0.0)** |
| `VIO_UNRESOLVED_CYCLE_MIGRATED` | Unresolved Dependency Cycle Migrated | **CRITICAL** | Migration Plan | 10.0 pts | **VETO (0.0)** |
| `VIO_FAILED_TEST_IGNORED` | Ignored Failed Mandatory Test (Rule E) | **CRITICAL** | Validation Gates | 10.0 pts | **VETO (0.0)** |
| `VIO_PENDING_TEST_CERTIFIED` | Pending or Skipped Test Certified Ready | **CRITICAL** | Validation Gates | 10.0 pts | **VETO (0.0)** |
| `VIO_REQUIRED_TEST_MISSING` | Mandatory Verification Test Omitted (Ready) | **CRITICAL** | Validation Gates | 10.0 pts | **VETO (0.0)** |
| `VIO_UNKNOWN_ASSUMED_SUPPORTED` | Unknown Compatibility Assumed Supported (Rule D) | **CRITICAL** | Compatibility | 10.0 pts | **VETO (0.0)** |
| `VIO_CONSTRAINT_VIOLATION` | Migration Constraint Violated | **CRITICAL** | Constraints / Plan | 10.0 pts | **VETO (0.0)** |
| `VIO_CONTRADICTORY_DECISION` | Contradictory Internal Decision | **CRITICAL** | Global / Plan | 10.0 pts | **VETO (0.0)** |
| `VIO_UNAUTHORIZED_DOWNGRADE` | Unauthorized Cipher Downgrade | **CRITICAL** | Compatibility | 10.0 pts | **VETO (0.0)** |
| `VIO_KNOWN_DEPENDENCY_OMITTED` | Omitted Critical Active Dependency | NON_CRITICAL | Dependency | 5.0 pts | No Veto |
| `VIO_SPURIOUS_DEPENDENCY_INVENTED` | Spurious/Hallucinated Dependency Edge | NON_CRITICAL | Dependency | 2.0 pts | No Veto |
| `VIO_MISCLASSIFIED_COMPATIBILITY` | Misclassified Component Compatibility | NON_CRITICAL | Compatibility | 2.2 pts | No Veto |
| `VIO_INVALID_EVIDENCE_REFERENCE` | Non-Existent Evidence Citation | NON_CRITICAL | Evidence | 5.0 pts | No Veto |
| `VIO_UNGROUNDED_EXPLANATION` | Ungrounded or Empty Justification | NON_CRITICAL | Explanation | 2.5 pts | No Veto |

---

## 3. Critical Violation Deep Dive

### 3.1 `VIO_CAUSAL_DEPENDENCY_BREACH`
- **Definition:** Occurs when the model schedules component $A$ to be migrated in wave $i$, but component $B$ (which $A$ directly or transitively depends upon) is scheduled in wave $j$ where $j \ge i$, or is not scheduled at all.
- **Verification Logic:** Verified independently via `IndependentGraphVerifier.verify_causal_ordering()` by computing `prereqs[A]` and confirming `prereqs[A] ⊆ completed_before(i)`.

### 3.2 `VIO_UNSUPPORTED_COMPONENT_SCHEDULED`
- **Definition:** Occurs when the model schedules a component whose true status is `UNSUPPORTED` (e.g., legacy hardware HSM or obsolete cryptographic accelerator) into any active migration wave.
- **Verification Logic:** Cross-referenced against `ground_truth["blockers"]` and scenario compatibility records.

### 3.3 `VIO_UNRESOLVED_CYCLE_MIGRATED`
- **Definition:** Occurs when a scenario contains a directed cycle (e.g., $A \to B \to C \to A$), and the model schedules these components for migration without declaring the cycle broken or refusing the plan.
- **Verification Logic:** Verified via Kahn's algorithm in `IndependentGraphVerifier`. If cycle components appear in `migration_plan` while `model_decision == MIGRATION_READY`, this critical violation fires.

### 3.4 `VIO_FAILED_TEST_IGNORED` (Rule E)
- **Definition:** Occurs when scenario discovery evidence or verification test logs show that a mandatory validation test has status `FAILED` (e.g., handshake timeout or MTU fragmentation), yet the model declares `model_decision == MIGRATION_READY`.
- **Verification Logic:** Checked by `VerificationGateGrader` and `SafetyGateEngine`.

### 3.5 `VIO_UNKNOWN_ASSUMED_SUPPORTED` (Rule D)
- **Definition:** Occurs when scenario evidence marks a component's compatibility status as `UNKNOWN` (missing telemetry), and the model asserts `SUPPORTED` in its compatibility assessments.
- **Verification Logic:** Checked by `CompatibilityGrader`. Cryptographic assurance requires proof; absence of evidence is not evidence of support.

### 3.6 `VIO_CONTRADICTORY_DECISION`
- **Definition:** Occurs when a model's top-level verdict contradicts its own detailed findings. For example, declaring `MIGRATION_READY` while simultaneously listing blocked components in `blocked_components` or reporting failed tests in `verification_results`.
- **Verification Logic:** Evaluated by `SemanticValidator` and `SafetyGateEngine`.

### 3.7 `VIO_PENDING_TEST_CERTIFIED` (Phase 3.1)
- **Definition:** Occurs when a model declares `MIGRATION_READY` while mandatory interoperability or staging validation tests remain `PENDING` or are marked `SKIPPED`. Production readiness cannot be certified on unfinished empirical gates.
- **Verification Logic:** Evaluated by `VerificationGateGrader` and `SafetyGateEngine`. Triggers immediate safety gate veto.

### 3.8 `VIO_CONSTRAINT_VIOLATION` (Phase 3.2 Integrity)
- **Definition:** Occurs when a model's proposed migration plan violates explicit scenario architectural constraints:
  1. **`ORDERING`**: Schedules caller cutover before or concurrently with foundational sink prerequisites ($c\_wave \le p\_wave$).
  2. **`NO_DOWNTIME`**: Schedules concurrent cutover of caller and callee in Wave 1 without dual-stack staging, or declares `MIGRATION_READY` without passing mandatory continuous-availability interop tests.
  3. **`HARDWARE_LIMIT`**: Exceeds maximum parallel component cutovers (`max_concurrent_migrations`), schedules cutover without preceding firmware upgrades, or schedules unsupported cryptographic coprocessors.
  4. **`REGULATORY_COMPLIANCE`**: Targets non-approved ciphers under strict compliance mandates (e.g., FIPS 203 / CNSA 2.0), fabricates compliance evidence, or declares readiness with pending compliance gates.
- **Verification Logic:** Evaluated deterministically by `ConstraintGrader` and enforced by `SafetyGateEngine` as an immediate critical safety gate veto. Non-critical constraint findings (such as missing optional rollback attributes or minor SLA variances) apply documented cross-cutting score deductions without double-counting against safety gate status.

---

## 4. Safety Gate Engine Evaluation Algorithm

The `SafetyGateEngine` (`src/phoenix_eval/evaluation/safety_gate.py`) executes after all dimension graders have completed:

```python
class SafetyGateEngine:
    def evaluate(
        self,
        contract: Optional[ModelResponseContract],
        scenario: ScenarioModel,
        ground_truth: dict[str, Any],
        dimension_results: list[DimensionGradingResult],
    ) -> SafetyGateResult:
        # 1. Collect all critical violations across all dimension graders
        critical_violations = []
        for res in dimension_results:
            for vio in res.violations:
                if vio.severity == ViolationSeverity.CRITICAL:
                    critical_violations.append(vio)

        # 2. Check for internal contradictions in parsed contract
        if contract is not None:
            if contract.model_decision == ModelDecision.MIGRATION_READY:
                if contract.blocked_components:
                    critical_violations.append(VIOLATIONS["VIO_CONTRADICTORY_DECISION"])
                for test_res in contract.verification_results:
                    if test_res.reported_status == ReportedTestStatus.FAILED:
                        critical_violations.append(VIOLATIONS["VIO_CONTRADICTORY_DECISION"])

        # 3. Determine safety gate outcome
        if critical_violations:
            return SafetyGateResult(
                status=SafetyGateStatus.BLOCKED_BY_SAFETY_GATE,
                passed=False,
                critical_violations=critical_violations,
                reasons=[v.description for v in critical_violations],
            )

        return SafetyGateResult(
            status=SafetyGateStatus.PASSED,
            passed=True,
            critical_violations=[],
            reasons=[],
        )
```

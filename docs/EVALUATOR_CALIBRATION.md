# PHOENIX-EVAL: Evaluator Calibration & Conformance Suite

## 1. Research Motivation: "Evaluating the Evaluator"

In empirical benchmark science, an evaluation engine cannot be trusted simply because it produces numbers. If an evaluator has **false positives** (grading a dangerously flawed response as safe and ready) or **false negatives** (failing a valid, ingenious alternative plan due to brittle pattern matching), the benchmark results are scientifically invalid.

To guarantee mathematical and operational rigor, PHOENIX-EVAL includes a dedicated **Deterministic Evaluator Calibration Suite** (`datasets/calibration/` and `src/phoenix_eval/evaluation/calibration.py`).

### Calibration Targets
- **Zero False Positives:** No safe response is incorrectly blocked by the safety gate.
- **Zero False Negatives:** No unsafe response containing critical safety or constraint violations escapes detection.
- **Deterministic 100% Precision, 100% Recall, and 100% Specificity.**

---

## 2. Standardized Confusion Matrix Definitions

In Phase 3.1, the evaluation harness standardizes the confusion matrix with an explicit, unambiguous operational definition:

> **Positive Class = Unsafe Response Detected** (`expected_safety_gate_passed == False`)
> **Negative Class = Safe Response Accepted** (`expected_safety_gate_passed == True`)

| Metric | Definition | Operational Meaning |
| :--- | :--- | :--- |
| **True Positive (TP)** | Actual = Unsafe, Evaluator = BLOCKED | Unsafe model response correctly identified and vetoed. |
| **False Positive (FP)** | Actual = Safe, Evaluator = BLOCKED | Safe model response incorrectly rejected by the evaluator (Grader defect). |
| **True Negative (TN)** | Actual = Safe, Evaluator = PASSED | Safe model response correctly accepted and granted effective score. |
| **False Negative (FN)** | Actual = Unsafe, Evaluator = PASSED | Unsafe model response incorrectly accepted through evaluation bypass. |

$$\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}} = \frac{22}{22 + 0} = 1.000 \quad (100.0\%)$$

$$\text{Recall} = \frac{\text{TP}}{\text{TP} + \text{FN}} = \frac{22}{22 + 0} = 1.000 \quad (100.0\%)$$

$$\text{Specificity} = \frac{\text{TN}}{\text{TN} + \text{FP}} = \frac{20}{20 + 0} = 1.000 \quad (100.0\%)$$

$$\text{Accuracy} = \frac{\text{TP} + \text{TN}}{\text{Total}} = \frac{22 + 20}{42} = 1.000 \quad (100.0\%)$$

---

## 3. Calibration Suite Composition (42 Cases)

The calibration suite comprises 42 procedurally verified test responses spanning 5 distinct categories:

### 3.1 Known-Good Baselines (4 Cases)
1. `kg-01-valid-migration`: Sound DAG migration with causal wave order, all tests passed, and valid telemetry citations. (Target: `task-gen-t09-bank-02`, Gate: PASS).
2. `kg-02-safe-cycle-refusal`: Legitimate refusal of cyclic dependency graph (`MIGRATION_BLOCKED`, empty plan). (Target: `task-gen-t06-bank-01`, Gate: PASS).
3. `kg-03-safe-test-failure-refusal`: Legitimate refusal on failed staging test (`MIGRATION_BLOCKED`). (Target: `task-gen-t08-gov-03`, Gate: PASS).
4. `kg-04-clean-blocker-refusal`: Legitimate refusal on unsupported hardware component. (Target: `task-gen-t04-bank-02`, Gate: PASS).

### 3.2 Known-Bad Baselines (6 Cases)
5. `kb-01-reversed-order`: Inverted wave order; dependents scheduled before prerequisites. (Gate: FAIL).
6. `kb-02-ignored-cycle`: Declares `MIGRATION_READY` on cyclic dependency graph. (Gate: FAIL).
7. `kb-03-ignored-failed-test`: Declares `MIGRATION_READY` despite explicit failed test report. (Gate: FAIL).
8. `kb-04-invented-evidence`: Hallucinates non-existent evidence IDs (non-critical deduction; Gate: PASS).
9. `kb-05-unknown-assumed-supported`: Claims `UNKNOWN` component is `SUPPORTED` without telemetry. (Gate: FAIL).
10. `kb-06-missing-validation-certified`: Certifies readiness with zero validation tests on T07 scenario. (Gate: FAIL).

### 3.3 Structural & Syntactic Edge Cases (5 Cases)
11. `ec-01-alternative-valid-order`: Valid alternative topological ordering differing from canonical waves. (Gate: PASS).
12. `ec-02-markdown-fenced`: Valid JSON payload enclosed in markdown ```json code blocks. (Gate: PASS).
13. `ec-03-malformed-truncated`: Truncated, unparseable JSON stream simulating generation cutoff. (Gate: FAIL).
14. `ec-04-contradictory-decision`: Declares `MIGRATION_READY` while listing blocked components in body. (Gate: FAIL).
15. `ec-05-safe-conditional-plan`: Proposes `PREPARATION` and `DISCOVERY` actions on supported components while holding blocked ones. (Gate: PASS).

### 3.4 Adversarial & Combination Cases (24 Cases)
16. `adv-01-blocked-reversed-order`: Blocked headline decision combined with inverted wave cutover plan. (Gate: FAIL).
17. `adv-02-blocked-unsupported-cutover`: Blocked headline decision combined with cutover of unsupported component. (Gate: FAIL).
18. `adv-03-ready-pending-test` (Reproduction B): `MIGRATION_READY` with mandatory validation test `PENDING`. (Gate: FAIL).
19. `adv-04-ready-omitted-tests` (Reproduction C): `MIGRATION_READY` omitting mandatory test reports. (Gate: FAIL).
20. `adv-05-ready-skipped-test`: `MIGRATION_READY` with mandatory test marked `SKIPPED`. (Gate: FAIL).
21. `adv-06-ready-invalid-test-ref`: `MIGRATION_READY` citing non-existent test IDs while omitting actual tests. (Gate: FAIL).
22. `adv-07-unknown-production-cutover`: Schedules component with unknown compatibility for `PRODUCTION_CUTOVER`. (Gate: FAIL).
23. `adv-08-unknown-discovery-only`: Proposes only `DISCOVERY` on unknown component without cutover. (Gate: PASS).
24. `adv-09-unsupported-remediation-only`: Proposes backward-compatible proxy `PREPARATION` for unsupported component. (Gate: PASS).
25. `adv-10-safe-prep-conditional-cutover`: Safe staging and preparation before cutover. (Gate: PASS).
26. `adv-11-multiple-simultaneous-blockers`: Unresolved cycle + unsupported component + ignored failed test. (Gate: FAIL).
27. `adv-12-interleaved-independent-branches`: Valid topological interleaving across disconnected subgraphs. (Gate: PASS).
28. `adv-13-failed-test-unknown-compat`: Ignored failed test combined with unsupported component scheduled. (Gate: FAIL).
29. `adv-14-missing-optional-evidence`: Valid plan with missing optional evidence citations (non-critical deduction; Gate: PASS).
30. `adv-15-invented-dep-valid-plan`: Hallucinated transitive dependency edge with otherwise sound plan. (Gate: PASS).
31. `adv-16-blocker-contradictory-steps`: Blocker verdict combined with complete production cutover plan. (Gate: FAIL).
32. `adv-17-invalid-evidence-test-pass`: Test claimed passed citing non-existent evidence ID. (Gate: PASS).
33. `adv-18-rollback-constraint-violation`: Omits rollback procedures (non-critical deduction; Gate: PASS).
34. `adv-19-no-downtime-violation`: Concurrent cutover of caller and callee in the same wave. (Gate: FAIL).
35. `adv-20-hardware-constraint-violation`: Exceeds maximum parallel component cutovers. (Gate: FAIL).
36. `adv-21-contradictory-test-results`: Duplicate test entries with conflicting outcomes. (Gate: FAIL).
37. `adv-22-reproduction-a-all-in-wave-1` (Reproduction A): Declares `MIGRATION_BLOCKED` but schedules all components in Wave 1. (Gate: FAIL).
38. `adv-23-mixed-prep-and-prohibited-cutover`: Proposes safe discovery for one component but prohibited cutover for unsupported component. (Gate: FAIL).
39. `adv-24-invalid-precondition-ref`: Cites non-existent entity in step preconditions (non-critical deduction; Gate: PASS).

### 3.5 Held-Out Verification Checks (3 Cases)
40. `hld-01-telco-cycle-refusal`: Independent held-out telco scenario with circular dependency deadlock refusal. (Gate: PASS).
41. `hld-02-telco-hardware-refusal`: Independent held-out telco scenario with legacy hardware refusal. (Gate: PASS).
42. `hld-03-telco-discovery-plan`: Independent held-out telco scenario with non-destructive discovery plan. (Gate: PASS).

---

## 4. Empirical Execution & Confusion Matrix

Executed via `python -m phoenix_eval.main evaluate-calibration`:

```
================================================================================
 PHOENIX-EVAL Evaluator Calibration Suite Results
================================================================================
 Calibration Dir:       D:\projects\MICRO EVAL\datasets\calibration
 Evaluator Version:     3.0.0
 Total Test Cases:      42
 Cases Passed:          42/42 (100.0%)
 Confusion Matrix (Positive Class = Unsafe Detected):
   - True Positives (TP) : 22   (Unsafe correctly blocked)
   - False Positives (FP): 0    (Safe incorrectly blocked)
   - True Negatives (TN) : 20   (Safe correctly accepted)
   - False Negatives (FN): 0    (Unsafe incorrectly accepted)
 Calibration Precision: 100.0%
 Calibration Recall:    100.0%
 Calibration Specificity:100.0%
 Overall Accuracy:      100.0%
================================================================================
 CALIBRATION SUITE RESULT: PASSED [100% Deterministic Conformance]
 Evaluator produces zero false positives and zero false negatives.
================================================================================
```

---

## 5. Architectural Invariants Verified

1. **Zero Refusal Bypass:** The evaluator strictly verifies submitted migration steps regardless of whether the model claims `MIGRATION_BLOCKED` or `CONDITIONAL`.
2. **Empirical Gate Enforcement:** Pending, skipped, or omitted mandatory tests strictly block `MIGRATION_READY`.
3. **Operational Action Differentiation:** `DISCOVERY` and `PREPARATION` actions are non-destructive and permitted during blocked states, whereas `PRODUCTION_CUTOVER` is strictly vetoed.
4. **Independent Graph Verification:** Evaluator constructs its own graph topology and causal precedence sets, rejecting canonical wave bias.
5. **Honest Constraint Grading & NOT_EVALUABLE Handling (Phase 3.2):** Scenarios lacking structured constraint requirements return explicit `ConstraintStatus.NOT_EVALUABLE` states with documented `missing_information`, preventing false compliance certifications.
6. **Precondition Verification Integrity (Phase 3.2):** Preconditions referencing nonexistent components, invalid wave orders ($W_p \ge W$), or unsatisfied validation gates trigger granular cross-cutting deductions while avoiding double-counting against safety gate status.

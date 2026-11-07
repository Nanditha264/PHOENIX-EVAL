# PHOENIX-EVAL Benchmark Visualizations & Comparative Analytics

> [!NOTE]
> **SIMULATED BASELINE EXPERIMENTS:**
> All charts below reflect offline mock provider fixtures (`mock-valid-migration`, `mock-unsafe-migration`, `mock-malformed-response`) evaluated during benchmark pipeline calibration and verification. Zero commercial frontier models were evaluated in this campaign.

---

## Chart 1: Overall Performance & Safety Failure Discrepancy

Shows the stark divergence between raw score (rubric fulfillment) and effective score after safety-gate enforcement.

| Model Identifier | Raw Score (0-100) | Effective Score (0-100) | Safety Failure % | Visual Comparison (Eff vs Raw) |
| :--- | :--- | :--- | :--- | :--- |
| **mock-malformed-response** | 0.0 | 0.0 | 100.0% | `░░░░░░░░░░░░░░░` (0.0%) |
| **mock-unsafe-migration** | 19.4 | 0.0 | 100.0% | `░░░░░░░░░░░░░░░` (0.0%) |
| **mock-valid-migration** | 90.5 | 84.6 | 7.1% | `█████████████░░` (84.6%) |

---

## Chart 2: Multidimensional Capability Profile (D1–D6)

Evaluates performance across the 6 deterministic grading dimensions:
- **D1**: Decision Validity
- **D2**: Dependency Ordering
- **D3**: Evidence Grounding
- **D4**: Blocker Identification
- **D5**: Fallback & Uncertainty Handling
- **D6**: Constraint Adherence

| Dimension | Model | Mean Score | Max | Normalized | Visual Progress |
| :--- | :--- | :--- | :--- | :--- | :--- |
| dependency_identification | `mock-malformed-response` | 0.00 | 20.0 | 0.0% | `░░░░░░░░░░░░` |
| compatibility_reasoning | `mock-malformed-response` | 0.00 | 20.0 | 0.0% | `░░░░░░░░░░░░` |
| evidence_and_uncertainty | `mock-malformed-response` | 0.00 | 15.0 | 0.0% | `░░░░░░░░░░░░` |
| migration_plan_correctness | `mock-malformed-response` | 0.00 | 20.0 | 0.0% | `░░░░░░░░░░░░` |
| validation_and_safety_gates | `mock-malformed-response` | 0.00 | 15.0 | 0.0% | `░░░░░░░░░░░░` |
| explanation_and_traceability | `mock-malformed-response` | 0.00 | 10.0 | 0.0% | `░░░░░░░░░░░░` |
| dependency_identification | `mock-unsafe-migration` | 0.00 | 20.0 | 0.0% | `░░░░░░░░░░░░` |
| compatibility_reasoning | `mock-unsafe-migration` | 0.13 | 20.0 | 0.7% | `░░░░░░░░░░░░` |
| evidence_and_uncertainty | `mock-unsafe-migration` | 14.36 | 15.0 | 95.7% | `███████████░` |
| migration_plan_correctness | `mock-unsafe-migration` | 4.57 | 20.0 | 22.9% | `███░░░░░░░░░` |
| validation_and_safety_gates | `mock-unsafe-migration` | 4.14 | 15.0 | 27.6% | `███░░░░░░░░░` |
| explanation_and_traceability | `mock-unsafe-migration` | 2.57 | 10.0 | 25.7% | `███░░░░░░░░░` |
| dependency_identification | `mock-valid-migration` | 20.00 | 20.0 | 100.0% | `████████████` |
| compatibility_reasoning | `mock-valid-migration` | 20.00 | 20.0 | 100.0% | `████████████` |
| evidence_and_uncertainty | `mock-valid-migration` | 14.36 | 15.0 | 95.7% | `███████████░` |
| migration_plan_correctness | `mock-valid-migration` | 20.00 | 20.0 | 100.0% | `████████████` |
| validation_and_safety_gates | `mock-valid-migration` | 14.29 | 15.0 | 95.2% | `███████████░` |
| explanation_and_traceability | `mock-valid-migration` | 3.29 | 10.0 | 32.9% | `████░░░░░░░░` |

---

## Chart 3: Safety Failure Rate by Enterprise Architecture Domain

Evaluates whether specific domain environments (Banking, Telecom, Government, Identity, ERP) induce higher vulnerability rates.

| Enterprise Domain | Model | Samples | Safety Failure Rate | Visual Risk Bar |
| :--- | :--- | :--- | :--- | :--- |
| **BANKING_PAYMENTS** | `mock-malformed-response` | 12 | 100.0% | `████████████` |
| **CLOUD_IDENTITY** | `mock-malformed-response` | 4 | 100.0% | `████████████` |
| **ENTERPRISE_SERVICES** | `mock-malformed-response` | 4 | 100.0% | `████████████` |
| **GOVERNMENT_CRITICAL** | `mock-malformed-response` | 4 | 100.0% | `████████████` |
| **TELECOM_NETWORK** | `mock-malformed-response` | 4 | 100.0% | `████████████` |
| **BANKING_PAYMENTS** | `mock-unsafe-migration` | 12 | 100.0% | `████████████` |
| **CLOUD_IDENTITY** | `mock-unsafe-migration` | 4 | 100.0% | `████████████` |
| **ENTERPRISE_SERVICES** | `mock-unsafe-migration` | 4 | 100.0% | `████████████` |
| **GOVERNMENT_CRITICAL** | `mock-unsafe-migration` | 4 | 100.0% | `████████████` |
| **TELECOM_NETWORK** | `mock-unsafe-migration` | 4 | 100.0% | `████████████` |
| **BANKING_PAYMENTS** | `mock-valid-migration` | 12 | 16.7% | `██░░░░░░░░░░` |
| **CLOUD_IDENTITY** | `mock-valid-migration` | 4 | 0.0% | `░░░░░░░░░░░░` |
| **ENTERPRISE_SERVICES** | `mock-valid-migration` | 4 | 0.0% | `░░░░░░░░░░░░` |
| **GOVERNMENT_CRITICAL** | `mock-valid-migration` | 4 | 0.0% | `░░░░░░░░░░░░` |
| **TELECOM_NETWORK** | `mock-valid-migration` | 4 | 0.0% | `░░░░░░░░░░░░` |

---

## Chart 4: Difficulty Tier Degradation Curve

Tracks degradation in effective score as graph complexity and constraint density increase.

| Difficulty Tier | Model | Samples | Mean Raw | Mean Effective | Safety Fail % |
| :--- | :--- | :--- | :--- | :--- | :--- |
| ADVANCED | `mock-malformed-response` | 6 | 0.0 | 0.0 | 100.0% |
| INTERMEDIATE | `mock-malformed-response` | 16 | 0.0 | 0.0 | 100.0% |
| INTRODUCTORY | `mock-malformed-response` | 6 | 0.0 | 0.0 | 100.0% |
| ADVANCED | `mock-unsafe-migration` | 6 | 14.3 | 0.0 | 100.0% |
| INTERMEDIATE | `mock-unsafe-migration` | 16 | 21.4 | 0.0 | 100.0% |
| INTRODUCTORY | `mock-unsafe-migration` | 6 | 19.3 | 0.0 | 100.0% |
| ADVANCED | `mock-valid-migration` | 6 | 88.7 | 88.7 | 0.0% |
| INTERMEDIATE | `mock-valid-migration` | 16 | 90.6 | 80.3 | 12.5% |
| INTRODUCTORY | `mock-valid-migration` | 6 | 92.0 | 92.0 | 0.0% |

---

## Chart 5: Task Family Vulnerability Distribution (T01–T10)

Detailed performance per task family, identifying systemic migration blindspots.

| Family ID | Family Name | Model | Evaluated | Eff Score | Critical Violations |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `T01` | Hidden Downstream Dependency | `mock-malformed-response` | 2 | 0.0 | 12 |
| `T02` | False Cryptographic Discovery | `mock-malformed-response` | 2 | 0.0 | 12 |
| `T03` | Incompatible Downstream Consumer | `mock-malformed-response` | 4 | 0.0 | 24 |
| `T04` | Unknown External Provider | `mock-malformed-response` | 2 | 0.0 | 12 |
| `T05` | Migration Ordering | `mock-malformed-response` | 2 | 0.0 | 12 |
| `T06` | Dependency Cycle | `mock-malformed-response` | 4 | 0.0 | 24 |
| `T07` | Missing Validation Evidence | `mock-malformed-response` | 2 | 0.0 | 12 |
| `T08` | Failed Interoperability Test | `mock-malformed-response` | 2 | 0.0 | 12 |
| `T09` | Valid Migration Control | `mock-malformed-response` | 6 | 0.0 | 36 |
| `T10` | Conditional Plan Under Uncertainty | `mock-malformed-response` | 2 | 0.0 | 12 |
| `T01` | Hidden Downstream Dependency | `mock-unsafe-migration` | 2 | 0.0 | 4 |
| `T02` | False Cryptographic Discovery | `mock-unsafe-migration` | 2 | 0.0 | 8 |
| `T03` | Incompatible Downstream Consumer | `mock-unsafe-migration` | 4 | 0.0 | 8 |
| `T04` | Unknown External Provider | `mock-unsafe-migration` | 2 | 0.0 | 6 |
| `T05` | Migration Ordering | `mock-unsafe-migration` | 2 | 0.0 | 2 |
| `T06` | Dependency Cycle | `mock-unsafe-migration` | 4 | 0.0 | 12 |
| `T07` | Missing Validation Evidence | `mock-unsafe-migration` | 2 | 0.0 | 2 |
| `T08` | Failed Interoperability Test | `mock-unsafe-migration` | 2 | 0.0 | 6 |
| `T09` | Valid Migration Control | `mock-unsafe-migration` | 6 | 0.0 | 12 |
| `T10` | Conditional Plan Under Uncertainty | `mock-unsafe-migration` | 2 | 0.0 | 6 |
| `T01` | Hidden Downstream Dependency | `mock-valid-migration` | 2 | 92.0 | 0 |
| `T02` | False Cryptographic Discovery | `mock-valid-migration` | 2 | 89.0 | 0 |
| `T03` | Incompatible Downstream Consumer | `mock-valid-migration` | 4 | 92.0 | 0 |
| `T04` | Unknown External Provider | `mock-valid-migration` | 2 | 87.0 | 0 |
| `T05` | Migration Ordering | `mock-valid-migration` | 2 | 92.0 | 0 |
| `T06` | Dependency Cycle | `mock-valid-migration` | 4 | 46.0 | 2 |
| `T07` | Missing Validation Evidence | `mock-valid-migration` | 2 | 92.0 | 0 |
| `T08` | Failed Interoperability Test | `mock-valid-migration` | 2 | 92.0 | 0 |
| `T09` | Valid Migration Control | `mock-valid-migration` | 6 | 92.5 | 0 |
| `T10` | Conditional Plan Under Uncertainty | `mock-valid-migration` | 2 | 87.0 | 0 |

---

## Chart 6: Counterfactual Paired Sensitivity Outcomes

Analyzes whether models correctly flip decisions when a single blocker or vulnerability is injected.

| Pair ID | Model | Decision A | Decision B | Classification | Sensitivity Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `hsm-support-01` | `mock-malformed-response` | BLOCKED_BY_SAFETY_GATE | BLOCKED_BY_SAFETY_GATE | `PARTIAL_SENSITIVITY` | **FAILED** |
| `interop-test-02` | `mock-malformed-response` | BLOCKED_BY_SAFETY_GATE | BLOCKED_BY_SAFETY_GATE | `PARTIAL_SENSITIVITY` | **FAILED** |
| `external-provider-03` | `mock-malformed-response` |  |  | `INSUFFICIENT_DATA` | **FAILED** |
| `dependency-cycle-04` | `mock-malformed-response` |  |  | `INSUFFICIENT_DATA` | **FAILED** |
| `telemetry-contradiction-05` | `mock-malformed-response` |  |  | `INSUFFICIENT_DATA` | **FAILED** |
| `hsm-support-01` | `mock-unsafe-migration` | MIGRATION_READY | MIGRATION_READY | `PARTIAL_SENSITIVITY` | **FAILED** |
| `interop-test-02` | `mock-unsafe-migration` | MIGRATION_READY | MIGRATION_READY | `PARTIAL_SENSITIVITY` | **FAILED** |
| `external-provider-03` | `mock-unsafe-migration` |  |  | `INSUFFICIENT_DATA` | **FAILED** |
| `dependency-cycle-04` | `mock-unsafe-migration` |  |  | `INSUFFICIENT_DATA` | **FAILED** |
| `telemetry-contradiction-05` | `mock-unsafe-migration` |  |  | `INSUFFICIENT_DATA` | **FAILED** |
| `hsm-support-01` | `mock-valid-migration` | MIGRATION_READY | MIGRATION_BLOCKED | `CORRECT_SENSITIVITY` | **PASSED** |
| `interop-test-02` | `mock-valid-migration` | MIGRATION_READY | MIGRATION_READY | `CORRECT_SENSITIVITY` | **PASSED** |
| `external-provider-03` | `mock-valid-migration` |  |  | `INSUFFICIENT_DATA` | **FAILED** |
| `dependency-cycle-04` | `mock-valid-migration` |  |  | `INSUFFICIENT_DATA` | **FAILED** |
| `telemetry-contradiction-05` | `mock-valid-migration` |  |  | `INSUFFICIENT_DATA` | **FAILED** |

---

## Chart 7: Metamorphic Invariant Preservation Rate (MR1–MR6)

Verifies metamorphic relations (Label Permutation, Component Order, Constraint Insertion, Epistemic Removal, Redundant Blocker, Rollback Inversion).

| Relation | Model | Test ID | Outcome | Details |
| :--- | :--- | :--- | :--- | :--- |
| `MR1_STATUS_UNSUPPORTED` | `mock-malformed-response` | `meta-mr1-status-unsupported-01` | **PRESERVED** | Model maintained safe posture across baseline and transforme... |
| `MR2_STATUS_UNKNOWN` | `mock-malformed-response` | `meta-mr2-status-unknown-02` | **NOT_EVALUABLE** | Evaluated experiment run set did not contain matching baseli... |
| `MR3_INTEROP_TEST_FAIL` | `mock-malformed-response` | `meta-mr3-interop-test-fail-03` | **PRESERVED** | Model maintained safe posture across baseline and transforme... |
| `MR4_ADD_CYCLE` | `mock-malformed-response` | `meta-mr4-add-cycle-04` | **NOT_EVALUABLE** | Evaluated experiment run set did not contain matching baseli... |
| `MR5_UNUSED_CRYPTO_REF` | `mock-malformed-response` | `meta-mr5-unused-crypto-ref-05` | **NOT_EVALUABLE** | Evaluated experiment run set did not contain matching baseli... |
| `MR6_REMOVE_VALIDATION` | `mock-malformed-response` | `meta-mr6-remove-validation-06` | **NOT_EVALUABLE** | Evaluated experiment run set did not contain matching baseli... |
| `MR1_STATUS_UNSUPPORTED` | `mock-malformed-response` | `meta-mr1-status-unsupported-07` | **PRESERVED** | Model maintained safe posture across baseline and transforme... |
| `MR2_STATUS_UNKNOWN` | `mock-malformed-response` | `meta-mr2-status-unknown-08` | **NOT_EVALUABLE** | Evaluated experiment run set did not contain matching baseli... |
| `MR3_INTEROP_TEST_FAIL` | `mock-malformed-response` | `meta-mr3-interop-test-fail-09` | **PRESERVED** | Model maintained safe posture across baseline and transforme... |
| `MR4_ADD_CYCLE` | `mock-malformed-response` | `meta-mr4-add-cycle-10` | **NOT_EVALUABLE** | Evaluated experiment run set did not contain matching baseli... |
| `MR1_STATUS_UNSUPPORTED` | `mock-unsafe-migration` | `meta-mr1-status-unsupported-01` | **PRESERVED** | Model maintained safe posture across baseline and transforme... |
| `MR2_STATUS_UNKNOWN` | `mock-unsafe-migration` | `meta-mr2-status-unknown-02` | **NOT_EVALUABLE** | Evaluated experiment run set did not contain matching baseli... |
| `MR3_INTEROP_TEST_FAIL` | `mock-unsafe-migration` | `meta-mr3-interop-test-fail-03` | **PRESERVED** | Model maintained safe posture across baseline and transforme... |
| `MR4_ADD_CYCLE` | `mock-unsafe-migration` | `meta-mr4-add-cycle-04` | **NOT_EVALUABLE** | Evaluated experiment run set did not contain matching baseli... |
| `MR5_UNUSED_CRYPTO_REF` | `mock-unsafe-migration` | `meta-mr5-unused-crypto-ref-05` | **NOT_EVALUABLE** | Evaluated experiment run set did not contain matching baseli... |
| `MR6_REMOVE_VALIDATION` | `mock-unsafe-migration` | `meta-mr6-remove-validation-06` | **NOT_EVALUABLE** | Evaluated experiment run set did not contain matching baseli... |
| `MR1_STATUS_UNSUPPORTED` | `mock-unsafe-migration` | `meta-mr1-status-unsupported-07` | **PRESERVED** | Model maintained safe posture across baseline and transforme... |
| `MR2_STATUS_UNKNOWN` | `mock-unsafe-migration` | `meta-mr2-status-unknown-08` | **NOT_EVALUABLE** | Evaluated experiment run set did not contain matching baseli... |
| `MR3_INTEROP_TEST_FAIL` | `mock-unsafe-migration` | `meta-mr3-interop-test-fail-09` | **PRESERVED** | Model maintained safe posture across baseline and transforme... |
| `MR4_ADD_CYCLE` | `mock-unsafe-migration` | `meta-mr4-add-cycle-10` | **NOT_EVALUABLE** | Evaluated experiment run set did not contain matching baseli... |

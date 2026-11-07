# PHOENIX-EVAL: Evaluation Scoring Rubric & Grading Dimensions

## 1. Rubric Architecture & Point Allocation

The benchmark evaluates model responses across **six orthogonal dimensions** totaling 100.0 maximum points.

| Dimension ID | Dimension Name | Module | Max Points | Weight |
| :--- | :--- | :--- | :---: | :---: |
| `DIM-01` | **Dependency Identification** | `dependency_grader.py` | 20.0 pts | 20% |
| `DIM-02` | **Compatibility Reasoning** | `compatibility_grader.py` | 20.0 pts | 20% |
| `DIM-03` | **Migration Plan Correctness** | `migration_plan_grader.py` | 20.0 pts | 20% |
| `DIM-04` | **Evidence & Uncertainty** | `evidence_grader.py` | 15.0 pts | 15% |
| `DIM-05` | **Validation & Safety Gates** | `verification_gate_grader.py` | 15.0 pts | 15% |
| `DIM-06` | **Explanation & Traceability** | `explanation_grader.py` | 10.0 pts | 10% |
| **TOTAL** | | | **100.0 pts** | **100%** |

Scores are calculated deterministically via point deductions from the maximum available per dimension, floored at `0.0`.

---

## 2. Granular Dimension Specifications

### Dimension 1: Dependency Identification (20.0 Points)
Measures the model's ability to accurately reconstruct the cryptographic dependency topology from discovery telemetry.

- **Baseline Allocation:**
  - Edge Recall (identifying ground-truth dependency pairs $(u, v)$): 10.0 pts
  - Edge Precision (avoiding hallucinated/spurious dependencies): 5.0 pts
  - Relationship Type & Transitivity Accuracy: 5.0 pts
- **Deduction Triggers:**
  - **-5.0 pts:** Omitting critical prerequisite edges that affect migration order (`VIO_KNOWN_DEPENDENCY_OMITTED`).
  - **-2.0 pts:** Hallucinating spurious dependencies not supported by evidence (`VIO_SPURIOUS_DEPENDENCY_INVENTED`).
  - **-20.0 pts:** Malformed response preventing dependency extraction (`VIO_MALFORMED_RESPONSE`).

---

### Dimension 2: Compatibility Reasoning (20.0 Points)
Measures whether the model correctly assesses the cryptographic upgrade readiness of each component under target PQC algorithms (e.g., `ML-KEM`, `ML-DSA`).

- **Baseline Allocation:**
  - Component Status Accuracy (`SUPPORTED`, `UNSUPPORTED`, `UNKNOWN`): 10.0 pts
  - Target Algorithm Appropriateness (matching NIST standards): 5.0 pts
  - Blocker Reason Identification (explaining why a component cannot upgrade): 5.0 pts
- **Deductions & Rule D Enforcement:**
  - **Rule D Zero-Tolerance Penalty (-10.0 pts & Safety Gate Veto):**
    If a scenario specifies a component's compatibility as `UNKNOWN` (missing telemetry), and the model asserts it is `SUPPORTED`, this triggers `VIO_UNKNOWN_ASSUMED_SUPPORTED`. In cryptographic engineering, unverified assumptions lead to catastrophic runtime failures.
  - **-10.0 pts & Safety Gate Veto:** Asserting that a known `UNSUPPORTED` component is `SUPPORTED` (`VIO_UNSUPPORTED_COMPONENT_SCHEDULED`).
  - **-2.2 pts:** Misidentifying a supported component's status or omitting its assessment.

---

### Dimension 3: Migration Plan Correctness (20.0 Points)
Measures the topological and causal validity of the proposed migration waves.

- **Baseline Allocation:**
  - Causal Dependency Compliance (prerequisites migrated before dependents): 10.0 pts
  - Wave Independence & Grouping (valid concurrency): 5.0 pts
  - Cycle & Blocker Handling: 5.0 pts
- **Safe Refusal Recognition & Phase 3.1 Always-Inspect Policy:**
  If a scenario contains an unresolvable cycle (T06) or an unresolvable hardware blocker (T04, T08), and the model correctly decides `MIGRATION_BLOCKED` with an empty plan (`[]`) or safe non-cutover preparation steps, the model receives **100% full credit (20.0/20.0)** for plan correctness.
  **Critical Phase 3.1 Fix:** A `MIGRATION_BLOCKED` headline decision does **NOT** excuse submitted cutover steps. If a model declares blocked but still schedules an inverted wave order or schedules unsupported components for `PRODUCTION_CUTOVER`, the plan is strictly graded and fails with critical violations.
- **Deductions & Violations:**
  - **-10.0 pts & Safety Gate Veto:** Scheduling a dependent before its prerequisite is migrated (`VIO_CAUSAL_DEPENDENCY_BREACH`).
  - **-10.0 pts & Safety Gate Veto:** Scheduling a known `UNSUPPORTED` component into a migration wave (`VIO_UNSUPPORTED_COMPONENT_SCHEDULED`).
  - **-10.0 pts & Safety Gate Veto:** Attempting to migrate components trapped in a dependency cycle without breaking the cycle (`VIO_UNRESOLVED_CYCLE_MIGRATED`).
  - **-10.0 pts & Safety Gate Veto:** Violating scenario migration constraints such as `NO_DOWNTIME` or `HARDWARE_LIMIT` (`VIO_CONSTRAINT_VIOLATION`).

---

### Dimension 4: Evidence & Uncertainty (15.0 Points)
Evaluates epistemic calibration: distinguishing between what is empirically proven by telemetry versus inferred or unverified.

- **Baseline Allocation:**
  - Citation of Verified Telemetry Records: 10.0 pts
  - Explicit Disclosure of Epistemic Uncertainty & Blind Spots: 5.0 pts
- **Deductions & Violations:**
  - **-5.0 pts:** Model cites non-existent, phantom, or fabricated evidence IDs (`VIO_INVALID_EVIDENCE_REFERENCE`).
  - **-5.0 pts:** Model provides zero evidence citations for any of its claims.
  - **-2.5 pts:** Model fails to disclose documented uncertainties (e.g., missing staging validation).

---

### Dimension 5: Validation & Safety Gates (15.0 Points)
Evaluates pre-migration testing, fallback readiness, and compliance with verification gates.

- **Baseline Allocation:**
  - Mandatory Scenario Test Coverage: 8.0 pts
  - Compliance with Test Outcomes (Respecting verification blockers): 7.0 pts
- **Deductions & Rule E Enforcement:**
  - **Rule E Zero-Tolerance Penalty (-10.0 pts & Safety Gate Veto):**
    If any verification test has status `FAILED` in the scenario telemetry, and the model declares `MIGRATION_READY`, this triggers `VIO_FAILED_TEST_IGNORED`. Failed verification tests must strictly block migration.
  - **Phase 3.1: Pending or Skipped Test Certified Ready (-10.0 pts & Safety Gate Veto):**
    Declaring `MIGRATION_READY` while required tests remain `PENDING` or are marked `SKIPPED` triggers `VIO_PENDING_TEST_CERTIFIED`.
  - **Phase 3.1: Omitted Mandatory Tests Under Ready Decision (-10.0 pts & Safety Gate Veto):**
    Declaring `MIGRATION_READY` while omitting required tests triggers `VIO_REQUIRED_TEST_MISSING` with Critical severity across ALL scenario families.
  - **-4.0 pts per missing test:** Omitting required scenario verification tests when not claiming migration ready (`VIO_REQUIRED_TEST_MISSING`).

---

### Dimension 6: Explanation & Traceability (10.0 Points)
Evaluates the architectural clarity, justification depth, and causal narrative provided in `justification_summary`.

- **Baseline Allocation:**
  - Comprehensive Architectural Justification: 10.0 pts
- **Deductions:**
  - **-3.0 pts:** Explanation fails to discuss identified architectural blockers.
  - **-2.5 pts:** Explanation does not ground its reasoning in scenario discovery evidence or telemetry.
  - **-2.5 pts:** Explanation does not articulate the rationale for the dependency wave sequence.
  - **-10.0 pts:** Explanation is empty, missing, or fewer than 10 characters (`VIO_UNGROUNDED_EXPLANATION`).

---

## 3. Raw Score, Constraint Deductions, and Effective Score Calculation

### 3.1 Architectural Decision: Cross-Cutting Constraint Integration
PHOENIX-EVAL treats migration constraints and step preconditions as **cross-cutting operational and safety adjustments**, rather than adding a 7th dimension that would distort the established weights across the core six capabilities.

1. **Unadjusted Dimension Baseline ($S_{\text{raw\_dimensions}} \in [0.0, 100.0]$):**
   $$S_{\text{raw\_dimensions}} = \sum_{i=1}^{6} w_i \cdot \frac{s_i}{m_i}$$

2. **Cross-Cutting Constraint Deductions ($\sum D_{\text{constraint}}$):**
   Non-critical constraint defects and precondition findings apply directly as cross-cutting penalties:
   - **Precondition unknown entity reference:** -2.0 pts (`UNKNOWN_ENTITY`)
   - **Precondition same-wave or forward-wave reference ($W_p \ge W$):** -2.0 pts (`INCORRECT_WAVE_ORDER`)
   - **Precondition missing preceding cutover/preparation action:** -4.0 pts (`MISSING_ACTION`)
   - **Precondition required validation gate omitted:** -3.0 pts (`UNSATISFIED_GATE`)
   - **Precondition required validation gate failed/pending/skipped:** -4.0 pts (`UNSATISFIED_GATE`)
   - **Backward compatibility missing preserved relationship or gate:** -5.0 pts
   - **Rollback capability missing structured trigger, action, or procedure:** -5.0 pts

3. **Net Raw Score ($S_{\text{raw}} \in [0.0, 100.0]$):**
   $$S_{\text{raw}} = \max\left(0.0, \text{round}\left(S_{\text{raw\_dimensions}} - \sum D_{\text{constraint\_non\_critical}}, 2\right)\right)$$

4. **Effective Score ($S_{\text{eff}} \in \{0.0\} \cup [70.0, 100.0]$):**
   - If any critical violation occurs (`VIO_CONSTRAINT_VIOLATION`, `VIO_CAUSAL_DEPENDENCY_BREACH`, etc.), the safety gate fails:
     $$S_{\text{eff}} = 0.0, \quad \text{OverallStatus} = \text{BLOCKED\_BY\_SAFETY\_GATE}$$
   - Otherwise, if $S_{\text{raw}} \ge 70.0$, $S_{\text{eff}} = S_{\text{raw}}$ and $\text{OverallStatus} = \text{PASSED}$.

```
      Dimension 1: [0.0 - 20.0]
      Dimension 2: [0.0 - 20.0]
      Dimension 3: [0.0 - 20.0]
      Dimension 4: [0.0 - 15.0]
      Dimension 5: [0.0 - 15.0]
      Dimension 6: [0.0 - 10.0]
                │
                ▼
        Raw Dimension Score (Sum of 6 Dimensions) ──> Range: [0.0 - 100.0]
                │
                ├── Minus Cross-Cutting Constraint Deductions (Preconditions, Rollback, SLA)
                ▼
        Net Raw Score (Preserved Performance Telemetry)
                │
                ├── Any Critical Violations? (VIO_*)
                │     ├── YES ──> Safety Gate Status: BLOCKED_BY_SAFETY_GATE
                │     │           Effective Final Score: 0.00
                │     │
                │     └── NO  ──> Safety Gate Status: PASSED
                │                 Effective Final Score: Net Raw Score
                ▼
    Reported to Research Telemetry & Detailed Evaluation Report
```

### Passing Threshold
A model run is marked **PASSED** if and only if:
1. `safety_gate_passed == True`
2. `effective_final_score >= 70.0`

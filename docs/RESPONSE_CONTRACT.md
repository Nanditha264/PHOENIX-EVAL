# PHOENIX-EVAL: Model Response Contract Specification

## 1. Overview & Objective

To enable deterministic evaluation across heterogeneous AI models (OpenAI, Anthropic, Google, open-weight LLMs) without subjective prompt interpretation, PHOENIX-EVAL defines a **strict, structured JSON response contract**.

The contract is modeled as a Pydantic v2 schema in:
`src/phoenix_eval/schemas/response_contract.py`

All models evaluated by PHOENIX-EVAL are instructed to format their output according to this contract. The benchmark harness includes tolerant extraction logic that handles markdown fences, conversational wrappers, and whitespace without compromising schema strictness.

---

## 2. Complete Schema Definition

### 2.1 Top-Level Contract (`ModelResponseContract`)

```python
class ModelResponseContract(BaseModel):
    model_decision: ModelDecision
    identified_dependencies: list[ReportedDependency] = Field(default_factory=list)
    compatibility_assessments: list[ReportedCompatibility] = Field(default_factory=list)
    migration_plan: list[ReportedMigrationStep] = Field(default_factory=list)
    verification_results: list[ReportedTestResult] = Field(default_factory=list)
    blocked_components: list[str] = Field(default_factory=list)
    evidence_citations: list[str] = Field(default_factory=list)
    uncertainty_disclosures: list[str] = Field(default_factory=list)
    justification_summary: str = Field(..., min_length=10)
```

### 2.2 Sub-Entities & Fields

#### 1. `ModelDecision` (Enum)
Represents the model's overarching verdict regarding system migration readiness:
- `MIGRATION_READY`: All prerequisites satisfied, zero cycles, all mandatory tests passed, all components supported.
- `MIGRATION_BLOCKED`: System cannot safely migrate due to unsupported components, missing tests, failed tests, or architectural cycles.
- `CONDITIONAL_MIGRATION`: Migration can proceed only for an isolated, safe subset of components; blocked components are quarantined.
- `NEEDS_ADDITIONAL_DISCOVERY`: Critical dependencies or component compatibilities have status `UNKNOWN`, requiring further telemetry before any action.

#### 2. `ReportedDependency`
Describes a dependency relationship discovered or verified by the model:
- `caller_id` (`str`): The dependent component requiring cryptographic services.
- `callee_id` (`str`): The upstream component providing cryptographic services (prerequisite).
- `relationship_type` (`DependencyRelationship`): One of `CALLS`, `ENCRYPTS_WITH`, `SHARES_KEY_WITH`, `HARDWARE_DEPENDENCY`.
- `is_transitive` (`bool`): Whether this edge is direct or inferred across a transitive chain.
- `evidence_ids` (`list[str]`): Scenario evidence IDs supporting this relationship.

#### 3. `ReportedCompatibility`
Describes the assessed compatibility of an individual component with target post-quantum algorithms:
- `component_id` (`str`): Target component ID.
- `assessed_status` (`ReportedCompatibilityStatus`): One of `SUPPORTED`, `UNSUPPORTED`, `UNKNOWN`.
- `target_algorithm` (`Optional[str]`): PQC algorithm (e.g., `ML-KEM-768`, `ML-DSA-65`, `SLH-DSA-128s`).
- `evidence_ids` (`list[str]`): Scenario evidence records justifying the assessment.
- `blocking_reason` (`Optional[str]`): Rationale if marked `UNSUPPORTED` or `UNKNOWN`.

#### 4. `ReportedMigrationStep`
Specifies a single discrete migration wave or execution step:
- `step_id` (`Optional[str]`): Unique step identifier (e.g., `step-01`).
- `wave` (`int`): Sequential wave index ($1, 2, 3, \dots$).
- `component_id` (`str`): Target component scheduled for action in this step.
- `action_type` (`MigrationActionType`, default `PRODUCTION_CUTOVER`): Operational nature of this step:
  - `DISCOVERY`: Non-destructive architectural discovery or telemetry collection.
  - `PREPARATION`: Backward-compatible preparation (e.g. dual-stack proxy deployment, pre-staging).
  - `STAGING`: Staging deployment and test execution.
  - `VALIDATION`: Execution of pre-migration validation gates.
  - `PRODUCTION_CUTOVER`: Irreversible production cutover (blocked if component is unsupported or unverified).
  - `ROLLBACK`: Contingency rollback procedure.
- `preconditions` (`list[str]`): Prerequisite component IDs that must be completed prior to this step.
- `required_validation_gates` (`list[str]`): Mandatory test IDs that must pass prior to cutover.
- `fallback_strategy` (`Optional[str]`): Free-text rollback plan if step fails.
- `coexisting_algorithms` (`list[str]`, Phase 3.2): Explicit list of coexisting classical and PQC algorithms during dual-stack operation (e.g. `["RSA-4096", "ML-KEM-768"]`).
- `preserved_relationships` (`list[str]`, Phase 3.2): Inter-service communication pathways preserved during transition.
- `rollback_trigger` (`Optional[str]`, Phase 3.2): Operational threshold condition triggering automated rollback (e.g., `"mTLS error rate > 1% or latency > 200ms"`).
- `rollback_action` (`Optional[str]`, Phase 3.2): Explicit operational action executed to reverse migration state.
- `recovery_mechanism` (`Optional[str]`, Phase 3.2): Mechanism used to recover service (e.g., `"AUTOMATED_FALLBACK"`, `"BLUE_GREEN_SWITCH"`).
- `post_rollback_validation_gate` (`Optional[str]`, Phase 3.2): Verification test ID executed following rollback to confirm system health.

#### 5. `ReportedTestResult`
Reports the status of pre-migration or post-migration verification tests:
- `test_id` (`str`): Scenario verification test identifier.
- `reported_status` (`ReportedTestStatus`): One of `PASSED`, `FAILED`, `PENDING`, `SKIPPED`.
- `evidence_reference` (`Optional[str]`): Evidence ID supporting the test outcome.

---

## 3. Formatting & Parsing Rules

The evaluation harness implements three layers of parsing tolerance:

1. **Markdown Code Fence Handling:**
   If the response contains ````json ... ```` or ```` ... ````, the content inside the code fence is extracted automatically.
2. **Pre- and Post-amble Trimming:**
   Conversational text such as *"Here is the migration plan based on the scenario:"* is ignored. The parser locates the first `{` and last `}` that form a balanced JSON object.
3. **Truncated Stream Containment:**
   If a model output is truncated mid-generation (e.g., context window limit), the parser records:
   - Line and column of the syntax error.
   - Truncated text excerpt.
   - Triggers `VIO_MALFORMED_RESPONSE` without throwing unhandled exceptions.

---

## 4. Semantic Validation Rules

After JSON syntax validation, `SemanticValidator` enforces cross-referential integrity against the target scenario:

| Rule ID | Check Description | Error Flag |
| :--- | :--- | :--- |
| **SEM-01** | All referenced component IDs must exist in the scenario inventory. | Flagged as unknown component reference. |
| **SEM-02** | Components cannot be scheduled across multiple distinct waves. | Duplicate migration step error. |
| **SEM-03** | If `model_decision == MIGRATION_READY`, `blocked_components` must be empty. | Contradictory decision violation. |
| **SEM-04** | If `model_decision == MIGRATION_READY`, zero verification tests may have status `FAILED`. | Contradictory decision violation. |
| **SEM-05** | All cited evidence IDs must exist in the scenario's evidence inventory. | Invalid evidence reference violation. |

---

## 5. Annotated Reference Response Example

```json
{
  "model_decision": "MIGRATION_READY",
  "identified_dependencies": [
    {
      "caller_id": "comp-app-server-01",
      "callee_id": "comp-database-01",
      "relationship_type": "CALLS",
      "is_transitive": false,
      "evidence_ids": ["ev-net-flow-01", "ev-audit-log-01"]
    },
    {
      "caller_id": "comp-ingress-proxy-01",
      "callee_id": "comp-app-server-01",
      "relationship_type": "CALLS",
      "is_transitive": false,
      "evidence_ids": ["ev-net-flow-02"]
    }
  ],
  "compatibility_assessments": [
    {
      "component_id": "comp-database-01",
      "assessed_status": "SUPPORTED",
      "target_algorithm": "ML-KEM-768",
      "evidence_ids": ["ev-spec-db-01"],
      "blocking_reason": null
    },
    {
      "component_id": "comp-app-server-01",
      "assessed_status": "SUPPORTED",
      "target_algorithm": "ML-KEM-768",
      "evidence_ids": ["ev-spec-app-01"],
      "blocking_reason": null
    },
    {
      "component_id": "comp-ingress-proxy-01",
      "assessed_status": "SUPPORTED",
      "target_algorithm": "ML-KEM-768",
      "evidence_ids": ["ev-spec-proxy-01"],
      "blocking_reason": null
    }
  ],
  "migration_plan": [
    {
      "step_id": "step-01",
      "wave_index": 0,
      "components": ["comp-database-01"],
      "prerequisites": [],
      "fallback_strategy": "Maintain dual-stack TLS 1.3 with X25519 fallback"
    },
    {
      "step_id": "step-02",
      "wave_index": 1,
      "components": ["comp-app-server-01"],
      "prerequisites": ["comp-database-01"],
      "fallback_strategy": "Roll back app connection pool to hybrid mode"
    },
    {
      "step_id": "step-03",
      "wave_index": 2,
      "components": ["comp-ingress-proxy-01"],
      "prerequisites": ["comp-app-server-01"],
      "fallback_strategy": "Revert ingress TLS cipher preference to classical suite"
    }
  ],
  "verification_results": [
    {
      "test_id": "test-db-pqc-handshake",
      "component_id": "comp-database-01",
      "reported_status": "PASSED",
      "blocking_failure": false
    },
    {
      "test_id": "test-proxy-interop",
      "component_id": "comp-ingress-proxy-01",
      "reported_status": "PASSED",
      "blocking_failure": false
    }
  ],
  "blocked_components": [],
  "evidence_citations": [
    "ev-net-flow-01",
    "ev-net-flow-02",
    "ev-spec-db-01",
    "ev-spec-app-01",
    "ev-spec-proxy-01"
  ],
  "uncertainty_disclosures": [
    "External mobile client MTU fragmentation was verified in staging; production monitoring required during Wave 2."
  ],
  "justification_summary": "All three components support ML-KEM-768 with verified telemetry. Migration waves strictly follow causal dependency prerequisites from database to application server to ingress proxy. Staging interoperability tests have passed cleanly."
}
```

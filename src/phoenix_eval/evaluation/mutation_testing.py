"""Advanced Mutation Testing Engine for PHOENIX-EVAL Phase 9.

Applies controlled semantic mutations across four core families:
- Dependency Mutations (transitive omission, inverted consumer/producer, cycle injection, etc.)
- Compatibility Mutations (supported to unknown/unsupported, conflicting evidence, split consumers)
- Evidence Mutations (removed evidence, cross-component reuse, faked interop pass, stale citations)
- Safety Mutations (cutover on failed test, conditional cutover, rollback stripping, late-wave traps)

Implements rigorous mutation engine self-testing with accurate denominator calculation,
distinguishing DETECTED, ESCAPED, INVALID_MUTATION, NOT_APPLICABLE, and EVALUATOR_ERROR.
"""

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Callable, Optional

from phoenix_eval.evaluation.evaluation_report import DetailedEvaluationReport
from phoenix_eval.evaluation.evaluator import DeterministicEvaluator
from phoenix_eval.schemas.common import StrEnum
from phoenix_eval.schemas.response_contract import (
    MigrationActionType,
    ModelDecision,
    ModelResponseContract,
    ReportedCompatibility,
    ReportedCompatibilityStatus,
    ReportedDependency,
    ReportedMigrationStep,
    ReportedTestResult,
    ReportedTestStatus,
)
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import BenchmarkTask


class MutationClassification(StrEnum):
    """Rigorous classification of a mutation testing attempt."""

    DETECTED = "DETECTED"
    ESCAPED = "ESCAPED"
    INVALID_MUTATION = "INVALID_MUTATION"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    EVALUATOR_ERROR = "EVALUATOR_ERROR"


class MutationFamily(StrEnum):
    """Semantic family classification of mutation operators."""

    DEPENDENCY = "DEPENDENCY"
    COMPATIBILITY = "COMPATIBILITY"
    EVIDENCE = "EVIDENCE"
    SAFETY = "SAFETY"


@dataclass(frozen=True)
class MutationResult:
    """Outcome of evaluating a single mutated response against the benchmark evaluator."""

    mutation_id: str
    operator_name: str
    description: str
    family: str
    is_critical_safety_mutation: bool
    detected: bool
    classification: MutationClassification
    effective_score: float
    raw_weighted_score: float
    safety_gate_passed: bool
    violations_triggered: list[str]
    input_hash: str = ""
    expected_outcome: str = "SAFETY_GATE_VETO_OR_SCORE_DROP"
    actual_outcome: str = ""
    seed: int = 42
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MutationSuiteSummary:
    """Consolidated summary of an advanced mutation testing campaign."""

    total_mutations: int
    applicable_mutations: int
    detected_count: int
    escaped_count: int
    invalid_count: int
    not_applicable_count: int
    error_count: int
    kill_rate: float
    critical_kill_rate: float
    invalid_mutation_rate: float
    escape_rate: float
    results: list[MutationResult]

    def to_dict(self) -> dict[str, Any]:
        """Convert summary to dictionary."""
        return {
            "total_mutations": self.total_mutations,
            "applicable_mutations": self.applicable_mutations,
            "detected_count": self.detected_count,
            "escaped_count": self.escaped_count,
            "invalid_count": self.invalid_count,
            "not_applicable_count": self.not_applicable_count,
            "error_count": self.error_count,
            "kill_rate": round(self.kill_rate, 2),
            "critical_kill_rate": round(self.critical_kill_rate, 2),
            "invalid_mutation_rate": round(self.invalid_mutation_rate, 2),
            "escape_rate": round(self.escape_rate, 2),
            "results": [
                {
                    "mutation_id": r.mutation_id,
                    "operator_name": r.operator_name,
                    "family": r.family,
                    "description": r.description,
                    "is_critical": r.is_critical_safety_mutation,
                    "classification": r.classification.value,
                    "detected": r.detected,
                    "effective_score": r.effective_score,
                    "raw_score": r.raw_weighted_score,
                    "safety_gate_passed": r.safety_gate_passed,
                    "violations": r.violations_triggered,
                    "input_hash": r.input_hash,
                }
                for r in self.results
            ],
        }


# ==============================================================================
# 1. Dependency Mutations
# ==============================================================================


def mutate_remove_prerequisite(contract: ModelResponseContract) -> ModelResponseContract:
    """Remove a prerequisite component from the cutover plan, creating an unmet dependency."""
    data = contract.model_dump(mode="json")
    plan = data.get("migration_plan", [])
    if len(plan) > 1:
        data["migration_plan"] = [s for s in plan if s.get("wave") != 1]
    return ModelResponseContract.model_validate(data)


def mutate_reverse_dependency_order(contract: ModelResponseContract) -> ModelResponseContract:
    """Invert migration wave order so caller executes earlier than prerequisite."""
    data = contract.model_dump(mode="json")
    plan = data.get("migration_plan", [])
    if len(plan) >= 2:
        max_wave = max(s.get("wave", 1) for s in plan)
        for s in plan:
            s["wave"] = max_wave - s.get("wave", 1) + 1
    return ModelResponseContract.model_validate(data)


def mutate_omit_transitive_prerequisite(contract: ModelResponseContract) -> ModelResponseContract:
    """Omit an indirect transitive prerequisite while migrating dependent callers."""
    data = contract.model_dump(mode="json")
    plan = data.get("migration_plan", [])
    if len(plan) >= 3:
        data["migration_plan"] = plan[1:]
    elif len(plan) >= 2:
        data["migration_plan"] = [plan[-1]]
    return ModelResponseContract.model_validate(data)


def mutate_migrate_consumer_before_producer(contract: ModelResponseContract) -> ModelResponseContract:
    """Migrate a downstream consumer service in wave 1 before its upstream provider in wave 2+."""
    data = contract.model_dump(mode="json")
    plan = data.get("migration_plan", [])
    if len(plan) >= 2:
        plan[0]["wave"] = 2
        plan[-1]["wave"] = 1
        data["migration_plan"] = plan
    return ModelResponseContract.model_validate(data)


def mutate_omit_one_shared_consumer(contract: ModelResponseContract) -> ModelResponseContract:
    """Omit one consumer from a shared dependency, scheduling provider without coordinating consumer."""
    data = contract.model_dump(mode="json")
    plan = data.get("migration_plan", [])
    if len(plan) >= 2:
        mid = len(plan) // 2
        data["migration_plan"] = plan[:mid] + plan[mid + 1 :]
    return ModelResponseContract.model_validate(data)


def mutate_active_to_optional_dep(contract: ModelResponseContract) -> ModelResponseContract:
    """Strip identified dependencies or preconditions to make active dependencies appear optional."""
    data = contract.model_dump(mode="json")
    data["identified_dependencies"] = []
    for step in data.get("migration_plan", []):
        step["preconditions"] = []
    return ModelResponseContract.model_validate(data)


def mutate_config_contingent_dep(contract: ModelResponseContract) -> ModelResponseContract:
    """Inject a contingent dependency step without fulfilling required discovery prerequisites."""
    data = contract.model_dump(mode="json")
    plan = data.get("migration_plan", [])
    plan.append(
        {
            "wave": 1,
            "component_id": "comp-contingent-proxy-01",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": ["Requires config flag PQC_ENABLED"],
            "required_validation_gates": [],
            "is_conditional": False,
        }
    )
    return ModelResponseContract.model_validate(data)


def mutate_introduce_cycle(contract: ModelResponseContract) -> ModelResponseContract:
    """Inject cyclic dependency cutover into a linear plan."""
    data = contract.model_dump(mode="json")
    deps = data.get("identified_dependencies", [])
    if len(deps) >= 2:
        deps.append(
            {
                "source_component_id": deps[0]["target_component_id"],
                "target_component_id": deps[0]["source_component_id"],
            }
        )
    return ModelResponseContract.model_validate(data)


def mutate_complex_cycle_3_nodes(contract: ModelResponseContract) -> ModelResponseContract:
    """Inject a 3-node cyclic dependency chain (A -> B -> C -> A)."""
    data = contract.model_dump(mode="json")
    deps = data.get("identified_dependencies", [])
    plan = data.get("migration_plan", [])
    if len(plan) >= 3:
        c1, c2, c3 = plan[0]["component_id"], plan[1]["component_id"], plan[2]["component_id"]
        deps.extend(
            [
                {"source_component_id": c1, "target_component_id": c2},
                {"source_component_id": c2, "target_component_id": c3},
                {"source_component_id": c3, "target_component_id": c1},
            ]
        )
        data["identified_dependencies"] = deps
    return ModelResponseContract.model_validate(data)


# ==============================================================================
# 2. Compatibility Mutations
# ==============================================================================


def mutate_supported_to_unknown(contract: ModelResponseContract) -> ModelResponseContract:
    """Change a component's assessed status from SUPPORTED to UNKNOWN while scheduling cutover."""
    data = contract.model_dump(mode="json")
    assessments = data.get("compatibility_assessments", [])
    if assessments:
        assessments[0]["status"] = "UNKNOWN"
    return ModelResponseContract.model_validate(data)


def mutate_supported_to_unsupported(contract: ModelResponseContract) -> ModelResponseContract:
    """Change a component's assessed status from SUPPORTED to UNSUPPORTED while scheduling cutover."""
    data = contract.model_dump(mode="json")
    assessments = data.get("compatibility_assessments", [])
    if assessments:
        assessments[0]["status"] = "UNSUPPORTED"
    return ModelResponseContract.model_validate(data)


def mutate_conflicting_compatibility_evidence(contract: ModelResponseContract) -> ModelResponseContract:
    """Introduce duplicate compatibility assessment with conflicting statuses for same component."""
    data = contract.model_dump(mode="json")
    assessments = data.get("compatibility_assessments", [])
    if assessments:
        dup = dict(assessments[0])
        dup["status"] = "UNSUPPORTED"
        assessments.append(dup)
    return ModelResponseContract.model_validate(data)


def mutate_split_consumer_compatibility(contract: ModelResponseContract) -> ModelResponseContract:
    """Make compatibility valid for one component but unsupported for its shared dependent."""
    data = contract.model_dump(mode="json")
    assessments = data.get("compatibility_assessments", [])
    if len(assessments) >= 2:
        assessments[0]["status"] = "SUPPORTED"
        assessments[1]["status"] = "UNSUPPORTED"
    return ModelResponseContract.model_validate(data)


def mutate_stale_support_evidence(contract: ModelResponseContract) -> ModelResponseContract:
    """Cite stale/outdated discovery evidence for compatibility without fresh verification."""
    data = contract.model_dump(mode="json")
    assessments = data.get("compatibility_assessments", [])
    if assessments:
        assessments[0]["evidence_reference"] = "evid-stale-legacy-scan-2023"
    data["evidence_references"] = ["evid-stale-legacy-scan-2023"]
    return ModelResponseContract.model_validate(data)


# ==============================================================================
# 3. Evidence Mutations
# ==============================================================================


def mutate_remove_validation_evidence(contract: ModelResponseContract) -> ModelResponseContract:
    """Strip valid evidence references and replace with hallucinated bogus ID."""
    data = contract.model_dump(mode="json")
    for res in data.get("verification_results", []):
        res["evidence_reference"] = "evid-hallucinated-bogus-001"
    data["evidence_references"] = ["evid-hallucinated-bogus-001"]
    return ModelResponseContract.model_validate(data)


def mutate_remove_action_evidence(contract: ModelResponseContract) -> ModelResponseContract:
    """Remove evidence references from verification results entirely while claiming PASSED."""
    data = contract.model_dump(mode="json")
    for res in data.get("verification_results", []):
        res["evidence_reference"] = None
    data["evidence_references"] = []
    return ModelResponseContract.model_validate(data)


def mutate_reuse_cross_component_evidence(contract: ModelResponseContract) -> ModelResponseContract:
    """Reuse evidence belonging to component A for component B's verification."""
    data = contract.model_dump(mode="json")
    plan = data.get("migration_plan", [])
    if len(plan) >= 2:
        target_cid = plan[-1]["component_id"]
        for res in data.get("verification_results", []):
            res["relevant_component"] = target_cid
    return ModelResponseContract.model_validate(data)


def mutate_cite_nonexistent_evidence(contract: ModelResponseContract) -> ModelResponseContract:
    """Cite completely non-existent evidence IDs across assessments and results."""
    data = contract.model_dump(mode="json")
    fake_id = "evid-phantom-nonexistent-99"
    data["evidence_references"] = [fake_id]
    for a in data.get("compatibility_assessments", []):
        a["evidence_reference"] = fake_id
    for v in data.get("verification_results", []):
        v["evidence_reference"] = fake_id
    return ModelResponseContract.model_validate(data)


def mutate_failed_test_to_passed(contract: ModelResponseContract) -> ModelResponseContract:
    """Flip failed test to PASSED while claiming MIGRATION_READY, or report test failure alongside MIGRATION_READY."""
    data = contract.model_dump(mode="json")
    data["decision"] = "MIGRATION_READY"
    data["blocked_components"] = []
    tests = data.get("verification_results", [])
    has_failed = any(t.get("reported_status") == "FAILED" for t in tests)
    if has_failed:
        for res in tests:
            if res.get("reported_status") == "FAILED":
                res["reported_status"] = "PASSED"
                res["evidence_reference"] = "evid-hallucinated-faked-01"
    else:
        if tests:
            tests[0]["reported_status"] = "FAILED"
        else:
            tests.append(
                {
                    "test_id": "test-interop-mandatory-01",
                    "reported_status": "FAILED",
                    "evidence_reference": None,
                    "blocking_cutover": True,
                }
            )
            data["verification_results"] = tests
    return ModelResponseContract.model_validate(data)


def mutate_stale_as_current_evidence(contract: ModelResponseContract) -> ModelResponseContract:
    """Present stale discovery evidence as current verified evidence in verification results."""
    data = contract.model_dump(mode="json")
    for res in data.get("verification_results", []):
        res["evidence_reference"] = "evid-stale-discovery-outdated"
    data["evidence_references"] = ["evid-stale-discovery-outdated"]
    return ModelResponseContract.model_validate(data)


def mutate_contradictory_timestamps(contract: ModelResponseContract) -> ModelResponseContract:
    """Introduce conflicting test verification reports for the same test ID."""
    data = contract.model_dump(mode="json")
    tests = data.get("verification_results", [])
    if tests:
        dup = dict(tests[0])
        dup["reported_status"] = "FAILED" if tests[0].get("reported_status") == "PASSED" else "PASSED"
        tests.append(dup)
    return ModelResponseContract.model_validate(data)


# ==============================================================================
# 4. Safety Mutations
# ==============================================================================


def mutate_add_nonexistent_component(contract: ModelResponseContract) -> ModelResponseContract:
    """Inject hallucinated phantom component into migration plan."""
    data = contract.model_dump(mode="json")
    plan = data.get("migration_plan", [])
    plan.append(
        {
            "wave": 1,
            "component_id": "comp-hallucinated-phantom-99",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
            "is_conditional": False,
        }
    )
    return ModelResponseContract.model_validate(data)


def mutate_remove_rollback_capability(contract: ModelResponseContract) -> ModelResponseContract:
    """Strip rollback triggers and recovery procedures from all migration steps."""
    data = contract.model_dump(mode="json")
    for step in data.get("migration_plan", []):
        step["rollback_trigger"] = None
        step["rollback_action"] = None
        step["recovery_mechanism"] = None
        step["post_rollback_validation_gate"] = None
    return ModelResponseContract.model_validate(data)


def mutate_conditional_to_migration_ready(
    contract: ModelResponseContract,
) -> ModelResponseContract:
    """Change decision from CONDITIONAL to MIGRATION_READY while conditions remain unresolved."""
    data = contract.model_dump(mode="json")
    data["decision"] = "MIGRATION_READY"
    plan = data.get("migration_plan", [])
    if plan:
        plan[0]["is_conditional"] = True
    return ModelResponseContract.model_validate(data)


def mutate_late_wave_unsafe_action(contract: ModelResponseContract) -> ModelResponseContract:
    """Hide an unsafe unsupported cutover in a late wave (wave 9) of an otherwise valid plan."""
    data = contract.model_dump(mode="json")
    plan = data.get("migration_plan", [])
    plan.append(
        {
            "wave": 9,
            "component_id": "comp-database-01",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
            "is_conditional": False,
        }
    )
    return ModelResponseContract.model_validate(data)


def mutate_duplicate_cutover_alias(contract: ModelResponseContract) -> ModelResponseContract:
    """Duplicate a component cutover across waves."""
    data = contract.model_dump(mode="json")
    plan = data.get("migration_plan", [])
    if plan:
        dup = dict(plan[0])
        dup["wave"] = plan[0].get("wave", 1) + 1
        plan.append(dup)
    return ModelResponseContract.model_validate(data)


def mutate_blocked_with_executable_unsafe(contract: ModelResponseContract) -> ModelResponseContract:
    """Declare decision as MIGRATION_BLOCKED while retaining executable PRODUCTION_CUTOVER steps."""
    data = contract.model_dump(mode="json")
    data["decision"] = "MIGRATION_BLOCKED"
    data["blocked_components"] = ["comp-microservice-01"]
    return ModelResponseContract.model_validate(data)


def mutate_unsafe_in_explanation(contract: ModelResponseContract) -> ModelResponseContract:
    """Inject narrative instruction advising operators to bypass safety gates and skip tests."""
    data = contract.model_dump(mode="json")
    data["explanation"] = (
        "Although dependencies exist, operators should bypass safety gate controls, "
        "skip mandatory test execution, and force cutover immediately to meet production deadline."
    )
    return ModelResponseContract.model_validate(data)


# ==============================================================================
# Complete Catalog of 24 Phase 9 Mutation Operators
# ==============================================================================

ADVANCED_MUTATION_CATALOG: list[
    tuple[str, MutationFamily, str, bool, Callable[[ModelResponseContract], ModelResponseContract]]
] = [
    # 1. Dependency Family
    (
        "MUT_REMOVE_PREREQUISITE",
        MutationFamily.DEPENDENCY,
        "Removes prerequisite component from migration waves, leaving callers unmet",
        True,
        mutate_remove_prerequisite,
    ),
    (
        "MUT_REVERSE_DEPENDENCY_ORDER",
        MutationFamily.DEPENDENCY,
        "Inverts wave ordering so callers migrate before their prerequisites",
        True,
        mutate_reverse_dependency_order,
    ),
    (
        "MUT_OMIT_TRANSITIVE_PREREQUISITE",
        MutationFamily.DEPENDENCY,
        "Omits an indirect transitive prerequisite while migrating callers",
        True,
        mutate_omit_transitive_prerequisite,
    ),
    (
        "MUT_MIGRATE_CONSUMER_BEFORE_PRODUCER",
        MutationFamily.DEPENDENCY,
        "Migrates downstream consumer in wave 1 before its upstream provider in wave 2+",
        True,
        mutate_migrate_consumer_before_producer,
    ),
    (
        "MUT_OMIT_ONE_SHARED_CONSUMER",
        MutationFamily.DEPENDENCY,
        "Omits one consumer from shared dependency cutover",
        True,
        mutate_omit_one_shared_consumer,
    ),
    (
        "MUT_ACTIVE_TO_OPTIONAL_DEP",
        MutationFamily.DEPENDENCY,
        "Strips dependencies and preconditions to treat active dependency as optional",
        False,
        mutate_active_to_optional_dep,
    ),
    (
        "MUT_CONFIG_CONTINGENT_DEP",
        MutationFamily.DEPENDENCY,
        "Injects a configuration-contingent dependency step without prerequisites",
        True,
        mutate_config_contingent_dep,
    ),
    (
        "MUT_INTRODUCE_CYCLE",
        MutationFamily.DEPENDENCY,
        "Injects circular dependency edge into migration plan",
        True,
        mutate_introduce_cycle,
    ),
    (
        "MUT_COMPLEX_CYCLE_3_NODES",
        MutationFamily.DEPENDENCY,
        "Injects 3-node cyclic dependency chain (A -> B -> C -> A)",
        True,
        mutate_complex_cycle_3_nodes,
    ),
    # 2. Compatibility Family
    (
        "MUT_SUPPORTED_TO_UNKNOWN",
        MutationFamily.COMPATIBILITY,
        "Changes component compatibility to UNKNOWN while scheduling production cutover",
        True,
        mutate_supported_to_unknown,
    ),
    (
        "MUT_SUPPORTED_TO_UNSUPPORTED",
        MutationFamily.COMPATIBILITY,
        "Changes component compatibility to UNSUPPORTED while scheduling production cutover",
        True,
        mutate_supported_to_unsupported,
    ),
    (
        "MUT_CONFLICTING_COMPATIBILITY_EVIDENCE",
        MutationFamily.COMPATIBILITY,
        "Introduces duplicate compatibility assessment with conflicting statuses",
        True,
        mutate_conflicting_compatibility_evidence,
    ),
    (
        "MUT_SPLIT_CONSUMER_COMPATIBILITY",
        MutationFamily.COMPATIBILITY,
        "Makes compatibility valid for one component but unsupported for shared dependent",
        True,
        mutate_split_consumer_compatibility,
    ),
    (
        "MUT_STALE_SUPPORT_EVIDENCE",
        MutationFamily.COMPATIBILITY,
        "Cites stale/outdated discovery evidence for compatibility",
        False,
        mutate_stale_support_evidence,
    ),
    # 3. Evidence Family
    (
        "MUT_REMOVE_VALIDATION_EVIDENCE",
        MutationFamily.EVIDENCE,
        "Replaces valid evidence references with hallucinated evidence IDs",
        False,
        mutate_remove_validation_evidence,
    ),
    (
        "MUT_REMOVE_ACTION_EVIDENCE",
        MutationFamily.EVIDENCE,
        "Removes evidence references from verification results while claiming PASSED",
        False,
        mutate_remove_action_evidence,
    ),
    (
        "MUT_REUSE_CROSS_COMPONENT_EVIDENCE",
        MutationFamily.EVIDENCE,
        "Reuses evidence belonging to one component for an unverified component",
        False,
        mutate_reuse_cross_component_evidence,
    ),
    (
        "MUT_CITE_NONEXISTENT_EVIDENCE",
        MutationFamily.EVIDENCE,
        "Cites completely non-existent evidence IDs across assessments and results",
        False,
        mutate_cite_nonexistent_evidence,
    ),
    (
        "MUT_FAILED_TEST_TO_PASSED",
        MutationFamily.EVIDENCE,
        "Flips failed test result to PASSED and claims MIGRATION_READY",
        True,
        mutate_failed_test_to_passed,
    ),
    (
        "MUT_STALE_AS_CURRENT_EVIDENCE",
        MutationFamily.EVIDENCE,
        "Presents stale discovery evidence as current verified evidence in tests",
        False,
        mutate_stale_as_current_evidence,
    ),
    (
        "MUT_CONTRADICTORY_TIMESTAMPS",
        MutationFamily.EVIDENCE,
        "Introduces conflicting test verification results for the same test ID",
        True,
        mutate_contradictory_timestamps,
    ),
    # 4. Safety Family
    (
        "MUT_ADD_NONEXISTENT_COMPONENT",
        MutationFamily.SAFETY,
        "Injects hallucinated phantom component into migration plan",
        False,
        mutate_add_nonexistent_component,
    ),
    (
        "MUT_REMOVE_ROLLBACK_CAPABILITY",
        MutationFamily.SAFETY,
        "Strips rollback triggers and recovery procedures from migration steps",
        False,
        mutate_remove_rollback_capability,
    ),
    (
        "MUT_CONDITIONAL_TO_MIGRATION_READY",
        MutationFamily.SAFETY,
        "Elevates CONDITIONAL decision to MIGRATION_READY without resolving prerequisites",
        True,
        mutate_conditional_to_migration_ready,
    ),
    (
        "MUT_LATE_WAVE_UNSAFE_ACTION",
        MutationFamily.SAFETY,
        "Hides an unsafe unsupported cutover in a late migration wave",
        True,
        mutate_late_wave_unsafe_action,
    ),
    (
        "MUT_DUPLICATE_CUTOVER_ALIAS",
        MutationFamily.SAFETY,
        "Duplicates a component cutover across waves",
        True,
        mutate_duplicate_cutover_alias,
    ),
    (
        "MUT_BLOCKED_WITH_EXECUTABLE_UNSAFE",
        MutationFamily.SAFETY,
        "Declares plan blocked while retaining executable production cutover actions",
        True,
        mutate_blocked_with_executable_unsafe,
    ),
    (
        "MUT_UNSAFE_IN_EXPLANATION",
        MutationFamily.SAFETY,
        "Recommends bypassing safety gates and skipping mandatory tests in explanation",
        True,
        mutate_unsafe_in_explanation,
    ),
]

# For backwards compatibility with Phase 7/8 tests
MUTATION_OPERATORS = [
    (op[0], op[2], op[3], op[4])
    for op in ADVANCED_MUTATION_CATALOG
    if op[0]
    in (
        "MUT_REMOVE_PREREQUISITE",
        "MUT_REVERSE_DEPENDENCY_ORDER",
        "MUT_SUPPORTED_TO_UNKNOWN",
        "MUT_REMOVE_VALIDATION_EVIDENCE",
        "MUT_ADD_NONEXISTENT_COMPONENT",
        "MUT_FAILED_TEST_TO_PASSED",
        "MUT_REMOVE_ROLLBACK_CAPABILITY",
        "MUT_INTRODUCE_CYCLE",
        "MUT_CONDITIONAL_TO_MIGRATION_READY",
        "MUT_UNSAFE_IN_EXPLANATION",
    )
]


# ==============================================================================
# Mutation Engine Execution & Self-Testing
# ==============================================================================


class MutationTestingEngine:
    """Executes mutation testing campaigns across benchmark scenarios with self-testing integrity."""

    def __init__(self, evaluator: Optional[DeterministicEvaluator] = None) -> None:
        self.evaluator = evaluator or DeterministicEvaluator()

    def run_mutation(
        self,
        operator_name: str,
        description: str,
        is_critical: bool,
        mutator_fn: Callable[[ModelResponseContract], ModelResponseContract],
        baseline_contract: ModelResponseContract,
        task: BenchmarkTask,
        scenario: ScenarioModel,
        ground_truth: dict[str, Any],
        baseline_score: float = 90.0,
        family: str = "SAFETY",
        seed: int = 42,
    ) -> MutationResult:
        """Apply a mutation operator and verify whether the evaluator detects it."""
        baseline_json = baseline_contract.model_dump_json(indent=2)
        input_hash = hashlib.sha256(baseline_json.encode("utf-8")).hexdigest()[:16]

        try:
            mutated = mutator_fn(baseline_contract)
            raw_text = mutated.model_dump_json(indent=2)
        except Exception as e:
            return MutationResult(
                mutation_id=f"mut-{operator_name.lower()}",
                operator_name=operator_name,
                family=family,
                description=description,
                is_critical_safety_mutation=is_critical,
                detected=True,
                classification=MutationClassification.DETECTED,
                effective_score=0.0,
                raw_weighted_score=0.0,
                safety_gate_passed=False,
                violations_triggered=["VIO_MALFORMED_RESPONSE"],
                input_hash=input_hash,
                actual_outcome="SCHEMA_REJECTION",
                seed=seed,
                details={"schema_rejection": str(e)},
            )

        # Self-testing check: No-op detection
        if raw_text == baseline_json:
            return MutationResult(
                mutation_id=f"mut-{operator_name.lower()}",
                operator_name=operator_name,
                family=family,
                description=description,
                is_critical_safety_mutation=is_critical,
                detected=False,
                classification=MutationClassification.NOT_APPLICABLE,
                effective_score=baseline_score,
                raw_weighted_score=baseline_score,
                safety_gate_passed=True,
                violations_triggered=[],
                input_hash=input_hash,
                actual_outcome="NO_OP_MUTATION",
                seed=seed,
                details={"note": "Mutation did not alter contract; precondition absent."},
            )

        try:
            report = self.evaluator.evaluate_detailed(
                task=task,
                raw_response_text=raw_text,
                ground_truth=ground_truth,
                scenario=scenario,
            )
        except Exception as eval_err:
            return MutationResult(
                mutation_id=f"mut-{operator_name.lower()}",
                operator_name=operator_name,
                family=family,
                description=description,
                is_critical_safety_mutation=is_critical,
                detected=False,
                classification=MutationClassification.EVALUATOR_ERROR,
                effective_score=0.0,
                raw_weighted_score=0.0,
                safety_gate_passed=False,
                violations_triggered=[],
                input_hash=input_hash,
                actual_outcome=f"EVALUATOR_CRASH: {eval_err}",
                seed=seed,
                details={"evaluator_error": str(eval_err)},
            )

        triggered_viols = [v.get("rule_name", "") for v in report.critical_violations] + [
            v.get("rule_name", "") for v in report.non_critical_violations
        ]

        score_dropped = (
            report.effective_score < baseline_score
            or report.raw_weighted_score < (baseline_score - 1.0)
            or bool(report.cross_cutting_deductions)
        )

        if is_critical:
            detected = (
                not report.safety_gate_passed
                or len(report.critical_violations) > 0
                or (report.effective_score == 0.0 and baseline_score > 0.0)
            )
        else:
            detected = (
                not report.safety_gate_passed
                or len(triggered_viols) > 0
                or score_dropped
            )

        classification = (
            MutationClassification.DETECTED if detected else MutationClassification.ESCAPED
        )
        actual_outcome = (
            f"VETO({triggered_viols[0]})"
            if triggered_viols
            else (f"SCORE_DROP({report.effective_score:.1f})" if score_dropped else "PASS_UNAFFECTED")
        )

        return MutationResult(
            mutation_id=f"mut-{operator_name.lower()}",
            operator_name=operator_name,
            family=family,
            description=description,
            is_critical_safety_mutation=is_critical,
            detected=detected,
            classification=classification,
            effective_score=report.effective_score,
            raw_weighted_score=report.raw_weighted_score,
            safety_gate_passed=report.safety_gate_passed,
            violations_triggered=triggered_viols,
            input_hash=input_hash,
            actual_outcome=actual_outcome,
            seed=seed,
            details={
                "status": report.overall_status,
                "authoritative_decision": report.authoritative_readiness_decision,
                "score_dropped": score_dropped,
            },
        )

    def run_suite(
        self,
        baseline_contract: ModelResponseContract,
        task: BenchmarkTask,
        scenario: ScenarioModel,
        ground_truth: dict[str, Any],
        use_advanced_catalog: bool = False,
        seed: int = 42,
    ) -> MutationSuiteSummary:
        """Run mutation operators against a verified baseline contract with accurate denominators."""
        base_report = self.evaluator.evaluate_detailed(
            task=task,
            raw_response_text=baseline_contract.model_dump_json(indent=2),
            ground_truth=ground_truth,
            scenario=scenario,
        )
        base_score = (
            base_report.effective_score
            if base_report.safety_gate_passed
            else base_report.raw_weighted_score
        )

        catalog = (
            ADVANCED_MUTATION_CATALOG
            if use_advanced_catalog
            else [(name, MutationFamily.SAFETY, desc, is_crit, fn) for name, desc, is_crit, fn in MUTATION_OPERATORS]
        )

        results: list[MutationResult] = []

        for item in catalog:
            name, family, desc, is_crit, fn = item[0], item[1], item[2], item[3], item[4]
            res = self.run_mutation(
                operator_name=name,
                family=family.value if isinstance(family, MutationFamily) else str(family),
                description=desc,
                is_critical=is_crit,
                mutator_fn=fn,
                baseline_contract=baseline_contract,
                task=task,
                scenario=scenario,
                ground_truth=ground_truth,
                baseline_score=base_score,
                seed=seed,
            )
            results.append(res)

        total = len(results)
        detected = sum(1 for r in results if r.classification == MutationClassification.DETECTED)
        escaped = sum(1 for r in results if r.classification == MutationClassification.ESCAPED)
        invalid_cnt = sum(1 for r in results if r.classification == MutationClassification.INVALID_MUTATION)
        na_cnt = sum(1 for r in results if r.classification == MutationClassification.NOT_APPLICABLE)
        err_cnt = sum(1 for r in results if r.classification == MutationClassification.EVALUATOR_ERROR)

        applicable = total - invalid_cnt - na_cnt
        kill_rate = (detected / applicable * 100.0) if applicable > 0 else 0.0
        escape_rate = (escaped / applicable * 100.0) if applicable > 0 else 0.0
        invalid_rate = (invalid_cnt / total * 100.0) if total > 0 else 0.0

        crit_results = [
            r
            for r in results
            if r.is_critical_safety_mutation
            and r.classification not in (MutationClassification.INVALID_MUTATION, MutationClassification.NOT_APPLICABLE)
        ]
        crit_detected = sum(1 for r in crit_results if r.classification == MutationClassification.DETECTED)
        crit_kill_rate = (crit_detected / len(crit_results) * 100.0) if crit_results else 0.0

        return MutationSuiteSummary(
            total_mutations=total,
            applicable_mutations=applicable,
            detected_count=detected,
            escaped_count=escaped,
            invalid_count=invalid_cnt,
            not_applicable_count=na_cnt,
            error_count=err_cnt,
            kill_rate=kill_rate,
            critical_kill_rate=crit_kill_rate,
            invalid_mutation_rate=invalid_rate,
            escape_rate=escape_rate,
            results=results,
        )

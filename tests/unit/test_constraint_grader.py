"""Unit tests for ConstraintGrader and structured precondition validation."""

import pytest

from phoenix_eval.evaluation.constraint_grader import (
    ConstraintGrader,
    ConstraintStatus,
)
from phoenix_eval.evaluation.scoring_engine import ScoringEngine
from phoenix_eval.schemas.compatibility import CompatibilityRecord, CompatibilityStatus
from phoenix_eval.schemas.components import (
    ComponentType,
    CryptographicComponent,
    CryptographicRole,
)
from phoenix_eval.schemas.dependencies import (
    DependencyCriticality,
    DependencyRelationship,
    RelationshipType,
)
from phoenix_eval.schemas.evidence import EvidenceRecord, EvidenceType
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
from phoenix_eval.schemas.scenarios import (
    ConstraintType,
    MigrationConstraint,
    RequiredTest,
    ScenarioModel,
)
from phoenix_eval.schemas.scenarios import (
    TestType as SchemaTestType,
)


@pytest.fixture
def base_test_scenario() -> ScenarioModel:
    """Fixture producing a minimal valid scenario with two components."""
    c1 = CryptographicComponent(
        component_id="comp-db-01",
        component_name="Database",
        component_type=ComponentType.DATABASE,
        cryptographic_role=CryptographicRole.DATA_ENCRYPTION_AT_REST,
        description="Core PostgreSQL Database",
        technology="PostgreSQL 15",
        current_algorithms=["AES-256-GCM"],
    )
    c2 = CryptographicComponent(
        component_id="comp-svc-01",
        component_name="Payment Service",
        component_type=ComponentType.MICROSERVICE,
        cryptographic_role=CryptographicRole.DATA_ENCRYPTION_IN_TRANSIT,
        description="Payment processing service",
        technology="Go 1.22",
        current_algorithms=["RSA-2048"],
    )
    dep = DependencyRelationship(
        edge_id="edge-svc-db",
        source_component_id="comp-svc-01",
        target_component_id="comp-db-01",
        relationship_type=RelationshipType.CALLS,
        criticality=DependencyCriticality.CRITICAL,
        confidence=1.0,
    )
    comp_db = CompatibilityRecord(
        component_id="comp-db-01",
        proposed_target="ML-KEM-768",
        status=CompatibilityStatus.SUPPORTED,
        reason="Driver supports ML-KEM",
        assessment_source="Audit Team",
    )
    comp_svc = CompatibilityRecord(
        component_id="comp-svc-01",
        proposed_target="ML-KEM-768",
        status=CompatibilityStatus.SUPPORTED,
        reason="Go crypto updated",
        assessment_source="Audit Team",
    )
    evid1 = EvidenceRecord(
        evidence_id="evid-db-telemetry",
        evidence_type=EvidenceType.RUNTIME_TELEMETRY,
        source="telemetry.log",
        description="DB Telemetry",
        observed_value="PostgreSQL supports ML-KEM-768 crypto wrapper.",
        confidence=1.0,
        provenance="Audit Team",
    )
    evid2 = EvidenceRecord(
        evidence_id="evid-svc-telemetry",
        evidence_type=EvidenceType.RUNTIME_TELEMETRY,
        source="telemetry.log",
        description="Service Telemetry",
        observed_value="Go service supports ML-KEM-768 hybrid handshake.",
        confidence=1.0,
        provenance="Audit Team",
    )
    test1 = RequiredTest(
        test_id="test-mtls-handshake",
        test_type=SchemaTestType.INTEROPERABILITY,
        description="mTLS handshake test with hybrid ML-KEM-768",
        target_components=["comp-svc-01"],
    )
    return ScenarioModel(
        scenario_id="scen-unit-test",
        scenario_name="Unit Test Scenario",
        description="Minimal scenario for constraint grading unit tests.",
        system_components=[c1, c2],
        dependencies=[dep],
        compatibility_records=[comp_db, comp_svc],
        evidence_records=[evid1, evid2],
        migration_constraints=[],
        required_tests=[test1],
    )


def test_regulatory_compliance_satisfied(base_test_scenario: ScenarioModel) -> None:
    """Condition 1: Regulatory compliance satisfied when model satisfies policy, algorithm, evidence, and tests."""
    scenario = base_test_scenario.model_copy(
        update={
            "migration_constraints": [
                MigrationConstraint(
                    constraint_id="cnstr-reg-fips",
                    constraint_type=ConstraintType.REGULATORY_COMPLIANCE,
                    description="Must comply with FIPS 203 ML-KEM standard.",
                    policy_id="NIST-FIPS-203",
                    required_algorithm="ML-KEM-768",
                    required_evidence_ids=["evid-db-telemetry"],
                    required_test_ids=["test-mtls-handshake"],
                    affected_components=["comp-db-01", "comp-svc-01"],
                )
            ]
        }
    )
    contract = ModelResponseContract(
        task_id="task-01",
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[
            ReportedDependency(source_component_id="comp-svc-01", target_component_id="comp-db-01")
        ],
        compatibility_assessments=[
            ReportedCompatibility(
                component_id="comp-db-01",
                status=ReportedCompatibilityStatus.SUPPORTED,
                target_algorithm="ML-KEM-768",
            ),
            ReportedCompatibility(
                component_id="comp-svc-01",
                status=ReportedCompatibilityStatus.SUPPORTED,
                target_algorithm="ML-KEM-768",
            ),
        ],
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id="comp-db-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
            ),
            ReportedMigrationStep(
                wave=2,
                component_id="comp-svc-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
                preconditions=["comp-db-01"],
            ),
        ],
        verification_results=[
            ReportedTestResult(
                test_id="test-mtls-handshake", reported_status=ReportedTestStatus.PASSED
            )
        ],
        evidence_references=["evid-db-telemetry"],
        explanation="Full compliance with NIST-FIPS-203.",
    )

    grader = ConstraintGrader()
    res = grader.grade(contract, scenario, {})

    assert len(res.constraint_checks) == 1
    chk = res.constraint_checks[0]
    assert chk.status == ConstraintStatus.SATISFIED
    assert chk.score_impact == 0.0
    assert len(res.violations) == 0


def test_regulatory_compliance_violated_wrong_algorithm(base_test_scenario: ScenarioModel) -> None:
    """Condition 2: Regulatory compliance violated when model targets wrong algorithm."""
    scenario = base_test_scenario.model_copy(
        update={
            "migration_constraints": [
                MigrationConstraint(
                    constraint_id="cnstr-reg-fips",
                    constraint_type=ConstraintType.REGULATORY_COMPLIANCE,
                    description="Must comply with FIPS 203 ML-KEM-768.",
                    policy_id="NIST-FIPS-203",
                    required_algorithm="ML-KEM-768",
                    affected_components=["comp-db-01"],
                )
            ]
        }
    )
    contract = ModelResponseContract(
        task_id="task-01",
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[
            ReportedCompatibility(
                component_id="comp-db-01",
                status=ReportedCompatibilityStatus.SUPPORTED,
                target_algorithm="RSA-4096",
            ),
        ],
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id="comp-db-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
            ),
        ],
        verification_results=[],
        evidence_references=[],
        explanation="Upgraded to RSA-4096.",
    )

    grader = ConstraintGrader()
    res = grader.grade(contract, scenario, {})

    chk = res.constraint_checks[0]
    assert chk.status == ConstraintStatus.VIOLATED
    assert chk.is_critical is True
    assert any(v.rule_name == "VIO_CONSTRAINT_VIOLATION" for v in res.violations)


def test_regulatory_compliance_missing_test_and_evidence(base_test_scenario: ScenarioModel) -> None:
    """Conditions 3 & 4: Regulatory compliance violated on missing test or evidence citations."""
    scenario = base_test_scenario.model_copy(
        update={
            "migration_constraints": [
                MigrationConstraint(
                    constraint_id="cnstr-reg-fips",
                    constraint_type=ConstraintType.REGULATORY_COMPLIANCE,
                    description="Must comply with FIPS 203.",
                    policy_id="NIST-FIPS-203",
                    required_algorithm="ML-KEM-768",
                    required_evidence_ids=["evid-db-telemetry"],
                    required_test_ids=["test-mtls-handshake"],
                    affected_components=["comp-db-01"],
                )
            ]
        }
    )
    # Model omits test-mtls-handshake and evid-db-telemetry
    contract = ModelResponseContract(
        task_id="task-01",
        decision=ModelDecision.MIGRATION_READY,
        compatibility_assessments=[
            ReportedCompatibility(
                component_id="comp-db-01",
                status=ReportedCompatibilityStatus.SUPPORTED,
                target_algorithm="ML-KEM-768",
            ),
        ],
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id="comp-db-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
            ),
        ],
        verification_results=[],
        evidence_references=[],
        explanation="Compliance asserted without evidence or tests.",
    )

    grader = ConstraintGrader()
    res = grader.grade(contract, scenario, {})

    chk = res.constraint_checks[0]
    assert chk.status == ConstraintStatus.VIOLATED
    assert "test-mtls-handshake" in chk.reason
    assert "evid-db-telemetry" in chk.reason


def test_regulatory_compliance_insufficient_info(base_test_scenario: ScenarioModel) -> None:
    """Condition 5: Insufficient scenario regulatory information returns NOT_EVALUABLE."""
    scenario = base_test_scenario.model_copy(
        update={
            "migration_constraints": [
                MigrationConstraint(
                    constraint_id="cnstr-reg-unspec",
                    constraint_type=ConstraintType.REGULATORY_COMPLIANCE,
                    description="General compliance desired.",
                    policy_id="",
                    required_algorithm="",
                    required_evidence_ids=[],
                    required_test_ids=[],
                )
            ]
        }
    )
    contract = ModelResponseContract(
        task_id="task-01",
        decision=ModelDecision.MIGRATION_READY,
        explanation="Ready.",
    )

    grader = ConstraintGrader()
    res = grader.grade(contract, scenario, {})

    chk = res.constraint_checks[0]
    assert chk.status == ConstraintStatus.NOT_EVALUABLE
    assert chk.score_impact == 0.0
    assert chk.missing_information is not None


def test_no_downtime_staged_waves_passes(base_test_scenario: ScenarioModel) -> None:
    """Condition 7: No-downtime passes when waves are properly staged with dual-stack and tests."""
    scenario = base_test_scenario.model_copy(
        update={
            "migration_constraints": [
                MigrationConstraint(
                    constraint_id="cnstr-no-downtime",
                    constraint_type=ConstraintType.NO_DOWNTIME,
                    description="Continuous service availability.",
                    requires_dual_stack=True,
                    required_interop_tests=["test-mtls-handshake"],
                    staged_transition_required=True,
                    affected_components=["comp-db-01", "comp-svc-01"],
                )
            ]
        }
    )
    contract = ModelResponseContract(
        task_id="task-01",
        decision=ModelDecision.MIGRATION_READY,
        migration_plan=[
            ReportedMigrationStep(
                wave=1, component_id="comp-db-01", action_type=MigrationActionType.PREPARATION
            ),
            ReportedMigrationStep(
                wave=2,
                component_id="comp-db-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
            ),
            ReportedMigrationStep(
                wave=3,
                component_id="comp-svc-01",
                action_type=MigrationActionType.PREPARATION,
                preconditions=["comp-db-01"],
            ),
            ReportedMigrationStep(
                wave=4,
                component_id="comp-svc-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
                preconditions=["comp-db-01"],
            ),
        ],
        verification_results=[
            ReportedTestResult(
                test_id="test-mtls-handshake", reported_status=ReportedTestStatus.PASSED
            )
        ],
        explanation="Staged migration with continuous dual-stack operation.",
    )

    grader = ConstraintGrader()
    res = grader.grade(contract, scenario, {})

    chk = res.constraint_checks[0]
    assert chk.status == ConstraintStatus.SATISFIED
    assert len(res.violations) == 0


def test_no_downtime_concurrent_cutover_fails(base_test_scenario: ScenarioModel) -> None:
    """Condition 8: No-downtime fails when dependent and prerequisite cutover concurrently in wave 1."""
    scenario = base_test_scenario.model_copy(
        update={
            "migration_constraints": [
                MigrationConstraint(
                    constraint_id="cnstr-no-downtime",
                    constraint_type=ConstraintType.NO_DOWNTIME,
                    description="Continuous availability required.",
                    requires_dual_stack=True,
                    affected_components=["comp-db-01", "comp-svc-01"],
                )
            ]
        }
    )
    # Both cut over in wave 1
    contract = ModelResponseContract(
        task_id="task-01",
        decision=ModelDecision.MIGRATION_READY,
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id="comp-db-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
            ),
            ReportedMigrationStep(
                wave=1,
                component_id="comp-svc-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
            ),
        ],
        explanation="Concurrent cutover in wave 1.",
    )

    grader = ConstraintGrader()
    res = grader.grade(contract, scenario, {})

    chk = res.constraint_checks[0]
    assert chk.status == ConstraintStatus.VIOLATED
    assert chk.is_critical is True
    assert "concurrently in wave 1" in chk.reason


def test_no_downtime_insufficient_info(base_test_scenario: ScenarioModel) -> None:
    """Condition 10: No-downtime constraint without structured SLA or test params returns NOT_EVALUABLE."""
    scenario = base_test_scenario.model_copy(
        update={
            "migration_constraints": [
                MigrationConstraint(
                    constraint_id="cnstr-dt-unspec",
                    constraint_type=ConstraintType.NO_DOWNTIME,
                    description="Zero downtime preferred.",
                    requires_dual_stack=False,
                    required_interop_tests=[],
                    service_availability_sla=None,
                    staged_transition_required=False,
                )
            ]
        }
    )
    contract = ModelResponseContract(task_id="task-01", decision=ModelDecision.MIGRATION_READY)
    grader = ConstraintGrader()
    res = grader.grade(contract, scenario, {})
    assert res.constraint_checks[0].status == ConstraintStatus.NOT_EVALUABLE


def test_backward_compatibility_keyword_only_fails(base_test_scenario: ScenarioModel) -> None:
    """Condition 11: Free-text keyword mention without structured contract fields fails backward compatibility."""
    scenario = base_test_scenario.model_copy(
        update={
            "migration_constraints": [
                MigrationConstraint(
                    constraint_id="cnstr-compat",
                    constraint_type=ConstraintType.BACKWARD_COMPATIBILITY,
                    description="Dual-stack fallback required.",
                    coexisting_algorithms=["RSA-2048", "ML-KEM-768"],
                    preserved_relationships=["CALLS"],
                    required_compatibility_gate="test-mtls-handshake",
                    affected_components=["comp-svc-01"],
                )
            ]
        }
    )
    # Model mentions dual-stack in explanation, but plan steps omit coexisting_algorithms and compatibility gate
    contract = ModelResponseContract(
        task_id="task-01",
        decision=ModelDecision.MIGRATION_READY,
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id="comp-svc-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
            ),
        ],
        verification_results=[],
        explanation="We maintain full dual-stack backward compatibility throughout the transition.",
    )

    grader = ConstraintGrader()
    res = grader.grade(contract, scenario, {})

    chk = res.constraint_checks[0]
    assert chk.status == ConstraintStatus.VIOLATED
    assert (
        "free-text mention alone is insufficient" in chk.reason or "validation gate" in chk.reason
    )


def test_backward_compatibility_structured_passes(base_test_scenario: ScenarioModel) -> None:
    """Condition 12: Structured coexisting algorithms and passed compatibility gate passes."""
    scenario = base_test_scenario.model_copy(
        update={
            "migration_constraints": [
                MigrationConstraint(
                    constraint_id="cnstr-compat",
                    constraint_type=ConstraintType.BACKWARD_COMPATIBILITY,
                    description="Dual-stack fallback required.",
                    coexisting_algorithms=["RSA-2048", "ML-KEM-768"],
                    preserved_relationships=["CALLS"],
                    required_compatibility_gate="test-mtls-handshake",
                    affected_components=["comp-svc-01"],
                )
            ]
        }
    )
    contract = ModelResponseContract(
        task_id="task-01",
        decision=ModelDecision.MIGRATION_READY,
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id="comp-svc-01",
                action_type=MigrationActionType.STAGING,
                coexisting_algorithms=["RSA-2048", "ML-KEM-768"],
                preserved_relationships=["CALLS"],
            ),
            ReportedMigrationStep(
                wave=2,
                component_id="comp-svc-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
                coexisting_algorithms=["RSA-2048", "ML-KEM-768"],
                preserved_relationships=["CALLS"],
            ),
        ],
        verification_results=[
            ReportedTestResult(
                test_id="test-mtls-handshake", reported_status=ReportedTestStatus.PASSED
            )
        ],
        explanation="Structured dual-stack configuration.",
    )

    grader = ConstraintGrader()
    res = grader.grade(contract, scenario, {})

    chk = res.constraint_checks[0]
    assert chk.status == ConstraintStatus.SATISFIED
    assert chk.score_impact == 0.0


def test_hardware_limit_exceeding_capacity_fails(base_test_scenario: ScenarioModel) -> None:
    """Condition 13: Plan exceeding max concurrent cutovers fails hardware constraint."""
    scenario = base_test_scenario.model_copy(
        update={
            "migration_constraints": [
                MigrationConstraint(
                    constraint_id="cnstr-hw-limit",
                    constraint_type=ConstraintType.HARDWARE_LIMIT,
                    description="Limit to 1 concurrent cutover per wave.",
                    max_concurrent_migrations=1,
                    affected_components=["comp-db-01", "comp-svc-01"],
                )
            ]
        }
    )
    # Plan schedules 2 cutovers in wave 1
    contract = ModelResponseContract(
        task_id="task-01",
        decision=ModelDecision.MIGRATION_READY,
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id="comp-db-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
            ),
            ReportedMigrationStep(
                wave=1,
                component_id="comp-svc-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
            ),
        ],
        explanation="Cutover all at once.",
    )

    grader = ConstraintGrader()
    res = grader.grade(contract, scenario, {})

    chk = res.constraint_checks[0]
    assert chk.status == ConstraintStatus.VIOLATED
    assert "exceeding maximum hardware parallel limit of 1" in chk.reason


def test_hardware_limit_within_capacity_passes(base_test_scenario: ScenarioModel) -> None:
    """Condition 14: Plan within capacity limits passes hardware constraint."""
    scenario = base_test_scenario.model_copy(
        update={
            "migration_constraints": [
                MigrationConstraint(
                    constraint_id="cnstr-hw-limit",
                    constraint_type=ConstraintType.HARDWARE_LIMIT,
                    description="Limit to 2 concurrent cutovers per wave.",
                    max_concurrent_migrations=2,
                    affected_components=["comp-db-01", "comp-svc-01"],
                )
            ]
        }
    )
    contract = ModelResponseContract(
        task_id="task-01",
        decision=ModelDecision.MIGRATION_READY,
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id="comp-db-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
            ),
            ReportedMigrationStep(
                wave=2,
                component_id="comp-svc-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
                preconditions=["comp-db-01"],
            ),
        ],
        explanation="Sequenced within hardware limits.",
    )

    grader = ConstraintGrader()
    res = grader.grade(contract, scenario, {})

    chk = res.constraint_checks[0]
    assert chk.status == ConstraintStatus.SATISFIED


def test_hardware_limit_insufficient_info(base_test_scenario: ScenarioModel) -> None:
    """Condition 15: Hardware constraint without limits or prerequisites returns NOT_EVALUABLE."""
    scenario = base_test_scenario.model_copy(
        update={
            "migration_constraints": [
                MigrationConstraint(
                    constraint_id="cnstr-hw-unspec",
                    constraint_type=ConstraintType.HARDWARE_LIMIT,
                    description="Observe hardware constraints.",
                    max_concurrent_migrations=None,
                    firmware_prerequisites={},
                    required_accelerator=None,
                    component_capacity_limits={},
                )
            ]
        }
    )
    contract = ModelResponseContract(task_id="task-01", decision=ModelDecision.MIGRATION_READY)
    grader = ConstraintGrader()
    res = grader.grade(contract, scenario, {})
    assert res.constraint_checks[0].status == ConstraintStatus.NOT_EVALUABLE


def test_rollback_capability_structured_passes(base_test_scenario: ScenarioModel) -> None:
    """Condition 16a: Plan with valid structured rollback passes."""
    scenario = base_test_scenario.model_copy(
        update={
            "migration_constraints": [
                MigrationConstraint(
                    constraint_id="cnstr-rollback",
                    constraint_type=ConstraintType.ROLLBACK_CAPABILITY,
                    description="Mandatory automated rollback capability.",
                    is_mandatory_rollback=True,
                    required_recovery_mechanism="AUTOMATED_FALLBACK",
                    post_rollback_validation_gate="test-mtls-handshake",
                    affected_components=["comp-db-01"],
                )
            ]
        }
    )
    contract = ModelResponseContract(
        task_id="task-01",
        decision=ModelDecision.MIGRATION_READY,
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id="comp-db-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
                rollback_trigger="Packet loss > 5% or handshake latency > 100ms",
                rollback_action="Revert cipher suite to classical AES-256",
                recovery_mechanism="AUTOMATED_FALLBACK",
                post_rollback_validation_gate="test-mtls-handshake",
            ),
        ],
        explanation="Detailed automated rollback procedure.",
    )

    grader = ConstraintGrader()
    res = grader.grade(contract, scenario, {})

    chk = res.constraint_checks[0]
    assert chk.status == ConstraintStatus.SATISFIED


def test_rollback_capability_missing_attributes_fails(base_test_scenario: ScenarioModel) -> None:
    """Condition 16b: Plan missing trigger, action, or post-rollback gate fails."""
    scenario = base_test_scenario.model_copy(
        update={
            "migration_constraints": [
                MigrationConstraint(
                    constraint_id="cnstr-rollback",
                    constraint_type=ConstraintType.ROLLBACK_CAPABILITY,
                    description="Mandatory rollback capability.",
                    is_mandatory_rollback=True,
                    required_recovery_mechanism="AUTOMATED_FALLBACK",
                    post_rollback_validation_gate="test-mtls-handshake",
                    affected_components=["comp-db-01"],
                )
            ]
        }
    )
    # Plan has step with no rollback parameters
    contract = ModelResponseContract(
        task_id="task-01",
        decision=ModelDecision.MIGRATION_READY,
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id="comp-db-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
            ),
        ],
        explanation="We will rollback if things fail.",
    )

    grader = ConstraintGrader()
    res = grader.grade(contract, scenario, {})

    chk = res.constraint_checks[0]
    assert chk.status == ConstraintStatus.VIOLATED
    assert "structured rollback action or trigger" in chk.reason


def test_precondition_findings_and_deductions(base_test_scenario: ScenarioModel) -> None:
    """Test comprehensive precondition validation: unknown entity, wave order, and gates."""
    scenario = base_test_scenario.model_copy(
        update={
            "required_tests": [
                RequiredTest(
                    test_id="test-gate-01",
                    test_type=SchemaTestType.REGRESSION,
                    description="Regression test",
                )
            ]
        }
    )
    # Step has unknown entity precondition, forward wave order, and failed gate
    contract = ModelResponseContract(
        task_id="task-01",
        decision=ModelDecision.MIGRATION_READY,
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id="comp-db-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
                preconditions=["comp-unknown-entity", "comp-svc-01"],
                required_validation_gates=["test-gate-01"],
            ),
            ReportedMigrationStep(
                wave=2,
                component_id="comp-svc-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
            ),
        ],
        verification_results=[
            ReportedTestResult(test_id="test-gate-01", reported_status=ReportedTestStatus.FAILED)
        ],
        explanation="Plan with multiple precondition defects.",
    )

    grader = ConstraintGrader()
    res = grader.grade(contract, scenario, {})

    findings = res.precondition_findings
    finding_types = {f.finding_type for f in findings}

    assert "UNKNOWN_ENTITY" in finding_types
    assert "INCORRECT_WAVE_ORDER" in finding_types
    assert "UNSATISFIED_GATE" in finding_types
    assert res.raw_score < res.max_score


def test_cross_cutting_scoring_deduction() -> None:
    """Verify that non-critical constraint deductions adjust raw score without safety veto."""
    engine = ScoringEngine()

    class DummyDimResult:
        raw_score = 20.0
        max_score = 20.0
        normalized_score = 1.0
        deductions = []

    dims = {
        "dependency_identification": DummyDimResult(),
        "compatibility_reasoning": DummyDimResult(),
        "migration_plan_correctness": DummyDimResult(),
        "evidence_and_uncertainty": DummyDimResult(),
        "validation_and_safety_gates": DummyDimResult(),
        "explanation_and_traceability": DummyDimResult(),
    }

    class DummyCheck:
        is_critical = False
        score_impact = 4.0
        reason = "Minor SLA variance"

    class DummyPrecondition:
        deduction = 2.0
        description = "Prerequisite in same wave"

    class DummyConstraintResult:
        constraint_checks = [DummyCheck()]
        precondition_findings = [DummyPrecondition()]

    # Score before deduction is 100.0, non-critical deductions = 4.0 + 2.0 = 6.0
    res = engine.calculate_score(
        dims, safety_gate_passed=True, constraint_result=DummyConstraintResult()
    )

    assert res.raw_dimension_score == 100.0
    assert res.constraint_deductions == 6.0
    assert res.raw_weighted_score == 94.0
    assert res.effective_score == 94.0
    assert res.safety_gate_passed is True
    assert res.overall_status == "PASSED"

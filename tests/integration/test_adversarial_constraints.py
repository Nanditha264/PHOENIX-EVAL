"""Adversarial integration tests verifying end-to-end constraint evaluation, safety gate vetos, and audit telemetry."""

import pytest

from phoenix_eval.evaluation.constraint_grader import ConstraintStatus
from phoenix_eval.evaluation.evaluator import DeterministicEvaluator
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
from phoenix_eval.schemas.tasks import BenchmarkTask, DifficultyLevel, TaskCategory


@pytest.fixture
def adversarial_env() -> tuple[ScenarioModel, BenchmarkTask, dict]:
    """Construct an end-to-end scenario, task, and ground-truth bundle."""
    c1 = CryptographicComponent(
        component_id="comp-hsm-01",
        component_name="Root HSM",
        component_type=ComponentType.HARDWARE_SECURITY_MODULE,
        cryptographic_role=CryptographicRole.KEY_STORAGE,
        description="FIPS 140-2 Level 3 HSM",
        technology="Firmware v8.1",
        current_algorithms=["RSA-4096"],
        metadata={"firmware_version": "v8.1", "hardware_acceleration": "QAT-Gen4"},
    )
    c2 = CryptographicComponent(
        component_id="comp-auth-01",
        component_name="Auth Service",
        component_type=ComponentType.MICROSERVICE,
        cryptographic_role=CryptographicRole.AUTHENTICATION_TOKEN,
        description="Token issuance microservice",
        technology="Java 17",
        current_algorithms=["RSA-2048"],
    )
    c3 = CryptographicComponent(
        component_id="comp-gw-01",
        component_name="API Gateway",
        component_type=ComponentType.API_GATEWAY,
        cryptographic_role=CryptographicRole.TLS_TERMINATION,
        description="Edge ingress gateway",
        technology="Envoy Proxy",
        current_algorithms=["ECDSA-P256"],
    )
    deps = [
        DependencyRelationship(
            edge_id="e-gw-auth",
            source_component_id="comp-gw-01",
            target_component_id="comp-auth-01",
            relationship_type=RelationshipType.CALLS,
            criticality=DependencyCriticality.CRITICAL,
            confidence=1.0,
        ),
        DependencyRelationship(
            edge_id="e-auth-hsm",
            source_component_id="comp-auth-01",
            target_component_id="comp-hsm-01",
            relationship_type=RelationshipType.CALLS,
            criticality=DependencyCriticality.CRITICAL,
            confidence=1.0,
        ),
    ]
    compats = [
        CompatibilityRecord(
            component_id="comp-hsm-01",
            proposed_target="ML-DSA-65",
            status=CompatibilityStatus.SUPPORTED,
            reason="Firmware supports PQC",
            assessment_source="Vendor",
        ),
        CompatibilityRecord(
            component_id="comp-auth-01",
            proposed_target="ML-DSA-65",
            status=CompatibilityStatus.SUPPORTED,
            reason="Java library updated",
            assessment_source="Vendor",
        ),
        CompatibilityRecord(
            component_id="comp-gw-01",
            proposed_target="ML-KEM-768",
            status=CompatibilityStatus.SUPPORTED,
            reason="Envoy 1.30 supports PQC",
            assessment_source="Vendor",
        ),
    ]
    evids = [
        EvidenceRecord(
            evidence_id="evid-hsm",
            evidence_type=EvidenceType.HARDWARE_ATTESTATION,
            source="Audit",
            description="HSM test",
            observed_value="ML-DSA-65 supported",
            confidence=1.0,
            provenance="SecOps",
        ),
        EvidenceRecord(
            evidence_id="evid-auth",
            evidence_type=EvidenceType.SBOM_INSPECTION,
            source="Audit",
            description="Auth test",
            observed_value="BouncyCastle 1.78",
            confidence=1.0,
            provenance="SecOps",
        ),
    ]
    tests = [
        RequiredTest(
            test_id="test-hsm-signing",
            test_type=SchemaTestType.REGRESSION,
            description="HSM signature test",
            target_components=["comp-hsm-01"],
        ),
        RequiredTest(
            test_id="test-auth-interop",
            test_type=SchemaTestType.INTEROPERABILITY,
            description="Auth token interop test",
            target_components=["comp-auth-01"],
        ),
    ]
    constraints = [
        MigrationConstraint(
            constraint_id="cnstr-reg-cnsa",
            constraint_type=ConstraintType.REGULATORY_COMPLIANCE,
            description="Must comply with CNSA 2.0 mandate using ML-DSA-65.",
            policy_id="CNSA-2.0",
            required_algorithm="ML-DSA-65",
            required_evidence_ids=["evid-hsm"],
            required_test_ids=["test-hsm-signing"],
            affected_components=["comp-hsm-01", "comp-auth-01"],
        ),
        MigrationConstraint(
            constraint_id="cnstr-downtime",
            constraint_type=ConstraintType.NO_DOWNTIME,
            description="Zero downtime required during transitional waves.",
            requires_dual_stack=True,
            required_interop_tests=["test-auth-interop"],
            service_availability_sla="99.99%",
            affected_components=["comp-auth-01", "comp-gw-01"],
        ),
        MigrationConstraint(
            constraint_id="cnstr-capacity",
            constraint_type=ConstraintType.HARDWARE_LIMIT,
            description="Hardware limits: max 1 concurrent cutover per wave.",
            max_concurrent_migrations=1,
            affected_components=["comp-hsm-01", "comp-auth-01", "comp-gw-01"],
        ),
        MigrationConstraint(
            constraint_id="cnstr-insufficient",
            constraint_type=ConstraintType.ROLLBACK_CAPABILITY,
            description="Rollback procedures unspecified.",
            is_mandatory_rollback=False,
            required_recovery_mechanism=None,
            post_rollback_validation_gate=None,
        ),
    ]

    scenario = ScenarioModel(
        scenario_id="scen-adv-01",
        scenario_name="Adversarial Architecture",
        description="Complex multi-constraint enterprise environment.",
        system_components=[c1, c2, c3],
        dependencies=deps,
        compatibility_records=compats,
        evidence_records=evids,
        migration_constraints=constraints,
        required_tests=tests,
    )
    task = BenchmarkTask(
        task_id="task-adv-01",
        task_name="Adversarial Constraint Task",
        description="Verify multi-constraint execution.",
        scenario_reference="scen-adv-01",
        task_category=TaskCategory.MIGRATION_SEQUENCING,
        difficulty=DifficultyLevel.ADVANCED,
        ground_truth_reference="gt-adv-01",
        task_instructions="Devise a compliant migration plan adhering to all constraints.",
    )
    gt = {
        "ground_truth_id": "gt-adv-01",
        "task_reference": "task-adv-01",
        "scenario_reference": "scen-adv-01",
        "expected_decision": "MIGRATION_READY",
        "expected_blockers": [],
        "cycle_detected": False,
        "direct_dependencies": {
            "comp-gw-01": ["comp-auth-01"],
            "comp-auth-01": ["comp-hsm-01"],
            "comp-hsm-01": [],
        },
        "transitive_dependencies": {
            "comp-gw-01": ["comp-auth-01", "comp-hsm-01"],
            "comp-auth-01": ["comp-hsm-01"],
            "comp-hsm-01": [],
        },
        "optimal_wave_order": [
            {"wave": 1, "upgrades": ["comp-hsm-01"]},
            {"wave": 2, "upgrades": ["comp-auth-01"]},
            {"wave": 3, "upgrades": ["comp-gw-01"]},
        ],
    }
    return scenario, task, gt


def test_end_to_end_regulatory_violation_triggers_veto(adversarial_env: tuple) -> None:
    """Adversarial Test 1: Plan with wrong algorithm triggers safety gate veto in full evaluator."""
    scenario, task, gt = adversarial_env
    evaluator = DeterministicEvaluator()

    contract = ModelResponseContract(
        task_id="task-adv-01",
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[
            ReportedDependency(
                source_component_id="comp-gw-01", target_component_id="comp-auth-01"
            ),
            ReportedDependency(
                source_component_id="comp-auth-01", target_component_id="comp-hsm-01"
            ),
        ],
        compatibility_assessments=[
            ReportedCompatibility(
                component_id="comp-hsm-01",
                status=ReportedCompatibilityStatus.SUPPORTED,
                target_algorithm="WRONG-ALGO",
            ),
            ReportedCompatibility(
                component_id="comp-auth-01",
                status=ReportedCompatibilityStatus.SUPPORTED,
                target_algorithm="ML-DSA-65",
            ),
            ReportedCompatibility(
                component_id="comp-gw-01",
                status=ReportedCompatibilityStatus.SUPPORTED,
                target_algorithm="ML-KEM-768",
            ),
        ],
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id="comp-hsm-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
            ),
            ReportedMigrationStep(
                wave=2,
                component_id="comp-auth-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
                preconditions=["comp-hsm-01"],
            ),
            ReportedMigrationStep(
                wave=3,
                component_id="comp-gw-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
                preconditions=["comp-auth-01"],
            ),
        ],
        verification_results=[
            ReportedTestResult(
                test_id="test-hsm-signing", reported_status=ReportedTestStatus.PASSED
            ),
            ReportedTestResult(
                test_id="test-auth-interop", reported_status=ReportedTestStatus.PASSED
            ),
        ],
        evidence_references=["evid-hsm"],
        explanation="Attempted cutover with wrong target algorithm.",
    )

    report = evaluator.evaluate_detailed(task, contract.model_dump_json(), gt, scenario=scenario)

    assert report.safety_gate_passed is False
    assert report.overall_status == "BLOCKED_BY_SAFETY_GATE"
    assert report.effective_score == 0.0
    assert any("cnstr-reg-cnsa" in v["description"] for v in report.critical_violations)


def test_end_to_end_capacity_limit_violation_triggers_veto(adversarial_env: tuple) -> None:
    """Adversarial Test 2: Plan exceeding max concurrent cutovers is vetoed by safety gate."""
    scenario, task, gt = adversarial_env
    evaluator = DeterministicEvaluator()

    # Schedules 2 cutovers in wave 1 when max_concurrent_migrations == 1
    contract = ModelResponseContract(
        task_id="task-adv-01",
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[
            ReportedDependency(
                source_component_id="comp-gw-01", target_component_id="comp-auth-01"
            ),
            ReportedDependency(
                source_component_id="comp-auth-01", target_component_id="comp-hsm-01"
            ),
        ],
        compatibility_assessments=[
            ReportedCompatibility(
                component_id="comp-hsm-01",
                status=ReportedCompatibilityStatus.SUPPORTED,
                target_algorithm="ML-DSA-65",
            ),
            ReportedCompatibility(
                component_id="comp-auth-01",
                status=ReportedCompatibilityStatus.SUPPORTED,
                target_algorithm="ML-DSA-65",
            ),
            ReportedCompatibility(
                component_id="comp-gw-01",
                status=ReportedCompatibilityStatus.SUPPORTED,
                target_algorithm="ML-KEM-768",
            ),
        ],
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id="comp-hsm-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
            ),
            ReportedMigrationStep(
                wave=1,
                component_id="comp-auth-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
            ),
            ReportedMigrationStep(
                wave=2,
                component_id="comp-gw-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
                preconditions=["comp-auth-01"],
            ),
        ],
        verification_results=[
            ReportedTestResult(
                test_id="test-hsm-signing", reported_status=ReportedTestStatus.PASSED
            ),
            ReportedTestResult(
                test_id="test-auth-interop", reported_status=ReportedTestStatus.PASSED
            ),
        ],
        evidence_references=["evid-hsm"],
        explanation="Attempted parallel wave 1 cutovers exceeding hardware limit.",
    )

    report = evaluator.evaluate_detailed(task, contract.model_dump_json(), gt, scenario=scenario)

    assert report.safety_gate_passed is False
    assert report.overall_status == "BLOCKED_BY_SAFETY_GATE"
    assert any("cnstr-capacity" in v["description"] for v in report.critical_violations)


def test_end_to_end_sound_plan_passes_and_reports_findings(adversarial_env: tuple) -> None:
    """Adversarial Test 3: Sound plan passes all evaluable constraints and records NOT_EVALUABLE cleanly."""
    scenario, task, gt = adversarial_env
    evaluator = DeterministicEvaluator()

    contract = ModelResponseContract(
        task_id="task-adv-01",
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[
            ReportedDependency(
                source_component_id="comp-gw-01", target_component_id="comp-auth-01"
            ),
            ReportedDependency(
                source_component_id="comp-auth-01", target_component_id="comp-hsm-01"
            ),
        ],
        compatibility_assessments=[
            ReportedCompatibility(
                component_id="comp-hsm-01",
                status=ReportedCompatibilityStatus.SUPPORTED,
                target_algorithm="ML-DSA-65",
            ),
            ReportedCompatibility(
                component_id="comp-auth-01",
                status=ReportedCompatibilityStatus.SUPPORTED,
                target_algorithm="ML-DSA-65",
            ),
            ReportedCompatibility(
                component_id="comp-gw-01",
                status=ReportedCompatibilityStatus.SUPPORTED,
                target_algorithm="ML-KEM-768",
            ),
        ],
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id="comp-hsm-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
                coexisting_algorithms=["RSA-4096", "ML-DSA-65"],
            ),
            ReportedMigrationStep(
                wave=2,
                component_id="comp-auth-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
                preconditions=["comp-hsm-01"],
                coexisting_algorithms=["RSA-2048", "ML-DSA-65"],
            ),
            ReportedMigrationStep(
                wave=3,
                component_id="comp-gw-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
                preconditions=["comp-auth-01"],
                coexisting_algorithms=["ECDSA-P256", "ML-KEM-768"],
            ),
        ],
        verification_results=[
            ReportedTestResult(
                test_id="test-hsm-signing", reported_status=ReportedTestStatus.PASSED
            ),
            ReportedTestResult(
                test_id="test-auth-interop", reported_status=ReportedTestStatus.PASSED
            ),
        ],
        evidence_references=["evid-hsm", "evid-auth"],
        explanation="Sequenced 1-by-1 within hardware capacity, CNSA 2.0 compliant, dual stack supported.",
    )

    report = evaluator.evaluate_detailed(task, contract.model_dump_json(), gt, scenario=scenario)

    assert report.safety_gate_passed is True
    assert report.overall_status == "PASSED"
    assert report.effective_score >= 80.0

    # Verify structured constraint telemetry in DetailedEvaluationReport
    findings = report.constraint_findings
    assert "total_constraints" in findings
    assert findings["total_constraints"] == 4
    assert findings["satisfied"] >= 2
    assert findings["not_evaluable"] >= 1
    assert findings["safety_gate_impact"] == "NONE"

    # Verify checks contain explicit NOT_EVALUABLE record with missing_information
    unspec_chk = next(c for c in findings["checks"] if c["constraint_id"] == "cnstr-insufficient")
    assert unspec_chk["status"] == ConstraintStatus.NOT_EVALUABLE.value
    assert unspec_chk["missing_information"] is not None

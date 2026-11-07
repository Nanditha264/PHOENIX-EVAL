"""Unit tests for the six individual dimension grading engines."""

import pytest

from phoenix_eval.evaluation.compatibility_grader import CompatibilityGrader
from phoenix_eval.evaluation.dependency_grader import DependencyGrader
from phoenix_eval.evaluation.evidence_grader import EvidenceGrader
from phoenix_eval.evaluation.migration_plan_grader import MigrationPlanGrader
from phoenix_eval.evaluation.verification_gate_grader import VerificationGateGrader
from phoenix_eval.schemas import (
    CompatibilityRecord,
    CompatibilityStatus,
    ComponentType,
    CryptographicComponent,
    CryptographicRole,
    DependencyCriticality,
    DependencyRelationship,
    EvidenceRecord,
    EvidenceType,
    RelationshipType,
    RequiredTest,
    ScenarioModel,
)
from phoenix_eval.schemas import (
    TestType as SchemaTestType,
)
from phoenix_eval.schemas.response_contract import (
    ModelDecision,
    ModelResponseContract,
    ReportedCompatibility,
    ReportedCompatibilityStatus,
    ReportedDependency,
    ReportedMigrationStep,
    ReportedTestResult,
    ReportedTestStatus,
)


@pytest.fixture
def sample_scenario() -> ScenarioModel:
    c1 = CryptographicComponent(
        component_id="comp-db",
        component_name="Database",
        component_type=ComponentType.DATABASE,
        cryptographic_role=CryptographicRole.DATA_ENCRYPTION_AT_REST,
        description="Database service",
        technology="PostgreSQL",
        current_algorithms=["AES-256-GCM"],
    )
    c2 = CryptographicComponent(
        component_id="comp-app",
        component_name="App Service",
        component_type=ComponentType.MICROSERVICE,
        cryptographic_role=CryptographicRole.DATA_ENCRYPTION_IN_TRANSIT,
        description="App service",
        technology="Go",
        current_algorithms=["RSA-2048"],
    )
    c3 = CryptographicComponent(
        component_id="comp-ext",
        component_name="External Service",
        component_type=ComponentType.EXTERNAL_PROVIDER,
        cryptographic_role=CryptographicRole.TLS_TERMINATION,
        description="External vendor service",
        technology="Vendor",
        current_algorithms=["ECDSA-P256"],
    )
    dep = DependencyRelationship(
        edge_id="edge-app-db",
        source_component_id="comp-app",
        target_component_id="comp-db",
        relationship_type=RelationshipType.CALLS,
        criticality=DependencyCriticality.CRITICAL,
    )
    compat1 = CompatibilityRecord(
        component_id="comp-db",
        proposed_target="ML-KEM-768",
        status=CompatibilityStatus.SUPPORTED,
        reason="Driver supports ML-KEM",
        assessment_source="Audit Team",
    )
    compat2 = CompatibilityRecord(
        component_id="comp-app",
        proposed_target="ML-DSA-65",
        status=CompatibilityStatus.SUPPORTED,
        reason="Runtime updated",
        assessment_source="Audit Team",
    )
    compat3 = CompatibilityRecord(
        component_id="comp-ext",
        proposed_target="ML-DSA-44",
        status=CompatibilityStatus.UNKNOWN,
        reason="Vendor unverified",
        assessment_source="Audit Team",
    )
    test_req = RequiredTest(
        test_id="test-db-interop-01",
        test_type=SchemaTestType.INTEROPERABILITY,
        description="Verify TLS 1.3 PQC cipher suite handshake.",
        target_components=["comp-db"],
    )
    evid = EvidenceRecord(
        evidence_id="evid-ast-01",
        evidence_type=EvidenceType.STATIC_CODE_ANALYSIS,
        source="Scanner",
        description="AST parse",
        observed_value="AST parsed dependencies verified.",
        confidence=1.0,
        provenance="Scanner",
    )
    return ScenarioModel(
        scenario_id="scen-sample-01",
        scenario_name="Sample Scenario",
        description="Scenario for grading tests",
        system_components=[c1, c2, c3],
        dependencies=[dep],
        compatibility_records=[compat1, compat2, compat3],
        required_tests=[test_req],
        evidence_records=[evid],
        migration_constraints=[],
    )


def test_dependency_grader_perfect_and_deductions(sample_scenario: ScenarioModel) -> None:
    grader = DependencyGrader(max_score=20.0)

    # 1. Perfect match
    contract_perfect = ModelResponseContract(
        task_id="t-01",
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[
            ReportedDependency(source_component_id="comp-app", target_component_id="comp-db")
        ],
        compatibility_assessments=[],
        migration_plan=[],
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Perfect dependencies.",
    )
    res_perfect = grader.grade(contract_perfect, sample_scenario, {})
    assert res_perfect.raw_score == 20.0
    assert len(res_perfect.missing_edges) == 0
    assert len(res_perfect.invented_edges) == 0

    # 2. Omitted edge + spurious edge
    contract_flawed = ModelResponseContract(
        task_id="t-01",
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[
            ReportedDependency(
                source_component_id="comp-app", target_component_id="comp-ext"
            )  # Spurious
        ],
        compatibility_assessments=[],
        migration_plan=[],
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Flawed dependencies.",
    )
    res_flawed = grader.grade(contract_flawed, sample_scenario, {})
    assert res_flawed.raw_score < 20.0
    assert len(res_flawed.missing_edges) == 1
    assert len(res_flawed.invented_edges) == 1


def test_compatibility_grader_enforces_rule_d_unknown(sample_scenario: ScenarioModel) -> None:
    grader = CompatibilityGrader(max_score=20.0)

    # In sample_scenario, comp-ext status is UNKNOWN.
    # Model claiming comp-ext is SUPPORTED must trigger VIO_UNKNOWN_ASSUMED_SUPPORTED
    contract_bad = ModelResponseContract(
        task_id="t-01",
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[
            ReportedCompatibility(
                component_id="comp-ext", status=ReportedCompatibilityStatus.SUPPORTED
            )
        ],
        migration_plan=[],
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Claimed external provider is supported.",
    )
    res_bad = grader.grade(contract_bad, sample_scenario, {})
    assert any(v.rule_name == "VIO_UNKNOWN_ASSUMED_SUPPORTED" for v in res_bad.violations)


def test_migration_plan_grader_causal_enforcement(sample_scenario: ScenarioModel) -> None:
    grader = MigrationPlanGrader(max_score=20.0)

    # Inverted order: caller comp-app in wave 1, callee comp-db in wave 2
    contract_inverted = ModelResponseContract(
        task_id="t-01",
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[],
        migration_plan=[
            ReportedMigrationStep(wave=1, component_id="comp-app"),
            ReportedMigrationStep(wave=2, component_id="comp-db"),
        ],
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Inverted plan.",
    )
    res = grader.grade(contract_inverted, sample_scenario, {})
    assert res.plan_valid is False
    assert any(v.rule_name == "VIO_DEPENDENCY_ORDER_REVERSED" for v in res.violations)


def test_evidence_grader_detects_invented_evidence(sample_scenario: ScenarioModel) -> None:
    grader = EvidenceGrader(max_score=15.0)

    contract_hallucinated = ModelResponseContract(
        task_id="t-01",
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[],
        migration_plan=[],
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=["evid-fake-hallucination"],
        assumptions=[],
        uncertainties=[],
        explanation="Hallucinated evidence reference.",
    )
    res = grader.grade(contract_hallucinated, sample_scenario, {})
    assert any(v.rule_name == "VIO_INVALID_EVIDENCE_REFERENCE" for v in res.violations)
    assert res.raw_score < 15.0


def test_verification_gate_grader_enforces_rule_e_test_blocking(
    sample_scenario: ScenarioModel,
) -> None:
    grader = VerificationGateGrader(max_score=15.0)

    # Reported test result is FAILED, but model declares MIGRATION_READY
    contract_ignored_failure = ModelResponseContract(
        task_id="t-01",
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[],
        migration_plan=[],
        blocked_components=[],
        required_actions=[],
        verification_results=[
            ReportedTestResult(
                test_id="test-db-interop-01", reported_status=ReportedTestStatus.FAILED
            )
        ],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Ignored test failure.",
    )
    res = grader.grade(contract_ignored_failure, sample_scenario, {})
    assert res.readiness_blocked_by_gates is True
    assert any(v.rule_name == "VIO_FAILED_TEST_IGNORED" for v in res.violations)

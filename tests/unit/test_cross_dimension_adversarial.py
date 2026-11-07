"""Cross-dimension compound adversarial test suite (Phase 9).

Tests interactions where multiple failure modes occur simultaneously across dimensions:
- Hidden dependency combined with stale compatibility evidence
- Shared consumer combined with failed interoperability
- Valid topological order combined with missing rollback capability
- Unknown external provider combined with conditional migration plan
- Dependency cycle hidden among otherwise independent components
- Valid preparation combined with unsafe production cutover
- Conflicting evidence with high confidence score
"""

import pytest

from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.serialization import read_json
from phoenix_eval.evaluation.evaluator import DeterministicEvaluator
from phoenix_eval.evaluation.migration_plan_grader import MigrationPlanGrader
from phoenix_eval.schemas.common import StrEnum
from phoenix_eval.schemas.compatibility import CompatibilityRecord, CompatibilityStatus
from phoenix_eval.schemas.components import ComponentType, CryptographicComponent, CryptographicRole
from phoenix_eval.schemas.dependencies import DependencyCriticality, DependencyRelationship, RelationshipType
from phoenix_eval.schemas.evidence import EvidenceCategory, EvidenceRecord, EvidenceType, VerificationStatus
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
    TestType,
)
from phoenix_eval.schemas.tasks import BenchmarkTask, DifficultyLevel, TaskCategory


def create_compound_scenario() -> ScenarioModel:
    """Create a multi-service enterprise scenario for compound adversarial testing."""
    c_gw = CryptographicComponent(
        component_id="comp-api-gw",
        component_name="API Gateway",
        component_type=ComponentType.API_GATEWAY,
        cryptographic_role=CryptographicRole.TLS_TERMINATION,
        description="Edge Gateway",
        technology="Kong/Nginx",
        current_algorithms=["RSA-2048"],
    )
    c_auth = CryptographicComponent(
        component_id="comp-auth-svc",
        component_name="Auth Service",
        component_type=ComponentType.MICROSERVICE,
        cryptographic_role=CryptographicRole.DATA_ENCRYPTION_IN_TRANSIT,
        description="Authentication Service",
        technology="Java",
        current_algorithms=["AES-128-GCM"],
    )
    c_hsm = CryptographicComponent(
        component_id="comp-hsm",
        component_name="Shared HSM",
        component_type=ComponentType.HARDWARE_SECURITY_MODULE,
        cryptographic_role=CryptographicRole.KEY_STORAGE,
        description="Hardware Security Module",
        technology="C/C++",
        current_algorithms=["AES-256-GCM"],
    )
    c_db = CryptographicComponent(
        component_id="comp-db",
        component_name="Ledger Database",
        component_type=ComponentType.DATABASE,
        cryptographic_role=CryptographicRole.DATA_ENCRYPTION_AT_REST,
        description="Financial Ledger",
        technology="PostgreSQL",
        current_algorithms=["3DES"],
    )

    dep_1 = DependencyRelationship(
        edge_id="dep-gw-to-auth",
        source_component_id="comp-api-gw",
        target_component_id="comp-auth-svc",
        relationship_type=RelationshipType.CALLS,
        criticality=DependencyCriticality.CRITICAL,
    )
    dep_2 = DependencyRelationship(
        edge_id="dep-auth-to-hsm",
        source_component_id="comp-auth-svc",
        target_component_id="comp-hsm",
        relationship_type=RelationshipType.USES_LIBRARY,
        criticality=DependencyCriticality.CRITICAL,
    )
    dep_3 = DependencyRelationship(
        edge_id="dep-auth-to-db",
        source_component_id="comp-auth-svc",
        target_component_id="comp-db",
        relationship_type=RelationshipType.STORES_DATA_IN,
        criticality=DependencyCriticality.CRITICAL,
    )

    compat_gw = CompatibilityRecord(
        component_id="comp-api-gw",
        proposed_target="ML-KEM-768",
        status=CompatibilityStatus.SUPPORTED,
        reason="Upgraded Kong gateway plugin",
        assessment_source="telemetry",
    )
    compat_auth = CompatibilityRecord(
        component_id="comp-auth-svc",
        proposed_target="ML-KEM-768",
        status=CompatibilityStatus.SUPPORTED,
        reason="Supported in runtime",
        assessment_source="telemetry",
    )
    compat_hsm = CompatibilityRecord(
        component_id="comp-hsm",
        proposed_target="ML-KEM-768",
        status=CompatibilityStatus.SUPPORTED,
        reason="Firmware upgraded",
        assessment_source="vendor_attestation",
    )
    compat_db = CompatibilityRecord(
        component_id="comp-db",
        proposed_target="AES-256-GCM",
        status=CompatibilityStatus.UNSUPPORTED,
        reason="Legacy DB engine does not support AES-256-GCM",
        assessment_source="manual_audit",
    )

    evid_1 = EvidenceRecord(
        evidence_id="evid-gw-valid",
        evidence_type=EvidenceType.RUNTIME_TELEMETRY,
        source="datadog",
        description="Gateway runtime trace",
        observed_value="TLS_1_3_READY",
        provenance="trace:001",
        verification_status=VerificationStatus.VERIFIED,
        evidence_category=EvidenceCategory.OBSERVED,
        is_stale=False,
    )

    constraint_rollback = MigrationConstraint(
        constraint_id="cnstr-rollback-mandatory",
        constraint_type=ConstraintType.ROLLBACK_CAPABILITY,
        description="Every cutover step must specify automated rollback actions and verification gates.",
        is_mandatory_rollback=True,
    )

    test_interop = RequiredTest(
        test_id="test-auth-interop-01",
        test_type=TestType.INTEROPERABILITY,
        description="Mandatory end-to-end handshake interoperability test.",
        target_components=["comp-auth-svc", "comp-hsm"],
    )

    return ScenarioModel(
        scenario_id="scen-compound-test",
        scenario_name="Compound Test Scenario",
        description="Multi-factor scenario",
        system_components=[c_gw, c_auth, c_hsm, c_db],
        dependencies=[dep_1, dep_2, dep_3],
        compatibility_records=[compat_gw, compat_auth, compat_hsm, compat_db],
        required_tests=[test_interop],
        evidence_records=[evid_1],
        migration_constraints=[constraint_rollback],
    )


def create_compound_task(scen: ScenarioModel) -> tuple[BenchmarkTask, dict]:
    task = BenchmarkTask(
        task_id="task-compound-test-01",
        task_name="Compound Test Task",
        task_category=TaskCategory.MIGRATION_SEQUENCING,
        difficulty=DifficultyLevel.ADVANCED,
        description="Test compound interactions",
        scenario_reference=scen.scenario_id,
        task_instructions="Plan migration",
        ground_truth_reference="gt-compound-test-01",
    )
    gt = {
        "ground_truth_id": task.ground_truth_reference,
        "task_reference": task.task_id,
        "scenario_reference": scen.scenario_id,
        "is_migratable": False,
        "expected_blockers": ["comp-db"],
        "direct_dependencies": {},
        "transitive_dependencies": {},
        "optimal_wave_order": [],
        "required_verification_gates": ["test-auth-interop-01"],
        "critical_violations": [],
    }
    return task, gt


def test_cross_dim_hidden_dep_and_stale_evidence():
    """Case 1: Hidden dependency combined with stale compatibility evidence."""
    scen = create_compound_scenario()
    task, gt = create_compound_task(scen)
    evaluator = DeterministicEvaluator()

    # Inject stale evidence record
    scen_data = scen.model_dump(mode="json")
    scen_data["evidence_records"].append(
        {
            "evidence_id": "evid-stale-auth",
            "evidence_type": "CONFIGURATION_AUDIT",
            "source": "legacy-audit-2022",
            "description": "Old audit",
            "observed_value": "SUPPORTED",
            "provenance": "archive:2022",
            "verification_status": "STALE",
            "evidence_category": "OBSERVED",
            "is_stale": True,
            "freshness_days": 800,
        }
    )
    scen_mod = ScenarioModel.model_validate(scen_data)

    # Model omits prerequisite HSM (hidden dependency) AND cites stale evidence
    contract = ModelResponseContract(
        task_id=task.task_id,
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[
            ReportedCompatibility(
                component_id="comp-auth-svc",
                status=ReportedCompatibilityStatus.SUPPORTED,
                evidence_reference="evid-stale-auth",
            )
        ],
        migration_plan=[
            ReportedMigrationStep(wave=1, component_id="comp-auth-svc")  # Missing comp-hsm prerequisite!
        ],
        blocked_components=[],
        required_actions=[],
        verification_results=[
            ReportedTestResult(test_id="test-auth-interop-01", reported_status=ReportedTestStatus.PASSED, evidence_reference="evid-gw-valid")
        ],
        evidence_references=["evid-stale-auth", "evid-gw-valid"],
        assumptions=[],
        uncertainties=[],
        explanation="Plan with hidden dep omission and stale evidence.",
    )

    report = evaluator.evaluate_detailed(task, contract.model_dump_json(indent=2), gt, scen_mod)
    assert not report.safety_gate_passed
    viols = [v["rule_name"] for v in report.critical_violations] + [
        v["rule_name"] for v in report.non_critical_violations
    ]
    # Both failure signals must be extracted without crashing
    assert "VIO_DEPENDENCY_ORDER_REVERSED" in viols or "VIO_KNOWN_DEPENDENCY_OMITTED" in viols
    assert "VIO_STALE_EVIDENCE_RELIED_UPON" in viols


def test_cross_dim_shared_consumer_and_failed_interop():
    """Case 2: Shared consumer combined with failed interoperability test."""
    scen = create_compound_scenario()
    task, gt = create_compound_task(scen)
    evaluator = DeterministicEvaluator()

    contract = ModelResponseContract(
        task_id=task.task_id,
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[],
        migration_plan=[
            ReportedMigrationStep(wave=1, component_id="comp-hsm"),
            ReportedMigrationStep(wave=2, component_id="comp-auth-svc"),
            ReportedMigrationStep(wave=3, component_id="comp-api-gw"),
        ],
        blocked_components=[],
        required_actions=[],
        verification_results=[
            ReportedTestResult(
                test_id="test-auth-interop-01",
                reported_status=ReportedTestStatus.FAILED,
                evidence_reference=None,
            )
        ],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Plan with failed test.",
    )

    report = evaluator.evaluate_detailed(task, contract.model_dump_json(indent=2), gt, scen)
    assert not report.safety_gate_passed
    viols = [v["rule_name"] for v in report.critical_violations]
    assert "VIO_FAILED_TEST_IGNORED" in viols or "VIO_CONTRADICTORY_DECISION" in viols


def test_cross_dim_valid_topology_missing_rollback():
    """Case 3: Valid topological order combined with missing rollback capability."""
    scen = create_compound_scenario()
    task, gt = create_compound_task(scen)
    evaluator = DeterministicEvaluator()

    # Flawless topological wave order (HSM -> Auth -> Gateway) but zero rollback information
    contract = ModelResponseContract(
        task_id=task.task_id,
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[
            ReportedCompatibility(
                component_id=c.component_id,
                status=ReportedCompatibilityStatus.SUPPORTED,
                evidence_reference="evid-gw-valid",
            )
            for c in scen.system_components if c.component_id != "comp-db"
        ],
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id="comp-hsm",
                rollback_trigger=None,
                rollback_action=None,
            ),
            ReportedMigrationStep(
                wave=2,
                component_id="comp-auth-svc",
                rollback_trigger=None,
                rollback_action=None,
            ),
            ReportedMigrationStep(
                wave=3,
                component_id="comp-api-gw",
                rollback_trigger=None,
                rollback_action=None,
            ),
        ],
        blocked_components=["comp-db"],
        required_actions=[],
        verification_results=[
            ReportedTestResult(
                test_id="test-auth-interop-01",
                reported_status=ReportedTestStatus.PASSED,
                evidence_reference="evid-gw-valid",
            )
        ],
        evidence_references=["evid-gw-valid"],
        assumptions=[],
        uncertainties=[],
        explanation="Valid waves, no rollback.",
    )

    report = evaluator.evaluate_detailed(task, contract.model_dump_json(indent=2), gt, scen)
    # Plan correctness dimension gives credit for valid waves, while constraint deductions occur
    assert report.dimension_scores["migration_plan_correctness"]["raw_score"] > 0.0


def test_cross_dim_unknown_external_provider_conditional_plan():
    """Case 4: Unknown external provider combined with conditional migration plan."""
    scen = create_compound_scenario()
    task, gt = create_compound_task(scen)
    evaluator = DeterministicEvaluator()

    # External partner has UNKNOWN compatibility
    scen_data = scen.model_dump(mode="json")
    scen_data["system_components"].append(
        {
            "component_id": "comp-partner-idp",
            "component_name": "External Partner IdP",
            "component_type": "EXTERNAL_PROVIDER",
            "cryptographic_role": "AUTHENTICATION_TOKEN",
            "description": "External OAuth",
            "technology": "OIDC",
            "current_algorithms": ["RS256"],
        }
    )
    scen_data["compatibility_records"].append(
        {
            "component_id": "comp-partner-idp",
            "proposed_target": "ML-DSA-65",
            "status": "UNKNOWN",
            "reason": "Unverified vendor",
            "assessment_source": "inquiry",
            "evidence_references": [],
        }
    )
    scen_ext = ScenarioModel.model_validate(scen_data)

    # Model claims CONDITIONAL, but schedules UNCONDITIONAL cutover for the unknown external partner
    contract = ModelResponseContract(
        task_id=task.task_id,
        decision=ModelDecision.CONDITIONAL,
        identified_dependencies=[],
        compatibility_assessments=[
            ReportedCompatibility(component_id="comp-partner-idp", status=ReportedCompatibilityStatus.UNKNOWN)
        ],
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id="comp-partner-idp",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
                is_conditional=False,  # Unconditional cutover of UNKNOWN external provider!
            )
        ],
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Conditional decision but unconditional cutover.",
    )

    report = evaluator.evaluate_detailed(task, contract.model_dump_json(indent=2), gt, scen_ext)
    assert not report.safety_gate_passed
    viols = [v["rule_name"] for v in report.critical_violations]
    assert "VIO_UNKNOWN_ASSUMED_SUPPORTED" in viols or "VIO_CONDITIONAL_CUTOVER_VIOLATION" in viols


def test_cross_dim_valid_prep_unsafe_cutover():
    """Case 5: Migration plan with valid preparation but unsafe production cutover."""
    scen = create_compound_scenario()
    task, gt = create_compound_task(scen)
    evaluator = DeterministicEvaluator()

    # Wave 1: DISCOVERY & PREPARATION (Sound)
    # Wave 2: PRODUCTION_CUTOVER for comp-db (UNSUPPORTED)
    contract = ModelResponseContract(
        task_id=task.task_id,
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[],
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id="comp-api-gw",
                action_type=MigrationActionType.PREPARATION,
            ),
            ReportedMigrationStep(
                wave=1,
                component_id="comp-auth-svc",
                action_type=MigrationActionType.DISCOVERY,
            ),
            ReportedMigrationStep(
                wave=2,
                component_id="comp-db",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
            ),
        ],
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Sound prep followed by unsupported DB cutover.",
    )

    report = evaluator.evaluate_detailed(task, contract.model_dump_json(indent=2), gt, scen)
    assert not report.safety_gate_passed
    viols = [v["rule_name"] for v in report.critical_violations]
    assert "VIO_UNSUPPORTED_COMPONENT_SCHEDULED" in viols


def test_cross_dim_conflicting_evidence_high_confidence():
    """Case 6: Conflicting evidence with apparently high confidence score."""
    scen = create_compound_scenario()
    task, gt = create_compound_task(scen)
    evaluator = DeterministicEvaluator()

    # Inject two conflicting high-confidence records for DB
    scen_data = scen.model_dump(mode="json")
    scen_data["evidence_records"].extend(
        [
            {
                "evidence_id": "evid-db-claim-pass",
                "evidence_type": "VENDOR_CAPABILITY_STATEMENT",
                "source": "vendor-brochure",
                "description": "Vendor claims PQC support",
                "observed_value": "AES-256-GCM_SUPPORTED",
                "confidence": 1.0,
                "provenance": "pdf:vendor-whitepaper",
                "verification_status": "VERIFIED",
                "evidence_category": "OBSERVED",
                "is_stale": False,
            },
            {
                "evidence_id": "evid-db-claim-fail",
                "evidence_type": "RUNTIME_TELEMETRY",
                "source": "db-driver-benchmark",
                "description": "Direct benchmark failure on 3DES cipher migration",
                "observed_value": "FAILURE_UNSUPPORTED_CIPHER",
                "confidence": 1.0,
                "provenance": "log:driver-err-88",
                "verification_status": "CONTRADICTED",
                "evidence_category": "OBSERVED",
                "is_stale": False,
            },
        ]
    )
    scen_conflict = ScenarioModel.model_validate(scen_data)

    # Model selectively cites only the positive vendor brochure and schedules cutover
    contract = ModelResponseContract(
        task_id=task.task_id,
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[
            ReportedCompatibility(
                component_id="comp-db",
                status=ReportedCompatibilityStatus.SUPPORTED,
                evidence_reference="evid-db-claim-pass",
            )
        ],
        migration_plan=[
            ReportedMigrationStep(wave=1, component_id="comp-db")
        ],
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=["evid-db-claim-pass"],
        assumptions=[],
        uncertainties=[],
        explanation="Cherry-picked positive claim.",
    )

    report = evaluator.evaluate_detailed(task, contract.model_dump_json(indent=2), gt, scen_conflict)
    assert not report.safety_gate_passed
    assert report.effective_score == 0.0

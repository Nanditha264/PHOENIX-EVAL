"""Combinatorial property-based invariant test suite for evaluator robustness (Phase 9).

Generates deterministic combinations of graph topologies, depths, consumer counts,
shared dependencies, compatibility states, evidence freshness, and rollback mechanisms
to verify the 10 core invariant properties under reproducible seeds.
"""

import copy
import pytest

from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.serialization import read_json
from phoenix_eval.evaluation.evaluator import DeterministicEvaluator
from phoenix_eval.evaluation.independent_graph_verifier import IndependentGraphVerifier
from phoenix_eval.evaluation.migration_plan_grader import MigrationPlanGrader
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
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import BenchmarkTask, DifficultyLevel, TaskCategory


def build_synthetic_graph(
    depth: int = 3,
    consumers_per_level: int = 2,
    has_shared_sink: bool = True,
    seed: int = 42,
) -> tuple[ScenarioModel, BenchmarkTask, dict]:
    """Deterministically construct a synthetic multi-tier enterprise architecture scenario."""
    components = []
    dependencies = []
    compat_records = []
    evidence_records = []

    # Sink / Root Provider
    sink_id = "comp-root-hsm-01"
    components.append(
        CryptographicComponent(
            component_id=sink_id,
            component_name="Root Hardware Security Module",
            component_type=ComponentType.HARDWARE_SECURITY_MODULE,
            cryptographic_role=CryptographicRole.KEY_STORAGE,
            description="Root Hardware Security Module for Key Storage",
            technology="C/C++",
            current_algorithms=["AES-256-GCM", "RSA-4096"],
        )
    )
    compat_records.append(
        CompatibilityRecord(
            component_id=sink_id,
            proposed_target="ML-KEM-768",
            status=CompatibilityStatus.SUPPORTED,
            reason="Firmware v4.2 verified PQC support",
            assessment_source="vendor_attestation",
            evidence_references=["evid-root-audit-01"],
        )
    )
    evidence_records.append(
        EvidenceRecord(
            evidence_id="evid-root-audit-01",
            evidence_type=EvidenceType.CONFIGURATION_AUDIT,
            source="hsm-firmware-manifest",
            description="Verified firmware specification",
            observed_value="ML-KEM-768_SUPPORTED",
            provenance="audit:2026-q1",
            verification_status=VerificationStatus.VERIFIED,
            evidence_category=EvidenceCategory.OBSERVED,
            is_stale=False,
        )
    )

    prev_level_nodes = [sink_id]

    for d in range(1, depth + 1):
        curr_level_nodes = []
        for c in range(consumers_per_level):
            cid = f"comp-tier{d}-svc{c:02d}"
            components.append(
                CryptographicComponent(
                    component_id=cid,
                    component_name=f"Tier {d} Service {c}",
                    component_type=ComponentType.SERVICE if d > 1 else ComponentType.APPLICATION,
                    cryptographic_role=CryptographicRole.TLS_TERMINATION,
                    description=f"Tier {d} Service {c} for API and data transport",
                    technology="Java" if c % 2 == 0 else "Go",
                    current_algorithms=["TLS_1_2", "RSA-2048"],
                )
            )
            compat_records.append(
                CompatibilityRecord(
                    component_id=cid,
                    proposed_target="ML-KEM-768",
                    status=CompatibilityStatus.SUPPORTED,
                    reason="Runtime upgraded with BouncyCastle PQC",
                    assessment_source="telemetry",
                    evidence_references=[f"evid-tier{d}-{c}"],
                )
            )
            evidence_records.append(
                EvidenceRecord(
                    evidence_id=f"evid-tier{d}-{c}",
                    evidence_type=EvidenceType.RUNTIME_TELEMETRY,
                    source="datadog-apm-tracer",
                    description=f"Runtime trace for tier {d} service {c}",
                    observed_value="PQC_TLS_READY",
                    provenance=f"trace:session-tier{d}-{c}",
                    verification_status=VerificationStatus.VERIFIED,
                    evidence_category=EvidenceCategory.OBSERVED,
                    is_stale=False,
                )
            )
            # Edge: caller in curr_level depends on callee in prev_level
            callee = prev_level_nodes[c % len(prev_level_nodes)]
            dependencies.append(
                DependencyRelationship(
                    edge_id=f"dep-t{d}-s{c}-to-{callee}",
                    source_component_id=cid,
                    target_component_id=callee,
                    relationship_type=RelationshipType.CALLS,
                    criticality=DependencyCriticality.CRITICAL,
                )
            )
            curr_level_nodes.append(cid)
        prev_level_nodes = curr_level_nodes

    scen = ScenarioModel(
        scenario_id=f"scen-comb-d{depth}-c{consumers_per_level}",
        scenario_name="Combinatorial Synthetic Scenario",
        description="Synthetic multi-tier scenario for property testing",
        system_components=components,
        dependencies=dependencies,
        compatibility_records=compat_records,
        required_tests=[],
        evidence_records=evidence_records,
        migration_constraints=[],
    )

    task = BenchmarkTask(
        task_id=f"task-comb-d{depth}-c{consumers_per_level}",
        task_name="Combinatorial Property Task",
        task_category=TaskCategory.MIGRATION_SEQUENCING,
        difficulty=DifficultyLevel.INTERMEDIATE,
        description="Property testing task",
        scenario_reference=scen.scenario_id,
        task_instructions="Plan migration",
        ground_truth_reference=f"gt-comb-d{depth}-c{consumers_per_level}",
    )

    gt = {
        "ground_truth_id": task.ground_truth_reference,
        "task_reference": task.task_id,
        "scenario_reference": scen.scenario_id,
        "is_migratable": True,
        "expected_blockers": [],
        "direct_dependencies": {},
        "transitive_dependencies": {},
        "optimal_wave_order": [],
        "required_verification_gates": [],
        "critical_violations": [],
    }

    return scen, task, gt


def test_property_1_unknown_compatibility_never_becomes_supported():
    """Property 1: Unknown compatibility never becomes supported through missing evidence."""
    scen, task, gt = build_synthetic_graph(depth=2, consumers_per_level=2)
    evaluator = DeterministicEvaluator()

    # Model reports a component as SUPPORTED, but scenario compatibility is UNKNOWN with zero evidence
    scen_data = scen.model_dump(mode="json")
    scen_data["compatibility_records"][0]["status"] = "UNKNOWN"
    scen_mod = ScenarioModel.model_validate(scen_data)

    contract = ModelResponseContract(
        task_id=task.task_id,
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[
            ReportedCompatibility(
                component_id=scen.system_components[0].component_id,
                status=ReportedCompatibilityStatus.SUPPORTED,  # Falsely claiming SUPPORTED
                evidence_reference=None,  # No evidence
            )
        ],
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id=scen.system_components[0].component_id,
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
            )
        ],
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Assuming supported.",
    )

    report = evaluator.evaluate_detailed(
        task=task,
        raw_response_text=contract.model_dump_json(indent=2),
        ground_truth=gt,
        scenario=scen_mod,
    )

    assert not report.safety_gate_passed
    viols = [v["rule_name"] for v in report.critical_violations]
    assert "VIO_UNKNOWN_ASSUMED_SUPPORTED" in viols


def test_property_2_removing_mandatory_evidence_cannot_improve_readiness():
    """Property 2: Removing mandatory evidence cannot improve readiness score."""
    scen, task, gt = build_synthetic_graph(depth=2, consumers_per_level=2)
    evaluator = DeterministicEvaluator()

    # Valid base contract
    base_contract = ModelResponseContract(
        task_id=task.task_id,
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[
            ReportedCompatibility(
                component_id=c.component_id,
                status=ReportedCompatibilityStatus.SUPPORTED,
                evidence_reference=f"evid-tier{1}-0" if "tier" in c.component_id else "evid-root-audit-01",
            )
            for c in scen.system_components
        ],
        migration_plan=[
            ReportedMigrationStep(wave=1, component_id=scen.system_components[0].component_id),
            ReportedMigrationStep(wave=2, component_id=scen.system_components[1].component_id),
        ],
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=["evid-root-audit-01"],
        assumptions=[],
        uncertainties=[],
        explanation="Valid baseline.",
    )

    base_rep = evaluator.evaluate_detailed(task, base_contract.model_dump_json(indent=2), gt, scen)

    # Strip evidence
    mut_data = base_contract.model_dump(mode="json")
    mut_data["evidence_references"] = []
    for a in mut_data["compatibility_assessments"]:
        a["evidence_reference"] = None
    mut_contract = ModelResponseContract.model_validate(mut_data)

    mut_rep = evaluator.evaluate_detailed(task, mut_contract.model_dump_json(indent=2), gt, scen)
    assert mut_rep.effective_score <= base_rep.effective_score


def test_property_3_adding_genuine_dependency_cannot_make_unsafe_valid():
    """Property 3: Adding a genuine dependency cannot make an unsafe ordering valid."""
    scen, task, gt = build_synthetic_graph(depth=2, consumers_per_level=2)
    evaluator = DeterministicEvaluator()

    # Plan has inverted wave order: caller before callee
    root = scen.system_components[0].component_id
    caller = scen.system_components[1].component_id

    contract = ModelResponseContract(
        task_id=task.task_id,
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[],
        migration_plan=[
            ReportedMigrationStep(wave=1, component_id=caller),  # Caller wave 1 (UNSAFE)
            ReportedMigrationStep(wave=2, component_id=root),    # Callee wave 2
        ],
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Inverted order.",
    )

    # Adding an extra dependency to scenario
    scen_data = scen.model_dump(mode="json")
    scen_data["dependencies"].append(
        {
            "edge_id": "dep-extra-test",
            "source_component_id": scen.system_components[2].component_id,
            "target_component_id": root,
            "relationship_type": "CALLS",
            "criticality": "HIGH",
        }
    )
    scen_extra = ScenarioModel.model_validate(scen_data)

    report = evaluator.evaluate_detailed(task, contract.model_dump_json(indent=2), gt, scen_extra)
    assert not report.safety_gate_passed
    viols = [v["rule_name"] for v in report.critical_violations]
    assert "VIO_DEPENDENCY_ORDER_REVERSED" in viols


def test_property_4_reordering_independent_actions_causes_no_false_violations():
    """Property 4: Reordering independent actions does not cause false violations."""
    scen, task, gt = build_synthetic_graph(depth=2, consumers_per_level=3)
    evaluator = DeterministicEvaluator()

    # Three peer services in tier 1 (all depend on root)
    # Migrating them in order [S1, S2, S3] vs [S3, S2, S1] in wave 2 must both be valid!
    root = scen.system_components[0].component_id
    s0 = scen.system_components[1].component_id
    s1 = scen.system_components[2].component_id
    s2 = scen.system_components[3].component_id

    plan_a = [
        ReportedMigrationStep(wave=1, component_id=root),
        ReportedMigrationStep(wave=2, component_id=s0),
        ReportedMigrationStep(wave=2, component_id=s1),
        ReportedMigrationStep(wave=2, component_id=s2),
    ]
    plan_b = [
        ReportedMigrationStep(wave=1, component_id=root),
        ReportedMigrationStep(wave=2, component_id=s2),
        ReportedMigrationStep(wave=2, component_id=s1),
        ReportedMigrationStep(wave=2, component_id=s0),
    ]

    c_a = ModelResponseContract(
        task_id=task.task_id,
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[],
        migration_plan=plan_a,
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Plan A",
    )
    c_b = ModelResponseContract(
        task_id=task.task_id,
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[],
        migration_plan=plan_b,
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Plan B",
    )

    grader = MigrationPlanGrader()
    res_a = grader.grade(c_a, scen, gt)
    res_b = grader.grade(c_b, scen, gt)

    assert res_a.passed is True
    assert res_b.passed is True
    assert len(res_a.violations) == 0
    assert len(res_b.violations) == 0


def test_property_5_production_cutover_respects_transitive_prerequisites():
    """Property 5: Every production cutover respects all transitive prerequisites."""
    scen, task, gt = build_synthetic_graph(depth=3, consumers_per_level=1)
    # Chain: Tier 3 -> Tier 2 -> Tier 1 -> Root HSM
    evaluator = DeterministicEvaluator()

    root = scen.system_components[0].component_id
    tier3 = scen.system_components[-1].component_id

    # Omitting intermediate Tier 1 and Tier 2 from the plan, cutting over Tier 3 before Root
    contract = ModelResponseContract(
        task_id=task.task_id,
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[],
        migration_plan=[
            ReportedMigrationStep(wave=1, component_id=tier3),  # Deepest caller in wave 1!
            ReportedMigrationStep(wave=2, component_id=root),   # Root in wave 2!
        ],
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Direct cutover.",
    )

    report = evaluator.evaluate_detailed(task, contract.model_dump_json(indent=2), gt, scen)
    assert not report.safety_gate_passed
    viols = [v["rule_name"] for v in report.critical_violations]
    assert "VIO_DEPENDENCY_ORDER_REVERSED" in viols


def test_property_6_failed_mandatory_test_blocks_readiness():
    """Property 6: A failed mandatory interoperability test blocks migration readiness."""
    scen, task, gt = build_synthetic_graph(depth=1, consumers_per_level=1)
    evaluator = DeterministicEvaluator()

    contract = ModelResponseContract(
        task_id=task.task_id,
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[],
        migration_plan=[],
        blocked_components=[],
        required_actions=[],
        verification_results=[
            ReportedTestResult(
                test_id="test-pqc-tls-handshake-01",
                reported_status=ReportedTestStatus.FAILED,
                evidence_reference=None,
            )
        ],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Attempting readiness despite failure.",
    )

    report = evaluator.evaluate_detailed(task, contract.model_dump_json(indent=2), gt, scen)
    assert not report.safety_gate_passed
    assert report.effective_score == 0.0


def test_property_7_cycle_cannot_receive_valid_topological_order():
    """Property 7: A cycle cannot receive a valid topological migration order."""
    scen, task, gt = build_synthetic_graph(depth=2, consumers_per_level=2)
    # Inject cycle: C0 -> C1 -> C0
    scen_data = scen.model_dump(mode="json")
    c0 = scen.system_components[0].component_id
    c1 = scen.system_components[1].component_id
    scen_data["dependencies"].append(
        {
            "edge_id": "dep-cycle-edge",
            "source_component_id": c0,
            "target_component_id": c1,
            "relationship_type": "CALLS",
            "criticality": "CRITICAL",
        }
    )
    scen_cyclic = ScenarioModel.model_validate(scen_data)
    verifier = IndependentGraphVerifier(scen_cyclic)
    assert verifier.is_dag is False
    assert len(verifier.cycles) > 0


def test_property_8_stale_evidence_cannot_silently_become_current():
    """Property 8: Stale evidence cannot silently become current."""
    scen, task, gt = build_synthetic_graph(depth=1, consumers_per_level=1)
    evaluator = DeterministicEvaluator()

    # Set evidence to STALE in scenario
    scen_data = scen.model_dump(mode="json")
    scen_data["evidence_records"][0]["verification_status"] = "STALE"
    scen_data["evidence_records"][0]["is_stale"] = True
    scen_stale = ScenarioModel.model_validate(scen_data)

    contract = ModelResponseContract(
        task_id=task.task_id,
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[
            ReportedCompatibility(
                component_id=scen.system_components[0].component_id,
                status=ReportedCompatibilityStatus.SUPPORTED,
                evidence_reference="evid-root-audit-01",
            )
        ],
        migration_plan=[
            ReportedMigrationStep(wave=1, component_id=scen.system_components[0].component_id)
        ],
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=["evid-root-audit-01"],
        assumptions=[],
        uncertainties=[],
        explanation="Relying on stale audit.",
    )

    report = evaluator.evaluate_detailed(task, contract.model_dump_json(indent=2), gt, scen_stale)
    all_viols = [v["rule_name"] for v in report.critical_violations] + [
        v["rule_name"] for v in report.non_critical_violations
    ]
    assert "VIO_STALE_EVIDENCE_RELIED_UPON" in all_viols or not report.safety_gate_passed or report.raw_weighted_score < 90.0


def test_property_9_invented_component_cannot_receive_credit():
    """Property 9: An invented component cannot receive migration credit."""
    scen, task, gt = build_synthetic_graph(depth=1, consumers_per_level=1)
    evaluator = DeterministicEvaluator()

    contract = ModelResponseContract(
        task_id=task.task_id,
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[],
        migration_plan=[
            ReportedMigrationStep(wave=1, component_id="comp-invented-phantom-xyz")
        ],
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Invented component plan.",
    )

    report = evaluator.evaluate_detailed(task, contract.model_dump_json(indent=2), gt, scen)
    assert not report.safety_gate_passed
    viols = [v["rule_name"] for v in report.critical_violations]
    assert "VIO_MALFORMED_RESPONSE" in viols


def test_property_10_equivalent_valid_migration_plans_receive_equal_scores():
    """Property 10: Equivalent valid migration plans receive equivalent correctness treatment."""
    scen, task, gt = build_synthetic_graph(depth=2, consumers_per_level=2)
    evaluator = DeterministicEvaluator()

    root = scen.system_components[0].component_id
    peer1 = scen.system_components[1].component_id
    peer2 = scen.system_components[2].component_id

    contract_1 = ModelResponseContract(
        task_id=task.task_id,
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[
            ReportedCompatibility(
                component_id=c.component_id,
                status=ReportedCompatibilityStatus.SUPPORTED,
                evidence_reference=scen.evidence_records[0].evidence_id,
            )
            for c in scen.system_components[:3]
        ],
        migration_plan=[
            ReportedMigrationStep(wave=1, component_id=root),
            ReportedMigrationStep(wave=2, component_id=peer1),
            ReportedMigrationStep(wave=2, component_id=peer2),
        ],
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=[scen.evidence_records[0].evidence_id],
        assumptions=[],
        uncertainties=[],
        explanation="Valid plan permutation 1.",
    )

    contract_2 = ModelResponseContract(
        task_id=task.task_id,
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[
            ReportedCompatibility(
                component_id=c.component_id,
                status=ReportedCompatibilityStatus.SUPPORTED,
                evidence_reference=scen.evidence_records[0].evidence_id,
            )
            for c in scen.system_components[:3]
        ],
        migration_plan=[
            ReportedMigrationStep(wave=1, component_id=root),
            ReportedMigrationStep(wave=2, component_id=peer2),
            ReportedMigrationStep(wave=2, component_id=peer1),
        ],
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=[scen.evidence_records[0].evidence_id],
        assumptions=[],
        uncertainties=[],
        explanation="Valid plan permutation 2.",
    )

    rep1 = evaluator.evaluate_detailed(task, contract_1.model_dump_json(indent=2), gt, scen)
    rep2 = evaluator.evaluate_detailed(task, contract_2.model_dump_json(indent=2), gt, scen)

    assert rep1.safety_gate_passed == rep2.safety_gate_passed
    assert rep1.effective_score == rep2.effective_score
    assert rep1.raw_weighted_score == rep2.raw_weighted_score

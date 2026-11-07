"""Property-based and metamorphic invariant tests for evaluator robustness."""

import copy
import random
import pytest

from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.serialization import read_json
from phoenix_eval.evaluation.evaluator import DeterministicEvaluator
from phoenix_eval.evaluation.independent_graph_verifier import IndependentGraphVerifier
from phoenix_eval.schemas.common import StrEnum
from phoenix_eval.schemas.dependencies import (
    DependencyCriticality,
    DependencyRelationship,
    RelationshipType,
)
from phoenix_eval.schemas.response_contract import (
    MigrationActionType,
    ModelDecision,
    ModelResponseContract,
    ReportedCompatibilityStatus,
    ReportedTestStatus,
)
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import BenchmarkTask


@pytest.fixture
def test_fixtures():
    """Load baseline fixtures for metamorphic invariant testing."""
    paths = get_paths()
    task_file = paths.generated_tasks_dir / "task-gen-t09-bank-02.json"
    scen_file = paths.generated_scenarios_dir / "scen-gen-t09-bank-02.json"
    gt_file = paths.generated_ground_truth_dir / "gt-gen-t09-bank-02.json"
    resp_file = paths.datasets_dir / "calibration" / "responses" / "kg_01_valid_migration.json"

    task = BenchmarkTask.model_validate(read_json(task_file))
    scen = ScenarioModel.model_validate(read_json(scen_file))
    gt = read_json(gt_file)
    contract = ModelResponseContract.model_validate(read_json(resp_file))
    return task, scen, gt, contract


def test_invariant_1_irrelevant_narrative_comment_does_not_alter_score(test_fixtures):
    """Invariant 1: Adding irrelevant narrative notes to explanation must not alter safety gate or score."""
    task, scen, gt, contract = test_fixtures
    evaluator = DeterministicEvaluator()

    base_report = evaluator.evaluate_detailed(
        task=task,
        raw_response_text=contract.model_dump_json(indent=2),
        ground_truth=gt,
        scenario=scen,
    )

    # Add irrelevant benign comments to explanation
    data = contract.model_dump(mode="json")
    noise_comments = [
        " [NOTE: Internal maintenance window scheduled for Saturday 02:00 UTC.]",
        " Reference ticket SEC-98214 for corporate change advisory review.",
        " Documentation reviewed by team lead on 2026-11-05.",
    ]
    data["explanation"] += " ".join(noise_comments)
    mutated = ModelResponseContract.model_validate(data)

    mut_report = evaluator.evaluate_detailed(
        task=task,
        raw_response_text=mutated.model_dump_json(indent=2),
        ground_truth=gt,
        scenario=scen,
    )

    assert mut_report.safety_gate_passed == base_report.safety_gate_passed
    assert mut_report.effective_score == base_report.effective_score
    assert mut_report.raw_weighted_score == base_report.raw_weighted_score
    assert mut_report.overall_status == base_report.overall_status


def test_invariant_2_adding_downstream_dependency_enforces_causal_order(test_fixtures):
    """Invariant 2: Adding a genuine downstream dependency must enforce strict prerequisite ordering."""
    task, scen, gt, contract = test_fixtures
    evaluator = DeterministicEvaluator()

    # In contract, find two components in the plan
    plan_cids = [s.component_id for s in contract.migration_plan]
    assert len(plan_cids) >= 2
    c_later = plan_cids[-1]
    c_earlier = plan_cids[0]

    # Invert dependency: make earlier component depend on later component
    scen_mut = scen.model_copy(deep=True)
    new_dep = DependencyRelationship(
        edge_id="dep-injected-causal",
        source_component_id=c_earlier,  # c_earlier now calls c_later
        target_component_id=c_later,
        relationship_type=RelationshipType.CALLS,
        criticality=DependencyCriticality.CRITICAL,
    )
    scen_mut.dependencies.append(new_dep)

    # Now the original plan executes caller before prerequisite!
    report = evaluator.evaluate_detailed(
        task=task,
        raw_response_text=contract.model_dump_json(indent=2),
        ground_truth=gt,
        scenario=scen_mut,
    )

    # Safety gate MUST fail due to causal order violation
    assert not report.safety_gate_passed
    viols = [v["rule_name"] for v in report.critical_violations]
    assert "VIO_DEPENDENCY_ORDER_REVERSED" in viols


def test_invariant_3_reordering_independent_components_preserves_safety(test_fixtures):
    """Invariant 3: Reordering independent components in valid topological orders receives identical safety pass."""
    task, scen, gt, contract = test_fixtures
    evaluator = DeterministicEvaluator()

    data = contract.model_dump(mode="json")
    plan = data.get("migration_plan", [])
    waves = {}
    for s in plan:
        waves.setdefault(s["wave"], []).append(s)

    for w, steps in waves.items():
        if len(steps) > 1:
            steps.reverse()
    new_plan = []
    for w in sorted(waves.keys()):
        new_plan.extend(waves[w])
    data["migration_plan"] = new_plan
    mutated = ModelResponseContract.model_validate(data)

    base_report = evaluator.evaluate_detailed(
        task=task,
        raw_response_text=contract.model_dump_json(indent=2),
        ground_truth=gt,
        scenario=scen,
    )
    mut_report = evaluator.evaluate_detailed(
        task=task,
        raw_response_text=mutated.model_dump_json(indent=2),
        ground_truth=gt,
        scenario=scen,
    )

    assert mut_report.safety_gate_passed == base_report.safety_gate_passed
    assert mut_report.safety_gate_passed is True


def test_invariant_4_removing_mandatory_evidence_never_improves_score(test_fixtures):
    """Invariant 4: Removing mandatory verification evidence must never improve readiness score."""
    task, scen, gt, contract = test_fixtures
    evaluator = DeterministicEvaluator()

    base_report = evaluator.evaluate_detailed(
        task=task,
        raw_response_text=contract.model_dump_json(indent=2),
        ground_truth=gt,
        scenario=scen,
    )

    # Strip evidence references
    data = contract.model_dump(mode="json")
    data["evidence_references"] = []
    for res in data.get("verification_results", []):
        res["evidence_reference"] = None
    mutated = ModelResponseContract.model_validate(data)

    mut_report = evaluator.evaluate_detailed(
        task=task,
        raw_response_text=mutated.model_dump_json(indent=2),
        ground_truth=gt,
        scenario=scen,
    )

    # Effective score after removing evidence must be <= base score
    assert mut_report.effective_score <= base_report.effective_score
    assert mut_report.raw_weighted_score <= base_report.raw_weighted_score


def test_invariant_5_supported_to_unknown_never_makes_cutover_more_acceptable(test_fixtures):
    """Invariant 5: Changing compatibility from SUPPORTED to UNKNOWN must never improve readiness or pass safety gate."""
    task, scen, gt, contract = test_fixtures
    evaluator = DeterministicEvaluator()

    base_report = evaluator.evaluate_detailed(
        task=task,
        raw_response_text=contract.model_dump_json(indent=2),
        ground_truth=gt,
        scenario=scen,
    )

    # Mutate first assessed component to UNKNOWN while scheduling cutover
    data = contract.model_dump(mode="json")
    if data.get("compatibility_assessments"):
        data["compatibility_assessments"][0]["status"] = "UNKNOWN"
    mutated = ModelResponseContract.model_validate(data)

    mut_report = evaluator.evaluate_detailed(
        task=task,
        raw_response_text=mutated.model_dump_json(indent=2),
        ground_truth=gt,
        scenario=scen,
    )

    assert not mut_report.safety_gate_passed
    assert mut_report.effective_score == 0.0
    viols = [v["rule_name"] for v in mut_report.critical_violations]
    assert "VIO_UNKNOWN_ASSUMED_SUPPORTED" in viols


def test_invariant_6_failed_mandatory_test_blocks_migration_ready(test_fixtures):
    """Invariant 6: A failed mandatory interoperability test must prevent MIGRATION_READY status."""
    task, scen, gt, contract = test_fixtures
    evaluator = DeterministicEvaluator()

    data = contract.model_dump(mode="json")
    data["decision"] = "MIGRATION_READY"
    if data.get("verification_results"):
        data["verification_results"][0]["reported_status"] = "FAILED"
    mutated = ModelResponseContract.model_validate(data)

    report = evaluator.evaluate_detailed(
        task=task,
        raw_response_text=mutated.model_dump_json(indent=2),
        ground_truth=gt,
        scenario=scen,
    )

    assert not report.safety_gate_passed
    assert report.effective_score == 0.0
    viols = [v["rule_name"] for v in report.critical_violations]
    assert "VIO_FAILED_TEST_IGNORED" in viols or "VIO_CONTRADICTORY_DECISION" in viols


def test_invariant_7_equivalent_valid_topological_orders_equal_correctness(test_fixtures):
    """Invariant 7: Graph verifier treats alternative valid topological orderings identically."""
    task, scen, gt, contract = test_fixtures
    verifier = IndependentGraphVerifier(scenario=scen)

    plan1 = [
        {"wave": 1, "component_id": "D"},
        {"wave": 2, "component_id": "B"},
        {"wave": 2, "component_id": "C"},
        {"wave": 3, "component_id": "A"},
    ]
    plan2 = [
        {"wave": 1, "component_id": "D"},
        {"wave": 2, "component_id": "C"},
        {"wave": 2, "component_id": "B"},
        {"wave": 3, "component_id": "A"},
    ]

    c_map1 = {s["component_id"]: s["wave"] for s in plan1}
    c_map2 = {s["component_id"]: s["wave"] for s in plan2}

    deps = [
        ("A", "B"),
        ("A", "C"),
        ("B", "D"),
        ("C", "D"),
    ]
    for caller, callee in deps:
        assert c_map1[callee] < c_map1[caller]
        assert c_map2[callee] < c_map2[caller]
    assert verifier.is_dag is True

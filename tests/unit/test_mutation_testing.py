"""Unit tests for the mutation testing engine and exploit operators."""

import pytest

from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.serialization import read_json
from phoenix_eval.evaluation.evaluator import DeterministicEvaluator
from phoenix_eval.evaluation.mutation_testing import (
    MUTATION_OPERATORS,
    MutationResult,
    MutationSuiteSummary,
    MutationTestingEngine,
    mutate_add_nonexistent_component,
    mutate_conditional_to_migration_ready,
    mutate_failed_test_to_passed,
    mutate_introduce_cycle,
    mutate_remove_prerequisite,
    mutate_remove_rollback_capability,
    mutate_remove_validation_evidence,
    mutate_reverse_dependency_order,
    mutate_supported_to_unknown,
    mutate_unsafe_in_explanation,
)
from phoenix_eval.schemas.response_contract import (
    ModelDecision,
    ModelResponseContract,
    ReportedCompatibilityStatus,
)
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import BenchmarkTask


@pytest.fixture
def baseline_fixtures():
    """Load baseline calibration task and response fixture."""
    paths = get_paths()
    task_file = paths.generated_tasks_dir / "task-gen-t09-bank-02.json"
    scen_file = paths.generated_scenarios_dir / "scen-gen-t09-bank-02.json"
    gt_file = paths.generated_ground_truth_dir / "gt-gen-t09-bank-02.json"
    resp_file = paths.datasets_dir / "calibration" / "responses" / "kg_01_valid_migration.json"

    task = BenchmarkTask.model_validate(read_json(task_file))
    scen = ScenarioModel.model_validate(read_json(scen_file))
    gt = read_json(gt_file)
    resp_data = read_json(resp_file)
    for s in resp_data.get("migration_plan", []):
        s["rollback_trigger"] = "HEARTBEAT_TIMEOUT"
        s["rollback_action"] = "TRIGGER_CANARY_ROLLBACK"
        s["recovery_mechanism"] = "DUAL_STACK_FALLBACK"
    contract = ModelResponseContract.model_validate(resp_data)
    return task, scen, gt, contract


def test_mutation_operators_count():
    """Verify exactly 10 distinct mutation operators are registered."""
    assert len(MUTATION_OPERATORS) == 10
    names = [name for name, _, _, _ in MUTATION_OPERATORS]
    assert len(set(names)) == 10
    assert "MUT_REMOVE_PREREQUISITE" in names
    assert "MUT_REVERSE_DEPENDENCY_ORDER" in names
    assert "MUT_SUPPORTED_TO_UNKNOWN" in names
    assert "MUT_REMOVE_VALIDATION_EVIDENCE" in names
    assert "MUT_ADD_NONEXISTENT_COMPONENT" in names
    assert "MUT_FAILED_TEST_TO_PASSED" in names
    assert "MUT_REMOVE_ROLLBACK_CAPABILITY" in names
    assert "MUT_INTRODUCE_CYCLE" in names
    assert "MUT_CONDITIONAL_TO_MIGRATION_READY" in names
    assert "MUT_UNSAFE_IN_EXPLANATION" in names


def test_mutation_operator_remove_prerequisite(baseline_fixtures):
    _, _, _, contract = baseline_fixtures
    mutated = mutate_remove_prerequisite(contract)
    assert len(mutated.migration_plan) < len(contract.migration_plan)
    assert not any(s.wave == 1 for s in mutated.migration_plan)


def test_mutation_operator_reverse_dependency_order(baseline_fixtures):
    _, _, _, contract = baseline_fixtures
    mutated = mutate_reverse_dependency_order(contract)
    assert len(mutated.migration_plan) == len(contract.migration_plan)
    # First step should now have higher wave number
    assert mutated.migration_plan[0].wave >= mutated.migration_plan[-1].wave


def test_mutation_operator_supported_to_unknown(baseline_fixtures):
    _, _, _, contract = baseline_fixtures
    mutated = mutate_supported_to_unknown(contract)
    assert mutated.compatibility_assessments[0].status == ReportedCompatibilityStatus.UNKNOWN


def test_mutation_operator_remove_validation_evidence(baseline_fixtures):
    _, _, _, contract = baseline_fixtures
    mutated = mutate_remove_validation_evidence(contract)
    for res in mutated.verification_results:
        assert "bogus" in str(res.evidence_reference)


def test_mutation_operator_add_nonexistent_component(baseline_fixtures):
    _, _, _, contract = baseline_fixtures
    mutated = mutate_add_nonexistent_component(contract)
    plan_cids = [s.component_id for s in mutated.migration_plan]
    assert "comp-hallucinated-phantom-99" in plan_cids


def test_mutation_operator_failed_test_to_passed(baseline_fixtures):
    _, _, _, contract = baseline_fixtures
    mutated = mutate_failed_test_to_passed(contract)
    assert mutated.decision == ModelDecision.MIGRATION_READY
    # Should contain a test reported as FAILED alongside MIGRATION_READY
    assert any(t.reported_status.value == "FAILED" for t in mutated.verification_results)


def test_mutation_operator_remove_rollback_capability(baseline_fixtures):
    _, _, _, contract = baseline_fixtures
    mutated = mutate_remove_rollback_capability(contract)
    for step in mutated.migration_plan:
        assert step.rollback_trigger is None
        assert step.recovery_mechanism is None


def test_mutation_operator_introduce_cycle(baseline_fixtures):
    _, _, _, contract = baseline_fixtures
    mutated = mutate_introduce_cycle(contract)
    assert len(mutated.identified_dependencies) > len(contract.identified_dependencies)


def test_mutation_operator_conditional_to_migration_ready(baseline_fixtures):
    _, _, _, contract = baseline_fixtures
    mutated = mutate_conditional_to_migration_ready(contract)
    assert mutated.decision == ModelDecision.MIGRATION_READY
    assert any(s.is_conditional for s in mutated.migration_plan)


def test_mutation_operator_unsafe_in_explanation(baseline_fixtures):
    _, _, _, contract = baseline_fixtures
    mutated = mutate_unsafe_in_explanation(contract)
    assert "bypass safety gate" in mutated.explanation.lower()


def test_mutation_suite_kill_rate(baseline_fixtures):
    """Run full mutation suite and verify 100% kill rate on critical safety mutations."""
    task, scen, gt, contract = baseline_fixtures
    engine = MutationTestingEngine()
    summary: MutationSuiteSummary = engine.run_suite(
        baseline_contract=contract,
        task=task,
        scenario=scen,
        ground_truth=gt,
    )
    assert summary.total_mutations == 10
    assert summary.detected_count == 10
    assert summary.escaped_count == 0
    assert summary.kill_rate == 100.0
    assert summary.critical_kill_rate == 100.0

    d = summary.to_dict()
    assert d["kill_rate"] == 100.0
    assert d["critical_kill_rate"] == 100.0
    assert len(d["results"]) == 10

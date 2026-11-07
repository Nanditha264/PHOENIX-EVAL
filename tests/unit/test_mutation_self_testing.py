"""Unit tests for mutation engine self-testing, classifications, and denominator integrity."""

import hashlib
import pytest

from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.serialization import read_json
from phoenix_eval.evaluation.evaluator import DeterministicEvaluator
from phoenix_eval.evaluation.mutation_testing import (
    ADVANCED_MUTATION_CATALOG,
    MutationClassification,
    MutationFamily,
    MutationResult,
    MutationSuiteSummary,
    MutationTestingEngine,
)
from phoenix_eval.schemas.response_contract import ModelResponseContract
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import BenchmarkTask


@pytest.fixture
def baseline_fixtures():
    """Load baseline fixtures."""
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


def test_advanced_catalog_coverage():
    """Verify that the advanced mutation catalog contains exactly 28 operators across all 4 families."""
    assert len(ADVANCED_MUTATION_CATALOG) == 28
    families = {op[1] for op in ADVANCED_MUTATION_CATALOG}
    assert families == {
        MutationFamily.DEPENDENCY,
        MutationFamily.COMPATIBILITY,
        MutationFamily.EVIDENCE,
        MutationFamily.SAFETY,
    }

    # Verify counts per family
    dep_ops = [op for op in ADVANCED_MUTATION_CATALOG if op[1] == MutationFamily.DEPENDENCY]
    compat_ops = [op for op in ADVANCED_MUTATION_CATALOG if op[1] == MutationFamily.COMPATIBILITY]
    evid_ops = [op for op in ADVANCED_MUTATION_CATALOG if op[1] == MutationFamily.EVIDENCE]
    safety_ops = [op for op in ADVANCED_MUTATION_CATALOG if op[1] == MutationFamily.SAFETY]

    assert len(dep_ops) == 9
    assert len(compat_ops) == 5
    assert len(evid_ops) == 7
    assert len(safety_ops) == 7


def test_self_testing_noop_mutation_classified_not_applicable(baseline_fixtures):
    """Verify that a no-op mutator that makes zero changes is strictly classified as NOT_APPLICABLE."""
    task, scen, gt, contract = baseline_fixtures
    engine = MutationTestingEngine()

    def noop_mutator(c: ModelResponseContract) -> ModelResponseContract:
        # Returns identical copy
        return ModelResponseContract.model_validate(c.model_dump(mode="json"))

    res = engine.run_mutation(
        operator_name="MUT_TEST_NOOP",
        description="No-op mutation test",
        is_critical=True,
        mutator_fn=noop_mutator,
        baseline_contract=contract,
        task=task,
        scenario=scen,
        ground_truth=gt,
    )

    assert res.classification == MutationClassification.NOT_APPLICABLE
    assert not res.detected
    assert res.actual_outcome == "NO_OP_MUTATION"
    assert "precondition absent" in res.details.get("note", "")


def test_self_testing_schema_rejection_classified_detected(baseline_fixtures):
    """Verify that a mutator that violates strict schema validation is caught at parsing."""
    task, scen, gt, contract = baseline_fixtures
    engine = MutationTestingEngine()

    def invalid_mutator(c: ModelResponseContract) -> ModelResponseContract:
        data = c.model_dump(mode="json")
        data["decision"] = "NON_EXISTENT_ENUM_VALUE_BOGUS"
        return ModelResponseContract.model_validate(data)

    res = engine.run_mutation(
        operator_name="MUT_TEST_INVALID_SCHEMA",
        description="Invalid schema mutation test",
        is_critical=True,
        mutator_fn=invalid_mutator,
        baseline_contract=contract,
        task=task,
        scenario=scen,
        ground_truth=gt,
    )

    assert res.classification == MutationClassification.DETECTED
    assert res.detected
    assert res.effective_score == 0.0
    assert "VIO_MALFORMED_RESPONSE" in res.violations_triggered


def test_self_testing_denominator_accuracy(baseline_fixtures):
    """Verify that not-applicable or invalid mutations do not artificially inflate the kill rate denominator."""
    task, scen, gt, contract = baseline_fixtures
    engine = MutationTestingEngine()

    # Run on baseline without populating rollback procedures -> MUT_REMOVE_ROLLBACK_CAPABILITY is a no-op
    # Contract in kg_01 has null rollback fields
    summary = engine.run_suite(
        baseline_contract=contract,
        task=task,
        scenario=scen,
        ground_truth=gt,
        use_advanced_catalog=False,
    )

    # Total = 10, NOT_APPLICABLE = 1 (rollback no-op), Applicable = 9
    assert summary.total_mutations == 10
    assert summary.not_applicable_count == 1
    assert summary.applicable_mutations == 9
    assert summary.detected_count == 9
    # Kill rate must be computed over applicable mutations only: 9 / 9 = 100.0%
    assert summary.kill_rate == 100.0
    assert summary.escaped_count == 0


def test_composite_mutations_applied_together(baseline_fixtures):
    """Verify that multiple mutations applied concurrently trigger all respective violations."""
    task, scen, gt, contract = baseline_fixtures
    engine = MutationTestingEngine()

    def composite_mutator(c: ModelResponseContract) -> ModelResponseContract:
        data = c.model_dump(mode="json")
        # 1. Reverse order
        plan = data.get("migration_plan", [])
        if len(plan) >= 2:
            plan[0]["wave"] = 2
            plan[1]["wave"] = 1
        # 2. Supported to unknown
        assessments = data.get("compatibility_assessments", [])
        if assessments:
            assessments[0]["status"] = "UNKNOWN"
        # 3. Hallucinate evidence
        data["evidence_references"] = ["evid-composite-fabricated-01"]
        return ModelResponseContract.model_validate(data)

    res = engine.run_mutation(
        operator_name="MUT_COMPOSITE_TRIPLE",
        description="Composite mutation combining ordering, compatibility, and evidence tampering",
        is_critical=True,
        mutator_fn=composite_mutator,
        baseline_contract=contract,
        task=task,
        scenario=scen,
        ground_truth=gt,
    )

    assert res.classification == MutationClassification.DETECTED
    assert res.detected
    assert not res.safety_gate_passed
    assert res.effective_score == 0.0
    # Both critical violations must be present
    assert "VIO_DEPENDENCY_ORDER_REVERSED" in res.violations_triggered
    assert "VIO_UNKNOWN_ASSUMED_SUPPORTED" in res.violations_triggered

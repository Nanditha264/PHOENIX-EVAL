"""Unit tests for Phase 5 experiment and model comparability evaluation."""

from phoenix_eval.analysis.comparability import ExperimentComparabilityEvaluator
from phoenix_eval.analysis.ingestion import ExperimentIngestionValidator
from phoenix_eval.analysis.schemas import ComparabilityClassification


def test_comparability_within_mock_experiment():
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-comparison-001")
    evaluator = ExperimentComparabilityEvaluator()

    assessment = evaluator.assess_experiments([data])
    assert len(assessment.model_pairs) == 1
    pair = assessment.model_pairs[0]
    assert pair.model_a == "mock-model-v1"
    assert pair.model_b == "mock-refusal-v1"
    assert pair.common_task_count == 2
    assert pair.disjoint_task_count == 0
    assert pair.classification == ComparabilityClassification.COMPARABLE


def test_comparability_rejects_mock_vs_real():
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-comparison-001")
    evaluator = ExperimentComparabilityEvaluator()

    # Model A is mock, Model B is flagged as real
    runs_a = [r for r in data.valid_runs if r.model_identifier == "mock-model-v1"]
    runs_b = [
        r.model_copy(update={"is_mock": False})
        for r in data.valid_runs
        if r.model_identifier == "mock-refusal-v1"
    ]
    cfg_b = data.manifest.config.model_copy(update={"mode": "api"})
    manifest_b = data.manifest.model_copy(update={"config": cfg_b})

    pair = evaluator.evaluate_model_pair(
        model_a="mock-model-v1",
        runs_a=runs_a,
        manifest_a=data.manifest,
        model_b="real-gpt-4o",
        runs_b=runs_b,
        manifest_b=manifest_b,
    )

    assert pair.classification == ComparabilityClassification.NOT_COMPARABLE
    assert any("Cannot scientifically compare" in r for r in pair.reasons)


def test_comparability_rejects_disjoint_tasks():
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-comparison-001")
    evaluator = ExperimentComparabilityEvaluator()

    runs_a = [r for r in data.valid_runs if r.task_id == "task-gen-t01-bank-01"]
    runs_b = [r for r in data.valid_runs if r.task_id == "task-gen-t01-telco-02"]

    pair = evaluator.evaluate_model_pair(
        model_a="model_a",
        runs_a=runs_a,
        manifest_a=data.manifest,
        model_b="model_b",
        runs_b=runs_b,
        manifest_b=data.manifest,
    )

    assert pair.common_task_count == 0
    assert pair.classification == ComparabilityClassification.NOT_COMPARABLE
    assert any("Zero common tasks" in r for r in pair.reasons)


def test_comparability_flags_partial_overlap():
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-comparison-001")
    evaluator = ExperimentComparabilityEvaluator()

    runs_a = data.valid_runs  # both tasks
    runs_b = [r for r in data.valid_runs if r.task_id == "task-gen-t01-bank-01"]  # only 1 task

    pair = evaluator.evaluate_model_pair(
        model_a="model_a",
        runs_a=runs_a,
        manifest_a=data.manifest,
        model_b="model_b",
        runs_b=runs_b,
        manifest_b=data.manifest,
    )

    assert pair.common_task_count == 1
    assert pair.disjoint_task_count == 1
    assert pair.classification == ComparabilityClassification.COMPARABLE_WITH_LIMITATIONS

"""Unit tests for Phase 5 benchmark performance metrics analyzer."""

from phoenix_eval.analysis.ingestion import ExperimentIngestionValidator
from phoenix_eval.analysis.performance import BenchmarkPerformanceAnalyzer
from phoenix_eval.analysis.schemas import TrialConsistencyOutcome


def test_overall_model_metrics():
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-comparison-001")
    analyzer = BenchmarkPerformanceAnalyzer()

    overall = analyzer.compute_overall_metrics(data)
    assert len(overall) == 2
    models = {m.model_identifier: m for m in overall}
    assert "mock-model-v1" in models
    assert "mock-refusal-v1" in models

    m1 = models["mock-model-v1"]
    assert m1.scheduled_runs == 4
    assert m1.evaluated_responses == 4
    assert m1.completion_rate == 1.0
    assert m1.is_mock is True
    assert m1.safety_gate_passed_count == 0
    assert m1.safety_gate_failed_count == 4
    assert m1.safety_gate_failure_rate == 1.0
    assert m1.safety_gate_failure_rate_ci[0] > 0.50
    assert m1.safety_gate_failure_rate_ci[1] == 1.0
    assert m1.parsing_failures_count == 4


def test_dimension_metrics():
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-comparison-001")
    analyzer = BenchmarkPerformanceAnalyzer()

    dims = analyzer.compute_dimension_metrics(data)
    # 6 dimensions x 2 models = 12 records
    assert len(dims) == 12
    dim_names = {d.dimension_name for d in dims}
    assert "dependency_identification" in dim_names
    assert "compatibility_reasoning" in dim_names
    assert "migration_plan_correctness" in dim_names
    assert "evidence_and_uncertainty" in dim_names
    assert "validation_and_safety_gates" in dim_names
    assert "explanation_and_traceability" in dim_names

    for d in dims:
        assert d.valid_response_count == 4
        assert 0.0 <= d.mean_normalized_score <= 1.0


def test_task_family_metrics():
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-comparison-001")
    analyzer = BenchmarkPerformanceAnalyzer()

    fams = analyzer.compute_task_family_metrics(data)
    assert len(fams) == 2  # Both models evaluated on T01
    for f in fams:
        assert f.family_id == "T01"
        assert f.family_name == "Hidden Downstream Dependency"
        assert f.evaluated_response_count == 4
        assert f.critical_violations_count > 0


def test_domain_and_difficulty_metrics():
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-comparison-001")
    analyzer = BenchmarkPerformanceAnalyzer()

    doms = analyzer.compute_domain_metrics(data)
    # 2 tasks: bank (BANKING_PAYMENTS) and telco (TELECOM_NETWORK) across 2 models = 4 records
    assert len(doms) == 4
    dom_names = {d.domain_name for d in doms}
    assert "BANKING_PAYMENTS" in dom_names
    assert "TELECOM_NETWORK" in dom_names

    diffs = analyzer.compute_difficulty_metrics(data)
    assert len(diffs) == 4
    diff_levels = {d.difficulty_level for d in diffs}
    assert "INTRODUCTORY" in diff_levels
    assert "INTERMEDIATE" in diff_levels


def test_trial_consistency():
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-comparison-001")
    analyzer = BenchmarkPerformanceAnalyzer()

    consistency = analyzer.compute_trial_consistency(data)
    # 2 tasks x 2 models = 4 records
    assert len(consistency) == 4
    for c in consistency:
        assert c.trial_count == 2
        assert len(c.effective_scores) == 2
        assert c.outcome == TrialConsistencyOutcome.STABLE_UNSAFE
        assert "Consistently failed safety gates" in c.interpretation

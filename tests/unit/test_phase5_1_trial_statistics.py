"""Regression tests for Phase 5.1 Defect 5: Trial-level statistical data preservation and aggregation."""

from phoenix_eval.analysis.ingestion import ExperimentIngestionValidator
from phoenix_eval.analysis.performance import BenchmarkPerformanceAnalyzer
from phoenix_eval.analysis.schemas import TrialConsistencyOutcome
from phoenix_eval.analysis.statistics import calculate_paired_comparison


def test_paired_comparison_preserves_trial_counts() -> None:
    """Ensure paired model comparison records both common task counts and trial counts."""
    scores_a = {"task-1": 80.0, "task-2": 90.0}
    scores_b = {"task-1": 70.0, "task-2": 85.0}

    comp = calculate_paired_comparison(
        model_a_scores=scores_a,
        model_b_scores=scores_b,
        model_a_name="Model A",
        model_b_name="Model B",
        model_a_trial_count=6,
        model_b_trial_count=6,
    )

    assert comp.common_tasks_count == 2
    assert comp.model_a_trial_count == 6
    assert comp.model_b_trial_count == 6
    assert comp.mean_difference == 7.5


def test_multi_trial_consistency_evaluation_on_phase5_1_experiment() -> None:
    """Ensure multiple trials in exp-mock-phase5-1-001 produce trial consistency records."""
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-phase5-1-001")

    perf = BenchmarkPerformanceAnalyzer()
    consistency = perf.compute_trial_consistency(data)

    assert len(consistency) > 0

    # Check valid migration consistency
    valid_cons = [c for c in consistency if c.model_identifier == "mock-valid-migration"]
    assert len(valid_cons) == 2  # 2 tasks
    for c in valid_cons:
        assert c.trial_count == 2
        assert len(c.effective_scores) == 2
        # Deterministic valid mock produces zero variance across trials
        assert c.score_variance == 0.0
        assert c.outcome == TrialConsistencyOutcome.STABLE_CORRECT


def test_coordinator_aggregates_trials_without_overwriting() -> None:
    """Verify that coordinator averages multi-trial scores per task instead of overwriting."""
    from phoenix_eval.analysis.coordinator import Phase5AnalysisCoordinator

    coord = Phase5AnalysisCoordinator()
    coord.analyze_experiment("exp-mock-phase5-1-001")

    # In exp-mock-phase5-1-001, each model ran 2 tasks x 2 trials = 4 runs
    stats_file = coord.paths.results_dir / "statistics" / "statistics_exp-mock-phase5-1-001.json"
    from phoenix_eval.data.serialization import read_json

    stats_dict = read_json(stats_file)
    comparisons = stats_dict.get("paired_comparisons", [])
    assert len(comparisons) > 0

    for comp in comparisons:
        assert comp["common_tasks_count"] == 2
        assert comp["model_a_trial_count"] == 4
        assert comp["model_b_trial_count"] == 4

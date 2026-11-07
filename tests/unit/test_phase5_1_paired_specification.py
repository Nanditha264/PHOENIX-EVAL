"""Regression tests for Phase 5.1 Defect 4: Authoritative paired-case specifications and expected divergence."""

from phoenix_eval.analysis.ingestion import ExperimentIngestionValidator
from phoenix_eval.analysis.paired import PairedCaseAnalyzer
from phoenix_eval.analysis.schemas import PairedSensitivityOutcome


def test_paired_analysis_on_phase5_1_experiment() -> None:
    """Ensure PairedCaseAnalyzer correctly assesses sensitivity on exp-mock-phase5-1-001."""
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-phase5-1-001")

    analyzer = PairedCaseAnalyzer()
    items = analyzer.analyze_experiment(data)

    # 1. mock-valid-migration on hsm-support-01:
    # A has no blockers (MIGRATION_READY), B has comp-microservice-03 blocker (MIGRATION_BLOCKED)
    # Model correctly adapted decision -> CORRECT_SENSITIVITY
    valid_hsm = [
        it
        for it in items
        if it.pair_id == "hsm-support-01" and it.model_identifier == "mock-valid-migration"
    ]
    assert len(valid_hsm) == 1
    assert valid_hsm[0].classification == PairedSensitivityOutcome.CORRECT_SENSITIVITY
    assert valid_hsm[0].decision_a == "MIGRATION_READY"
    assert valid_hsm[0].decision_b == "MIGRATION_BLOCKED"

    # 2. Unevaluated pairs must be INSUFFICIENT_DATA
    unevaluated = [it for it in items if it.pair_id == "dependency-cycle-04"]
    assert len(unevaluated) > 0
    assert all(
        it.classification == PairedSensitivityOutcome.INSUFFICIENT_DATA for it in unevaluated
    )


def test_paired_analysis_respects_identical_expected_divergence() -> None:
    """When expected_divergence specifies identical ground truth, consistent decisions are CORRECT_SENSITIVITY."""
    from phoenix_eval.analysis.ingestion import ValidatedExperimentData
    from phoenix_eval.analysis.schemas import IngestionRecordStatus, IngestionReport
    from phoenix_eval.schemas.common import ExecutionStatus
    from phoenix_eval.schemas.experiments import (
        ExperimentConfig,
        ExperimentManifest,
        ExperimentRunRecord,
    )

    # Create dummy validated experiment data with identical safe pair
    pair_spec = {
        "pair_id": "test-safe-pair",
        "pair_type": "SAFE_EQUIVALENCE",
        "task_a_id": "task-safe-a",
        "task_b_id": "task-safe-b",
        "perturbed_property": "formatting only",
        "expected_divergence": {
            "ground_truth_a_blockers": [],
            "ground_truth_b_blockers": [],
            "ground_truth_a_cycle": False,
            "ground_truth_b_cycle": False,
        },
    }

    run_a = ExperimentRunRecord(
        experiment_id="exp-test",
        run_id="run-a",
        task_id="task-safe-a",
        scenario_id="scen-a",
        provider_name="mock",
        model_identifier="test-model",
        prompt_hash="dummy-prompt-hash-a",
        execution_status=ExecutionStatus.COMPLETED,
        safety_gate_passed=True,
        effective_score=95.0,
        overall_status="PASSED",
    )
    run_b = ExperimentRunRecord(
        experiment_id="exp-test",
        run_id="run-b",
        task_id="task-safe-b",
        scenario_id="scen-b",
        provider_name="mock",
        model_identifier="test-model",
        prompt_hash="dummy-prompt-hash-b",
        execution_status=ExecutionStatus.COMPLETED,
        safety_gate_passed=True,
        effective_score=95.0,
        overall_status="PASSED",
    )

    manifest = ExperimentManifest(
        experiment_id="exp-test",
        experiment_name="Test Safe Exp",
        config=ExperimentConfig(
            experiment_id="exp-test",
            experiment_name="Test Safe Exp",
            selected_models=["test-model"],
            selected_tasks=["task-safe-a", "task-safe-b"],
        ),
        runs=[run_a, run_b],
    )

    data = ValidatedExperimentData(
        manifest=manifest,
        valid_runs=[run_a, run_b],
        failed_runs=[],
        corrupted_runs=[],
        raw_responses={},
        evaluation_reports={},
        ingestion_report=IngestionReport(
            experiment_id="exp-test",
            import_status=IngestionRecordStatus.VALID,
            total_scheduled_runs=2,
            total_attempts=2,
            completed_runs=2,
            failed_runs=0,
            summary="test",
        ),
        is_mock=True,
    )

    analyzer = PairedCaseAnalyzer()
    analyzer.paired_cases = [pair_spec]

    results = analyzer.analyze_experiment(data)
    assert len(results) == 1
    # Because expected divergence is identical, producing identical decisions must NOT be flagged as MISSED_CHANGE
    assert results[0].classification == PairedSensitivityOutcome.CORRECT_SENSITIVITY

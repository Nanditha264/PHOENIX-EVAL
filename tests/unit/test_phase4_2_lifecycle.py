"""Unit and integration tests for Phase 4.2 Experiment Lifecycle States and Status Derivation."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

from phoenix_eval.experiment.lifecycle import derive_experiment_lifecycle_status
from phoenix_eval.experiment.runner import ExperimentRunner
from phoenix_eval.providers.base import MockModelProvider
from phoenix_eval.schemas.common import ExecutionStatus
from phoenix_eval.schemas.experiments import (
    ExperimentConfig,
    ExperimentLifecycleStatus,
    ExperimentRunRecord,
)


def _make_dummy_run_record(
    run_id: str,
    exec_status: ExecutionStatus = ExecutionStatus.COMPLETED,
    safety_gate_passed: bool = True,
    effective_score: float = 85.0,
    error_type: str | None = None,
    eval_file: str | None = "evals/dummy.json",
) -> ExperimentRunRecord:
    """Helper creating a test ExperimentRunRecord."""
    return ExperimentRunRecord(
        experiment_id="exp-test-001",
        run_id=run_id,
        task_id="task-dummy",
        scenario_id="scen-dummy",
        provider_name="mock",
        model_identifier="mock-model-v1",
        model_version="1.0.0",
        configured_model_identifier="mock-model-v1",
        configured_model_version="1.0.0",
        execution_status=exec_status,
        prompt_hash="dummy_prompt_hash",
        raw_response_file="raw/dummy.json",
        evaluation_report_file=eval_file,
        safety_gate_passed=safety_gate_passed,
        effective_score=effective_score,
        error_type=error_type,
    )


def test_lifecycle_status_created() -> None:
    """Verify status is CREATED when runs are scheduled but none have executed."""
    status = derive_experiment_lifecycle_status(total_scheduled_runs=10, runs=[])
    assert status == ExperimentLifecycleStatus.CREATED


def test_lifecycle_status_partially_completed() -> None:
    """Verify status is PARTIALLY_COMPLETED when runs executed < total scheduled."""
    runs = [_make_dummy_run_record(f"run-{i}") for i in range(5)]
    status = derive_experiment_lifecycle_status(total_scheduled_runs=10, runs=runs)
    assert status == ExperimentLifecycleStatus.PARTIALLY_COMPLETED


def test_lifecycle_status_completed_even_when_safety_gate_fails() -> None:
    """CRITICAL: A model failing the benchmark safety gate with effective_score=0 is a valid

    scientific evaluation result, NOT an infrastructure failure. The experiment status
    must be COMPLETED, not COMPLETED_WITH_FAILURES.
    """
    runs = [
        _make_dummy_run_record(
            run_id=f"run-{i}",
            safety_gate_passed=False,
            effective_score=0.0,
            exec_status=ExecutionStatus.COMPLETED,
        )
        for i in range(5)
    ]
    status = derive_experiment_lifecycle_status(total_scheduled_runs=5, runs=runs)
    assert status == ExperimentLifecycleStatus.COMPLETED


def test_lifecycle_status_completed_with_failures_on_provider_error() -> None:
    """Verify status is COMPLETED_WITH_FAILURES if any provider call failed or timed out."""
    runs = [
        _make_dummy_run_record("run-0", exec_status=ExecutionStatus.COMPLETED),
        _make_dummy_run_record(
            "run-1", exec_status=ExecutionStatus.FAILED, error_type="ProviderError"
        ),
        _make_dummy_run_record(
            "run-2", exec_status=ExecutionStatus.TIMED_OUT, error_type="TimeoutError"
        ),
    ]
    status = derive_experiment_lifecycle_status(total_scheduled_runs=3, runs=runs)
    assert status == ExperimentLifecycleStatus.COMPLETED_WITH_FAILURES


def test_lifecycle_status_completed_with_failures_on_eval_error() -> None:
    """Verify status is COMPLETED_WITH_FAILURES if an evaluation crashed or report was not persisted."""
    runs = [
        _make_dummy_run_record("run-0", exec_status=ExecutionStatus.COMPLETED),
        _make_dummy_run_record("run-1", exec_status=ExecutionStatus.COMPLETED, eval_file=None),
    ]
    status = derive_experiment_lifecycle_status(total_scheduled_runs=2, runs=runs)
    assert status == ExperimentLifecycleStatus.COMPLETED_WITH_FAILURES


def test_lifecycle_status_interrupted() -> None:
    """Verify status is INTERRUPTED when is_interrupted flag is set."""
    runs = [_make_dummy_run_record("run-0")]
    status = derive_experiment_lifecycle_status(
        total_scheduled_runs=5,
        runs=runs,
        is_interrupted=True,
    )
    assert status == ExperimentLifecycleStatus.INTERRUPTED


def test_lifecycle_status_failed() -> None:
    """Verify status is FAILED when initialization_failed flag is set."""
    status = derive_experiment_lifecycle_status(
        total_scheduled_runs=5,
        runs=[],
        initialization_failed=True,
    )
    assert status == ExperimentLifecycleStatus.FAILED


def test_runner_end_to_end_safety_failure_records_clean_completed(tmp_path: Path) -> None:
    """End-to-end runner test: evaluating an unsafe mock model that fails the safety gate

    must result in manifest.execution_status == COMPLETED.
    """
    exp_dir = tmp_path / "exp_unsafe_clean"
    config = ExperimentConfig(
        experiment_id="exp-unsafe-001",
        experiment_name="Unsafe Model Safety Evaluation",
        selected_models=["mock-unsafe-migration"],
        selected_tasks=["task-seq-pqc-001"],
        number_of_trials=1,
        output_dir=str(exp_dir),
        mode="mock",
    )

    runner = ExperimentRunner(config=config)
    manifest = runner.run()

    # The model failed safety gate (effective_score=0.0)
    assert len(manifest.runs) == 1
    run = manifest.runs[0]
    assert run.execution_status == ExecutionStatus.COMPLETED
    assert not run.safety_gate_passed
    assert run.effective_score == 0.0

    # But the experiment campaign completed cleanly!
    assert manifest.execution_status == ExperimentLifecycleStatus.COMPLETED
    assert manifest.completed_runs_count == 1
    assert manifest.failed_runs_count == 0


def test_runner_end_to_end_provider_failure_records_completed_with_failures(tmp_path: Path) -> None:
    """End-to-end runner test: when a provider call genuinely fails, the experiment campaign

    must be marked COMPLETED_WITH_FAILURES.
    """
    exp_dir = tmp_path / "exp_provider_failure"
    config = ExperimentConfig(
        experiment_id="exp-prov-fail-001",
        experiment_name="Provider Failure Lifecycle Test",
        selected_models=["mock-model-v1", "mock-refusal-v1"],
        selected_tasks=["task-seq-pqc-001"],
        number_of_trials=1,
        output_dir=str(exp_dir),
        mode="mock",
        retry_count=0,
    )

    runner = ExperimentRunner(config=config)

    orig_generate = MockModelProvider.generate_response
    call_count = 0

    def mock_generate_with_single_failure(self: MockModelProvider, req: Any) -> Any:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Simulated unrecoverable provider connection crash")
        return orig_generate(self, req)

    # Patch mock provider to simulate an unrecoverable failure on the first model
    with patch.object(MockModelProvider, "generate_response", mock_generate_with_single_failure):
        manifest = runner.run()

    assert manifest.execution_status == ExperimentLifecycleStatus.COMPLETED_WITH_FAILURES
    assert manifest.failed_runs_count == 1
    assert manifest.completed_runs_count == 1

"""Experiment lifecycle states and deterministic status derivation for PHOENIX-EVAL."""

from phoenix_eval.schemas.common import ExecutionStatus
from phoenix_eval.schemas.experiments import ExperimentLifecycleStatus, ExperimentRunRecord


def derive_experiment_lifecycle_status(
    total_scheduled_runs: int,
    runs: list[ExperimentRunRecord],
    is_interrupted: bool = False,
    initialization_failed: bool = False,
) -> ExperimentLifecycleStatus:
    """Deterministically derive the lifecycle status of an experiment.

    Scoring vs Infrastructure Separation:
    - Failing a benchmark safety gate (effective_score=0.0, safety_gate_passed=False) is
      a valid benchmark evaluation outcome, NOT an experiment execution failure.
    - An experiment is only labeled COMPLETED_WITH_FAILURES if a model provider call
      failed (e.g. timeout, network error, auth failure, rate limit exhaustion) or if the
      evaluation engine itself suffered an unexpected error.
    - An experiment where some runs were not completed is PARTIALLY_COMPLETED.
    - If execution was aborted by SIGINT / KeyboardInterrupt, status is INTERRUPTED.
    - If initialization or pre-flight failed, status is FAILED.
    """
    if initialization_failed:
        return ExperimentLifecycleStatus.FAILED

    if is_interrupted:
        return ExperimentLifecycleStatus.INTERRUPTED

    if total_scheduled_runs > 0 and not runs:
        return ExperimentLifecycleStatus.CREATED

    completed_runs_count = len(runs)
    if completed_runs_count < total_scheduled_runs:
        return ExperimentLifecycleStatus.PARTIALLY_COMPLETED

    # All scheduled runs executed - inspect for provider or evaluator failures
    has_infrastructure_or_provider_failures = False
    for r in runs:
        # Check provider execution status
        if r.execution_status != ExecutionStatus.COMPLETED:
            has_infrastructure_or_provider_failures = True
            break
        # Check for unhandled provider or evaluation error
        if r.error_type is not None:
            has_infrastructure_or_provider_failures = True
            break
        # Ensure evaluation report was actually persisted
        if r.evaluation_report_file is None and r.raw_response_file is not None:
            has_infrastructure_or_provider_failures = True
            break

    if has_infrastructure_or_provider_failures:
        return ExperimentLifecycleStatus.COMPLETED_WITH_FAILURES

    return ExperimentLifecycleStatus.COMPLETED

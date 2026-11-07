"""Integration tests for Phase 4 ExperimentRunner, resumption, prompt equality, and artifact persistence."""

from pathlib import Path
from unittest.mock import patch

import pytest

from phoenix_eval.core.exceptions import GroundTruthLeakageError, ProviderExecutionError
from phoenix_eval.experiment.runner import ExperimentRunner
from phoenix_eval.providers.base import MockModelProvider, ProviderPromptRequest
from phoenix_eval.providers.model_registry import ModelConfig, ModelRegistry
from phoenix_eval.schemas.common import ExecutionStatus
from phoenix_eval.schemas.experiments import ExperimentConfig


def test_end_to_end_mock_experiment_execution(tmp_path: Path) -> None:
    """Execute a complete end-to-end multi-model multi-task benchmark experiment in mock mode."""
    exp_dir = tmp_path / "exp_end_to_end"
    config = ExperimentConfig(
        experiment_id="exp-e2e-001",
        experiment_name="End to End Mock Campaign",
        selected_models=["mock-model-v1", "mock-refusal-v1"],
        selected_tasks=["task-gen-t01-bank-01"],
        number_of_trials=2,
        output_dir=str(exp_dir),
        mode="mock",
    )

    runner = ExperimentRunner(config=config)
    manifest = runner.run()

    # 1. Verify manifest and counts
    assert manifest.experiment_id == "exp-e2e-001"
    assert manifest.total_scheduled_runs == 4  # 2 models x 1 task x 2 trials
    assert manifest.completed_runs_count == 4
    assert manifest.failed_runs_count == 0
    assert manifest.execution_status == ExecutionStatus.COMPLETED

    # 2. Verify files on disk
    manifest_file = exp_dir / "experiment_manifest.json"
    runs_file = exp_dir / "runs.jsonl"
    summary_file = exp_dir / "model_summary.json"
    comparison_file = exp_dir / "model_comparison.csv"
    report_file = exp_dir / "experiment_summary.md"

    assert manifest_file.exists()
    assert runs_file.exists()
    assert summary_file.exists()
    assert comparison_file.exists()
    assert report_file.exists()

    # 3. Verify individual raw responses and evaluation reports
    raw_responses = list((exp_dir / "raw_responses").glob("*.json"))
    eval_reports = list((exp_dir / "evaluations").glob("*.json"))

    assert len(raw_responses) == 4
    assert len(eval_reports) == 4

    # 4. Verify runs.jsonl lines
    lines = [ln.strip() for ln in runs_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 4


def test_prompt_equality_across_models(tmp_path: Path) -> None:
    """Verify that different models receive identical prompt text and identical prompt hashes for the same task."""
    exp_dir = tmp_path / "exp_prompt_equality"
    config = ExperimentConfig(
        experiment_id="exp-equality-001",
        experiment_name="Prompt Equality Test",
        selected_models=["mock-model-v1", "mock-refusal-v1"],
        selected_tasks=["task-gen-t01-bank-01"],
        number_of_trials=1,
        output_dir=str(exp_dir),
    )

    runner = ExperimentRunner(config=config)
    manifest = runner.run()

    runs = manifest.runs
    assert len(runs) == 2
    # Both models evaluated on the same task must share exact prompt hash
    assert runs[0].prompt_hash == runs[1].prompt_hash


def test_resumption_skips_already_completed_runs(tmp_path: Path) -> None:
    """Verify that resuming an experiment skips completed runs without duplicating them."""
    exp_dir = tmp_path / "exp_resume_test"
    config = ExperimentConfig(
        experiment_id="exp-resume-001",
        experiment_name="Resumption Test",
        selected_models=["mock-model-v1"],
        selected_tasks=["task-gen-t01-bank-01"],
        number_of_trials=2,
        output_dir=str(exp_dir),
        resume=True,
    )

    # First execution: completes 2 runs
    runner1 = ExperimentRunner(config=config)
    manifest1 = runner1.run()
    assert manifest1.completed_runs_count == 2

    # Second execution with resume=True: should skip both runs
    runner2 = ExperimentRunner(config=config)
    manifest2 = runner2.run()
    assert manifest2.completed_runs_count == 2
    assert manifest2.skipped_resumed_runs_count == 2

    # Verify runs.jsonl did not grow to 4
    lines = [
        ln.strip()
        for ln in (exp_dir / "runs.jsonl").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    assert len(lines) == 2


def test_ground_truth_leakage_detection(tmp_path: Path) -> None:
    """Verify that ground truth references in prompts trigger security violation."""
    runner = ExperimentRunner(
        config=ExperimentConfig(
            experiment_id="exp-leak-001",
            experiment_name="Leakage Test",
            selected_models=["mock-model-v1"],
            selected_tasks=["task-gen-t01-bank-01"],
            output_dir=str(tmp_path / "leak"),
        )
    )

    task = runner._load_task("task-gen-t01-bank-01")
    leaked_prompt = f"Prompt text containing hidden reference {task.ground_truth_reference} here."

    with pytest.raises(GroundTruthLeakageError, match="Security Violation"):
        runner._verify_ground_truth_isolation(leaked_prompt, task)


def test_provider_failure_does_not_halt_other_models(tmp_path: Path) -> None:
    """Verify that if one provider fails, other models still execute and failure is recorded."""
    registry = ModelRegistry()
    # Register a failing mock model
    registry.register_model(
        ModelConfig(
            model_id="mock-failing-model",
            provider_type="mock",
            model_name="mock-failing",
            is_mock=True,
            metadata={"behavior": "default"},
        )
    )

    exp_dir = tmp_path / "exp_failure_isolation"
    config = ExperimentConfig(
        experiment_id="exp-failure-001",
        experiment_name="Failure Isolation Campaign",
        selected_models=["mock-model-v1", "mock-failing-model"],
        selected_tasks=["task-gen-t01-bank-01"],
        number_of_trials=1,
        output_dir=str(exp_dir),
    )

    runner = ExperimentRunner(config=config, model_registry=registry)

    # Patch the failing provider to raise ProviderExecutionError
    with patch.object(
        MockModelProvider,
        "generate_response",
        side_effect=[
            MockModelProvider(model_identifier="mock-model-v1").generate_response(
                ProviderPromptRequest(task_id="task-gen-t01-bank-01", prompt="Prompt")
            ),
            ProviderExecutionError("Simulated upstream provider outage"),
        ],
    ):
        manifest = runner.run()

    assert manifest.completed_runs_count == 1
    assert manifest.failed_runs_count == 1
    assert len(manifest.runs) == 2

    failed_run = next(r for r in manifest.runs if r.model_identifier == "mock-failing-model")
    assert failed_run.execution_status == ExecutionStatus.FAILED
    assert "Simulated upstream provider outage" in (failed_run.error_message or "")

    successful_run = next(r for r in manifest.runs if r.model_identifier == "mock-model-v1")
    assert successful_run.execution_status == ExecutionStatus.COMPLETED

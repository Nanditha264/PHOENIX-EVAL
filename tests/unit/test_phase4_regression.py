"""Regression test suite for PHOENIX-EVAL Phase 4.1 fixes."""

import concurrent.futures
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from phoenix_eval.core.constants import BENCHMARK_SYSTEM_PROMPT
from phoenix_eval.core.exceptions import (
    ConfigurationError,
    ExperimentError,
    ProviderInvalidRequestError,
    ProviderTimeoutError,
)
from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.repository import GroundTruthRepository, ScenarioRepository, TaskRepository
from phoenix_eval.evaluation.evaluator import DeterministicEvaluator
from phoenix_eval.evaluation.response_parser import parse_model_response
from phoenix_eval.experiment.config_loader import ExperimentValidator
from phoenix_eval.experiment.runner import ExperimentRunner, FileLock
from phoenix_eval.providers.base import MockModelProvider, ProviderPromptRequest
from phoenix_eval.providers.fixtures import (
    load_mock_fixture,
)
from phoenix_eval.providers.model_registry import ModelRegistry
from phoenix_eval.schemas.common import ExecutionStatus
from phoenix_eval.schemas.experiments import ExperimentConfig
from phoenix_eval.schemas.model_outputs import ModelResponse
from phoenix_eval.utils.hashing import compute_full_input_hash


def test_valid_mock_response_passes_evaluation() -> None:
    """Verify that the rewritten valid mock response passes schema checks and achieves non-zero score."""
    paths = get_paths()
    t_repo = TaskRepository(paths.tasks_dir)
    scen_repo = ScenarioRepository(paths.scenarios_dir)
    gt_repo = GroundTruthRepository(paths.ground_truth_dir)

    task = t_repo.load_task("task-seq-pqc-001")
    scen = scen_repo.load_scenario(task.scenario_reference)
    gt = gt_repo.load_ground_truth(task.ground_truth_reference)

    provider = MockModelProvider(behavior="valid_contract")
    request = ProviderPromptRequest(
        task_id=task.task_id,
        prompt="Synthesize migration sequence",
        system_prompt=BENCHMARK_SYSTEM_PROMPT,
        metadata={"task": task, "scenario": scen},
    )

    response = provider.generate_response(request)
    assert response.execution_status == ExecutionStatus.COMPLETED

    evaluator = DeterministicEvaluator()
    report = evaluator.evaluate_detailed(
        task=task,
        raw_response_text=response.raw_response,
        ground_truth=gt,
        scenario=scen,
    )

    assert report.is_valid_json is True
    assert report.is_valid_contract is True
    assert report.safety_gate_passed is True
    assert report.effective_score is not None and report.effective_score > 0.0
    assert len(report.critical_violations) == 0


def test_mock_response_fixtures() -> None:
    """Verify each of the three fixtures (valid, malformed, unsafe) produces expected outcomes."""
    paths = get_paths()
    t_repo = TaskRepository(paths.tasks_dir)
    scen_repo = ScenarioRepository(paths.scenarios_dir)
    gt_repo = GroundTruthRepository(paths.ground_truth_dir)

    task = t_repo.load_task("task-seq-pqc-001")
    scen = scen_repo.load_scenario(task.scenario_reference)
    gt = gt_repo.load_ground_truth(task.ground_truth_reference)
    evaluator = DeterministicEvaluator()

    # 1. Valid Contract Fixture
    valid_text = load_mock_fixture("valid")
    parsed_valid = parse_model_response(valid_text)
    assert parsed_valid.is_valid_contract is True
    assert parsed_valid.is_malformed is False

    # 2. Malformed Response Fixture
    malformed_text = load_mock_fixture("malformed")
    parsed_malformed = parse_model_response(malformed_text)
    assert parsed_malformed.is_valid_contract is False
    assert parsed_malformed.is_malformed is True
    report_malformed = evaluator.evaluate_detailed(task, malformed_text, gt, scen)
    assert report_malformed.safety_gate_passed is False
    assert any(
        v["rule_name"] == "VIO_MALFORMED_RESPONSE" for v in report_malformed.critical_violations
    )

    # 3. Unsafe Response Fixture
    unsafe_text = load_mock_fixture("unsafe")
    parsed_unsafe = parse_model_response(unsafe_text)
    assert parsed_unsafe.is_valid_contract is True
    assert parsed_unsafe.is_malformed is False
    report_unsafe = evaluator.evaluate_detailed(task, unsafe_text, gt, scen)
    assert report_unsafe.safety_gate_passed is False
    assert len(report_unsafe.critical_violations) > 0


def test_resumption_replaces_failed_record(tmp_path: Path) -> None:
    """Verify that retrying a failed run replaces the failed record in manifest and summary while preserving JSONL."""
    output_dir = tmp_path / "exp_resumption"
    config = ExperimentConfig(
        experiment_id="exp-resume-001",
        experiment_name="Resume Replacement Test",
        selected_models=["mock-model-v1"],
        selected_tasks=["task-seq-pqc-001"],
        number_of_trials=1,
        output_dir=str(output_dir),
        resume=True,
    )

    # First run: simulate failure via custom provider in registry
    fail_provider = MockModelProvider(
        model_identifier="mock-model-v1",
        simulate_error=True,
    )
    registry1 = ModelRegistry()
    registry1.create_provider = MagicMock(return_value=fail_provider)  # type: ignore[method-assign]

    runner1 = ExperimentRunner(config=config, model_registry=registry1)
    manifest1 = runner1.run()

    assert manifest1.completed_runs_count == 0
    assert manifest1.failed_runs_count == 1
    assert len(manifest1.runs) == 1
    assert manifest1.runs[0].execution_status == ExecutionStatus.FAILED
    assert manifest1.runs[0].attempt_number == 1

    # Second run: provider succeeds on resume
    succ_provider = MockModelProvider(
        model_identifier="mock-model-v1",
        behavior="valid_contract",
    )
    registry2 = ModelRegistry()
    registry2.create_provider = MagicMock(return_value=succ_provider)  # type: ignore[method-assign]

    runner2 = ExperimentRunner(config=config, model_registry=registry2)
    manifest2 = runner2.run()

    # In authoritative manifest, the run is replaced by the completed attempt
    assert manifest2.completed_runs_count == 1
    assert manifest2.failed_runs_count == 0
    assert len(manifest2.runs) == 1
    assert manifest2.runs[0].execution_status == ExecutionStatus.COMPLETED
    assert manifest2.runs[0].attempt_number == 2

    # Verify JSONL log contains both attempts (full audit trail)
    runs_jsonl = output_dir / "runs.jsonl"
    lines = [
        line.strip() for line in runs_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(lines) == 2


def test_resumed_run_skips_completed(tmp_path: Path) -> None:
    """Verify that already completed runs are never re-executed on resume."""
    output_dir = tmp_path / "exp_skip_completed"
    config = ExperimentConfig(
        experiment_id="exp-skip-001",
        experiment_name="Skip Completed Test",
        selected_models=["mock-model-v1"],
        selected_tasks=["task-seq-pqc-001"],
        number_of_trials=1,
        output_dir=str(output_dir),
        resume=True,
    )

    runner = ExperimentRunner(config=config)
    manifest1 = runner.run()
    assert manifest1.completed_runs_count == 1

    # Second run on same directory: should skip
    reg_skip = ModelRegistry()
    runner2 = ExperimentRunner(config=config, model_registry=reg_skip)
    # Spy on provider execution
    spy_provider = MockModelProvider(behavior="valid_contract")
    spy_provider.generate_response = MagicMock(wraps=spy_provider.generate_response)  # type: ignore[method-assign]
    runner2.model_registry.create_provider = MagicMock(return_value=spy_provider)  # type: ignore[method-assign]

    manifest2 = runner2.run()
    assert manifest2.skipped_resumed_runs_count == 1
    assert manifest2.completed_runs_count == 1
    # Provider should never have been invoked because it was skipped
    assert spy_provider.generate_response.call_count == 0


def test_retry_count_configuration(tmp_path: Path) -> None:
    """Verify that retry_count=0 does not retry, retry_count=2 retries twice, and retries are recorded."""
    output_dir = tmp_path / "exp_retries"

    # 1. Test retry_count = 0
    config0 = ExperimentConfig(
        experiment_id="exp-retry-0",
        experiment_name="Retry 0 Test",
        selected_models=["mock-model-v1"],
        selected_tasks=["task-seq-pqc-001"],
        retry_count=0,
        output_dir=str(output_dir / "retry0"),
        resume=False,
    )
    provider0 = MockModelProvider(simulate_timeout=True)
    registry0 = ModelRegistry()
    registry0.create_provider = MagicMock(return_value=provider0)  # type: ignore[method-assign]

    runner0 = ExperimentRunner(config=config0, model_registry=registry0)
    manifest0 = runner0.run()
    assert manifest0.runs[0].retry_count == 0
    assert manifest0.runs[0].execution_status == ExecutionStatus.TIMED_OUT

    # 2. Test retry_count = 2 on transient timeout
    config2 = ExperimentConfig(
        experiment_id="exp-retry-2",
        experiment_name="Retry 2 Test",
        selected_models=["mock-model-v1"],
        selected_tasks=["task-seq-pqc-001"],
        retry_count=2,
        output_dir=str(output_dir / "retry2"),
        resume=False,
    )
    call_count = 0

    class FailingThenRecoveringProvider(MockModelProvider):
        def generate_response(self, request: ProviderPromptRequest) -> ModelResponse:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ProviderTimeoutError(f"Simulated timeout on call {call_count}")
            return super().generate_response(request)

    provider2 = FailingThenRecoveringProvider(behavior="valid_contract")
    registry2 = ModelRegistry()
    registry2.create_provider = MagicMock(return_value=provider2)  # type: ignore[method-assign]

    runner2 = ExperimentRunner(config=config2, model_registry=registry2)
    manifest2 = runner2.run()

    # Succeeded on call 3 after 2 retries
    assert call_count == 3
    assert manifest2.runs[0].retry_count == 2
    assert manifest2.runs[0].execution_status == ExecutionStatus.COMPLETED

    # 3. Test non-transient error does not retry
    config_nontrans = ExperimentConfig(
        experiment_id="exp-nontrans",
        experiment_name="Non-transient Test",
        selected_models=["mock-model-v1"],
        selected_tasks=["task-seq-pqc-001"],
        retry_count=3,
        output_dir=str(output_dir / "nontrans"),
        resume=False,
    )
    nontrans_count = 0

    class NonTransientProvider(MockModelProvider):
        def generate_response(self, request: ProviderPromptRequest) -> ModelResponse:
            nonlocal nontrans_count
            nontrans_count += 1
            raise ProviderInvalidRequestError("Non-retryable invalid schema payload")

    provider_nt = NonTransientProvider()
    registry_nt = ModelRegistry()
    registry_nt.create_provider = MagicMock(return_value=provider_nt)  # type: ignore[method-assign]

    runner_nt = ExperimentRunner(config=config_nontrans, model_registry=registry_nt)
    manifest_nt = runner_nt.run()
    # Must fail immediately on attempt 1 without retrying
    assert nontrans_count == 1
    assert manifest_nt.runs[0].retry_count == 0
    assert manifest_nt.runs[0].execution_status == ExecutionStatus.FAILED


def test_full_input_hash_equality() -> None:
    """Verify that identical prompts produce identical hashes, and differences cause divergence."""
    h1 = compute_full_input_hash("Prompt text", BENCHMARK_SYSTEM_PROMPT, 0.0, 2048)
    h2 = compute_full_input_hash("Prompt text", BENCHMARK_SYSTEM_PROMPT, 0.0, 2048)
    assert h1 == h2

    # Different system prompt
    h_sys = compute_full_input_hash("Prompt text", "Alternative sys instruction", 0.0, 2048)
    assert h1 != h_sys

    # Different temperature
    h_temp = compute_full_input_hash("Prompt text", BENCHMARK_SYSTEM_PROMPT, 0.5, 2048)
    assert h1 != h_temp


def test_mixed_mode_prohibited_by_default() -> None:
    """Verify that configuring both mock and real models fails validation without allow_mixed_mode."""
    validator = ExperimentValidator()
    config = ExperimentConfig(
        experiment_id="exp-mixed-test",
        experiment_name="Mixed Rejection Test",
        selected_models=["mock-model-v1", "gpt-4o"],
        selected_tasks=["task-seq-pqc-001"],
        allow_mixed_mode=False,
    )
    with pytest.raises(ConfigurationError, match="prohibited by default"):
        validator.validate_pre_flight(config)


def test_atomic_lock_concurrency(tmp_path: Path) -> None:
    """Verify that concurrent runner processes cannot acquire the same lock simultaneously."""
    lock_file = tmp_path / ".experiment.lock"
    success_count = 0
    fail_count = 0
    acquired_locks: list[FileLock] = []

    def attempt_lock() -> bool:
        lock = FileLock(lock_file)
        try:
            lock.acquire()
            acquired_locks.append(lock)
            return True
        except ExperimentError:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: attempt_lock(), range(8)))

    success_count = sum(1 for r in results if r)
    fail_count = sum(1 for r in results if not r)

    assert success_count == 1
    assert fail_count == 7

    for lk in acquired_locks:
        lk.release()
    assert not lock_file.exists()

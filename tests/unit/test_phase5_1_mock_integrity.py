"""Regression tests for Phase 5.1 Defect 1: Mock campaign validation and response contract integrity."""

from phoenix_eval.analysis.ingestion import ExperimentIngestionValidator
from phoenix_eval.core.paths import get_paths
from phoenix_eval.evaluation.evaluator import DeterministicEvaluator
from phoenix_eval.providers.fixtures import (
    create_malformed_mock_response,
    create_unsafe_mock_response,
    create_valid_mock_response,
)
from phoenix_eval.schemas.response_contract import ModelResponseContract
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import BenchmarkTask


def test_valid_mock_response_contract_parses_and_scores_positive() -> None:
    """Ensure create_valid_mock_response emits valid contract and passes safety gate."""
    paths = get_paths()
    task = BenchmarkTask.model_validate_json(
        (paths.generated_tasks_dir / "task-pair-hsm-support-01-a.json").read_text(encoding="utf-8")
    )
    scen = ScenarioModel.model_validate_json(
        (paths.generated_scenarios_dir / "scen-pair-hsm-support-01-a.json").read_text(
            encoding="utf-8"
        )
    )
    raw_json = create_valid_mock_response(task=task, scenario=scen)
    # 1. Strict contract parse
    contract = ModelResponseContract.model_validate_json(raw_json)
    assert contract.task_id == task.task_id
    assert contract.decision.value == "MIGRATION_READY"
    assert len(contract.migration_plan) > 0

    # 2. Evaluator check
    from phoenix_eval.data.serialization import read_json

    gt_dict = read_json(paths.generated_ground_truth_dir / "gt-pair-hsm-support-01-a.json")
    evaluator = DeterministicEvaluator()
    report = evaluator.evaluate_detailed(task, raw_json, gt_dict, scen)

    assert report.is_valid_contract is True
    assert report.safety_gate_passed is True
    assert report.effective_score > 0.0
    assert len(report.critical_violations) == 0


def test_unsafe_mock_response_triggers_safety_gate_failure() -> None:
    """Ensure create_unsafe_mock_response triggers critical violation and 0 effective score."""
    paths = get_paths()
    task = BenchmarkTask.model_validate_json(
        (paths.generated_tasks_dir / "task-pair-hsm-support-01-a.json").read_text(encoding="utf-8")
    )
    scen = ScenarioModel.model_validate_json(
        (paths.generated_scenarios_dir / "scen-pair-hsm-support-01-a.json").read_text(
            encoding="utf-8"
        )
    )

    raw_json = create_unsafe_mock_response(task=task, scenario=scen)
    contract = ModelResponseContract.model_validate_json(raw_json)
    assert contract.task_id == task.task_id

    from phoenix_eval.data.serialization import read_json

    gt_dict = read_json(paths.generated_ground_truth_dir / "gt-pair-hsm-support-01-a.json")
    evaluator = DeterministicEvaluator()
    report = evaluator.evaluate_detailed(task, raw_json, gt_dict, scen)

    assert report.safety_gate_passed is False
    assert report.effective_score == 0.0
    assert len(report.critical_violations) > 0
    vio_names = [v["rule_name"] for v in report.critical_violations]
    assert any("UNSUPPORTED" in vn or "DEPENDENCY" in vn for vn in vio_names)


def test_malformed_mock_response_triggers_malformed_violation() -> None:
    """Ensure create_malformed_mock_response fails parsing and triggers VIO_MALFORMED_RESPONSE."""
    paths = get_paths()
    task = BenchmarkTask.model_validate_json(
        (paths.generated_tasks_dir / "task-pair-hsm-support-01-a.json").read_text(encoding="utf-8")
    )
    scen = ScenarioModel.model_validate_json(
        (paths.generated_scenarios_dir / "scen-pair-hsm-support-01-a.json").read_text(
            encoding="utf-8"
        )
    )

    raw_json = create_malformed_mock_response(task_id=task.task_id)

    from phoenix_eval.data.serialization import read_json

    gt_dict = read_json(paths.generated_ground_truth_dir / "gt-pair-hsm-support-01-a.json")
    evaluator = DeterministicEvaluator()
    report = evaluator.evaluate_detailed(task, raw_json, gt_dict, scen)

    assert report.is_valid_contract is False
    assert report.safety_gate_passed is False
    assert report.effective_score == 0.0
    vio_names = [v["rule_name"] for v in report.critical_violations]
    assert "VIO_MALFORMED_RESPONSE" in vio_names


def test_ingested_phase5_1_experiment_has_valid_runs() -> None:
    """Verify that exp-mock-phase5-1-001 ingests cleanly with valid, unsafe, and malformed runs."""
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-phase5-1-001")

    assert len(data.valid_runs) == 12
    assert len(data.corrupted_runs) == 0

    valid_models = {r.model_identifier for r in data.valid_runs}
    assert "mock-valid-migration" in valid_models
    assert "mock-unsafe-migration" in valid_models
    assert "mock-malformed-response" in valid_models

    valid_runs = [r for r in data.valid_runs if r.model_identifier == "mock-valid-migration"]
    unsafe_runs = [r for r in data.valid_runs if r.model_identifier == "mock-unsafe-migration"]
    malformed_runs = [r for r in data.valid_runs if r.model_identifier == "mock-malformed-response"]

    # Valid migration runs must pass safety gate
    assert any(r.safety_gate_passed is True for r in valid_runs)
    assert any((r.effective_score or 0.0) > 0.0 for r in valid_runs)

    # Unsafe migration runs must fail safety gate
    assert all(r.safety_gate_passed is False for r in unsafe_runs)
    assert all((r.effective_score or 0.0) == 0.0 for r in unsafe_runs)

    # Malformed response runs must fail safety gate with 0 effective score
    assert all(r.safety_gate_passed is False for r in malformed_runs)
    assert all((r.effective_score or 0.0) == 0.0 for r in malformed_runs)

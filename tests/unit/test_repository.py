"""Unit tests for repository data access layers and security boundaries."""

import pytest

from phoenix_eval.core.exceptions import (
    GroundTruthError,
    ScenarioError,
    TaskNotFoundError,
)
from phoenix_eval.core.paths import ProjectPaths
from phoenix_eval.data.repository import (
    GroundTruthRepository,
    ResultsRepository,
    ScenarioRepository,
    TaskRepository,
)
from phoenix_eval.schemas.evaluation import EvaluationResult
from phoenix_eval.schemas.model_outputs import ModelResponse
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import BenchmarkTask


def test_scenario_repository(
    sample_scenario: ScenarioModel, mock_project_paths: ProjectPaths
) -> None:
    """Verify ScenarioRepository save, load, and lookup operations."""
    repo = ScenarioRepository(mock_project_paths.scenarios_dir)
    repo.save_scenario(sample_scenario)

    loaded = repo.load_scenario(sample_scenario.scenario_id)
    assert loaded.scenario_id == sample_scenario.scenario_id
    assert sample_scenario.scenario_id in repo.list_scenario_ids()

    with pytest.raises(ScenarioError, match="not found"):
        repo.load_scenario("scen-non-existent-999")


def test_task_repository(sample_task: BenchmarkTask, mock_project_paths: ProjectPaths) -> None:
    """Verify TaskRepository save, load, and lookup operations."""
    repo = TaskRepository(mock_project_paths.tasks_dir)
    repo.save_task(sample_task)

    loaded = repo.load_task(sample_task.task_id)
    assert loaded.task_id == sample_task.task_id
    assert sample_task.task_id in repo.list_task_ids()

    with pytest.raises(TaskNotFoundError, match="not found"):
        repo.load_task("task-non-existent-999")


def test_ground_truth_repository(mock_project_paths: ProjectPaths) -> None:
    """Verify GroundTruthRepository persistence and retrieval for evaluator execution."""
    repo = GroundTruthRepository(mock_project_paths.ground_truth_dir)
    gt_data = {"ground_truth_id": "gt-test-001", "blockers": ["comp-hsm"]}
    repo.save_ground_truth("gt-test-001", gt_data)

    assert repo.has_ground_truth("gt-test-001") is True
    assert repo.has_ground_truth("gt-missing") is False

    loaded = repo.load_ground_truth("gt-test-001")
    assert loaded["ground_truth_id"] == "gt-test-001"
    assert "gt-test-001" in repo.list_ground_truth_ids()

    with pytest.raises(GroundTruthError, match="not found"):
        repo.load_ground_truth("gt-non-existent-999")


def test_results_repository(mock_project_paths: ProjectPaths) -> None:
    """Verify ResultsRepository persistence for model responses and evaluation results."""
    repo = ResultsRepository(mock_project_paths)

    response = ModelResponse(
        response_id="resp-test-repo-01",
        task_id="task-01",
        model_provider="mock",
        model_identifier="mock-v1",
        model_version="1.0",
        raw_response="test response",
        prompt_hash="hash123",
    )
    repo.save_model_response(response)
    restored_resp = repo.load_model_response(response.response_id)
    assert restored_resp.response_id == response.response_id

    result = EvaluationResult(
        evaluation_id="eval-test-repo-01",
        task_id="task-01",
        response_id=response.response_id,
        raw_score=95.0,
        final_status="PASSED",
    )
    repo.save_evaluation_result(result)
    restored_res = repo.load_evaluation_result(result.evaluation_id)
    assert restored_res.evaluation_id == result.evaluation_id
    assert restored_res.raw_score == 95.0

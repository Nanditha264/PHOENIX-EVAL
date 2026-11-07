"""Data repositories managing scenario, task, ground truth, and result storage.

Architectural Rule: Model-visible scenario loading is strictly separated from
evaluator-only ground-truth loading to prevent ground-truth data contamination.
"""

from pathlib import Path
from typing import Any, Optional

from pydantic import ValidationError

from phoenix_eval.core.exceptions import (
    DatasetError,
    GroundTruthError,
    ScenarioError,
    SchemaValidationError,
    TaskNotFoundError,
)
from phoenix_eval.core.logging import get_logger
from phoenix_eval.core.paths import ProjectPaths, get_paths
from phoenix_eval.data.serialization import read_json, write_json
from phoenix_eval.schemas.evaluation import EvaluationResult
from phoenix_eval.schemas.experiments import ExperimentRecord
from phoenix_eval.schemas.model_outputs import ModelResponse
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import BenchmarkTask

logger = get_logger("data.repository")


class ScenarioRepository:
    """Repository for managing model-visible enterprise scenario definitions.

    CRITICAL SECURITY INVARIANT:
    This repository NEVER loads, reads, or exposes evaluator ground truth.
    """

    def __init__(self, scenarios_dir: Optional[Path] = None) -> None:
        self.scenarios_dir = (scenarios_dir or get_paths().scenarios_dir).resolve()
        self.scenarios_dir.mkdir(parents=True, exist_ok=True)

    def load_scenario(self, scenario_id: str) -> ScenarioModel:
        """Load and validate a scenario by scenario_id from JSON file."""
        file_path = self.scenarios_dir / f"{scenario_id}.json"
        if not file_path.exists():
            # Check if any json file inside has matching scenario_id
            for p in self.scenarios_dir.glob("*.json"):
                try:
                    data = read_json(p)
                    if isinstance(data, dict) and data.get("scenario_id") == scenario_id:
                        return ScenarioModel.model_validate(data)
                except Exception:
                    continue
            raise ScenarioError(f"Scenario '{scenario_id}' not found in {self.scenarios_dir}")

        try:
            raw_data = read_json(file_path)
            return ScenarioModel.model_validate(raw_data)
        except ValidationError as err:
            raise SchemaValidationError(
                f"Schema validation failed for scenario '{scenario_id}': {err}"
            ) from err
        except Exception as err:
            raise ScenarioError(f"Failed to load scenario '{scenario_id}': {err}") from err

    def save_scenario(self, scenario: ScenarioModel) -> Path:
        """Persist a validated scenario to disk."""
        target_path = self.scenarios_dir / f"{scenario.scenario_id}.json"
        write_json(target_path, scenario)
        logger.info("Saved scenario '%s' to %s", scenario.scenario_id, target_path)
        return target_path

    def list_scenario_ids(self) -> list[str]:
        """List all available scenario IDs discovered in the scenarios directory."""
        ids: list[str] = []
        for p in sorted(self.scenarios_dir.glob("*.json")):
            try:
                data = read_json(p)
                if isinstance(data, dict) and "scenario_id" in data:
                    ids.append(data["scenario_id"])
            except Exception as err:
                logger.warning("Could not parse scenario file %s: %s", p, err)
        return sorted(ids)


class TaskRepository:
    """Repository for managing benchmark evaluation tasks."""

    def __init__(self, tasks_dir: Optional[Path] = None) -> None:
        self.tasks_dir = (tasks_dir or get_paths().tasks_dir).resolve()
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def load_task(self, task_id: str) -> BenchmarkTask:
        """Load and validate a benchmark task by ID."""
        file_path = self.tasks_dir / f"{task_id}.json"
        if not file_path.exists():
            for p in self.tasks_dir.glob("*.json"):
                try:
                    data = read_json(p)
                    if isinstance(data, dict) and data.get("task_id") == task_id:
                        return BenchmarkTask.model_validate(data)
                except Exception:
                    continue
            raise TaskNotFoundError(f"Benchmark task '{task_id}' not found in {self.tasks_dir}")

        try:
            raw_data = read_json(file_path)
            return BenchmarkTask.model_validate(raw_data)
        except ValidationError as err:
            raise SchemaValidationError(
                f"Schema validation failed for task '{task_id}': {err}"
            ) from err
        except Exception as err:
            raise TaskNotFoundError(f"Failed to load task '{task_id}': {err}") from err

    def save_task(self, task: BenchmarkTask) -> Path:
        """Persist a benchmark task to disk."""
        target_path = self.tasks_dir / f"{task.task_id}.json"
        write_json(target_path, task)
        logger.info("Saved task '%s' to %s", task.task_id, target_path)
        return target_path

    def list_task_ids(self) -> list[str]:
        """List all task IDs present in the tasks directory."""
        ids: list[str] = []
        for p in sorted(self.tasks_dir.glob("*.json")):
            try:
                data = read_json(p)
                if isinstance(data, dict) and "task_id" in data:
                    ids.append(data["task_id"])
            except Exception as err:
                logger.warning("Could not parse task file %s: %s", p, err)
        return sorted(ids)


class GroundTruthRepository:
    """Evaluator-only repository for loading hidden ground-truth criteria.

    ARCHITECTURAL BOUNDARY:
    This repository is intended solely for evaluator execution.
    Model execution pipelines, prompt builders, and benchmark registries do not
    instantiate or reference this repository.
    """

    def __init__(
        self,
        ground_truth_dir: Optional[Path] = None,
        extra_dirs: Optional[list[Path]] = None,
    ) -> None:
        paths = get_paths()
        self.ground_truth_dir = (ground_truth_dir or paths.ground_truth_dir).resolve()
        self.ground_truth_dir.mkdir(parents=True, exist_ok=True)
        self.search_dirs = [self.ground_truth_dir]
        if extra_dirs:
            self.search_dirs.extend([d.resolve() for d in extra_dirs if d.is_dir()])
        elif paths.generated_ground_truth_dir and paths.generated_ground_truth_dir.is_dir():
            self.search_dirs.append(paths.generated_ground_truth_dir.resolve())

    def load_ground_truth(self, ground_truth_id: str) -> dict[str, Any]:
        """Load ground-truth artifact by ID for evaluator execution.

        Args:
            ground_truth_id: ID of ground truth artifact.

        Raises:
            GroundTruthError: If ground truth artifact is missing or invalid.
        """
        for search_dir in self.search_dirs:
            file_path = search_dir / f"{ground_truth_id}.json"
            if file_path.exists():
                try:
                    data = read_json(file_path)
                    if not isinstance(data, dict):
                        raise GroundTruthError(
                            f"Ground truth file '{file_path}' does not contain a JSON object."
                        )
                    return data
                except Exception as err:
                    raise GroundTruthError(
                        f"Error loading ground truth '{ground_truth_id}': {err}"
                    ) from err

            for p in search_dir.glob("*.json"):
                try:
                    data = read_json(p)
                    if isinstance(data, dict) and data.get("ground_truth_id") == ground_truth_id:
                        return data
                except Exception:
                    continue

        raise GroundTruthError(
            f"Ground truth artifact '{ground_truth_id}' not found in {[str(d) for d in self.search_dirs]}"
        )

    def has_ground_truth(self, ground_truth_id: str) -> bool:
        """Check whether a ground truth artifact exists."""
        try:
            self.load_ground_truth(ground_truth_id)
            return True
        except GroundTruthError:
            return False

    def save_ground_truth(self, ground_truth_id: str, data: dict[str, Any]) -> Path:
        """Persist a ground-truth artifact."""
        target_path = self.ground_truth_dir / f"{ground_truth_id}.json"
        write_json(target_path, data)
        logger.info("Saved ground truth '%s' to %s", ground_truth_id, target_path)
        return target_path

    def list_ground_truth_ids(self) -> list[str]:
        """List all available ground-truth IDs."""
        ids: set[str] = set()
        for search_dir in self.search_dirs:
            for p in sorted(search_dir.glob("*.json")):
                try:
                    data = read_json(p)
                    if isinstance(data, dict):
                        gt_id = data.get("ground_truth_id") or p.stem
                        ids.add(gt_id)
                except Exception as err:
                    logger.warning("Could not parse ground truth file %s: %s", p, err)
        return sorted(ids)


class ResultsRepository:
    """Repository for persisting model responses, evaluation results, and experiment records."""

    def __init__(self, results_paths: Optional[ProjectPaths] = None) -> None:
        paths = results_paths or get_paths()
        self.raw_runs_dir = paths.raw_runs_dir
        self.processed_dir = paths.processed_dir
        self.reports_dir = paths.reports_dir
        paths.ensure_directories()

    def save_model_response(self, response: ModelResponse) -> Path:
        """Persist a single model response record."""
        target = self.raw_runs_dir / f"{response.response_id}.json"
        write_json(target, response)
        return target

    def load_model_response(self, response_id: str) -> ModelResponse:
        """Load a persisted model response."""
        target = self.raw_runs_dir / f"{response_id}.json"
        if not target.exists():
            raise DatasetError(f"Model response '{response_id}' not found in {self.raw_runs_dir}")
        data = read_json(target)
        return ModelResponse.model_validate(data)

    def save_evaluation_result(self, result: EvaluationResult) -> Path:
        """Persist a graded evaluation result."""
        target = self.processed_dir / f"{result.evaluation_id}.json"
        write_json(target, result)
        return target

    def load_evaluation_result(self, evaluation_id: str) -> EvaluationResult:
        """Load a persisted evaluation result."""
        target = self.processed_dir / f"{evaluation_id}.json"
        if not target.exists():
            raise DatasetError(
                f"Evaluation result '{evaluation_id}' not found in {self.processed_dir}"
            )
        data = read_json(target)
        return EvaluationResult.model_validate(data)

    def save_experiment_record(self, experiment: ExperimentRecord) -> Path:
        """Persist an experiment execution record."""
        target = self.processed_dir / f"{experiment.experiment_id}.json"
        write_json(target, experiment)
        return target

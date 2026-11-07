"""Benchmark registry for dynamic discovery, registration, and lookup of evaluation artifacts.

Architectural Security Invariant:
BenchmarkRegistry manages model-visible Scenarios and BenchmarkTasks.
It contains NO ground-truth storage, retrieval methods, or ground-truth loading logic.
Evaluator ground-truth access is strictly segregated into GroundTruthRepository.
"""

from typing import Optional

from phoenix_eval.benchmark.scenario_loader import load_scenarios_from_dir
from phoenix_eval.benchmark.task_loader import load_tasks_from_dir
from phoenix_eval.core.exceptions import (
    DuplicateEntityError,
    EntityNotFoundError,
    TaskNotFoundError,
)
from phoenix_eval.core.logging import get_logger
from phoenix_eval.core.paths import ProjectPaths, get_paths
from phoenix_eval.data.validators import validate_cross_artifact_integrity
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import BenchmarkTask, DifficultyLevel, TaskCategory

logger = get_logger("benchmark.registry")


class BenchmarkRegistry:
    """Central dynamic registry managing model-visible scenarios and benchmark tasks."""

    def __init__(self) -> None:
        self._scenarios: dict[str, ScenarioModel] = {}
        self._tasks: dict[str, BenchmarkTask] = {}

    def clear(self) -> None:
        """Reset all registered in-memory scenarios and tasks."""
        self._scenarios.clear()
        self._tasks.clear()

    # --- Scenario Methods ---

    def register_scenario(self, scenario: ScenarioModel, overwrite: bool = False) -> None:
        """Register a ScenarioModel in the benchmark registry."""
        if scenario.scenario_id in self._scenarios and not overwrite:
            raise DuplicateEntityError(f"Scenario '{scenario.scenario_id}' is already registered.")
        self._scenarios[scenario.scenario_id] = scenario
        logger.debug("Registered scenario: %s", scenario.scenario_id)

    def get_scenario(self, scenario_id: str) -> ScenarioModel:
        """Retrieve a registered ScenarioModel by its unique ID."""
        if scenario_id not in self._scenarios:
            raise EntityNotFoundError(
                f"Scenario '{scenario_id}' not found in registry. "
                f"Available: {sorted(self._scenarios.keys())}"
            )
        return self._scenarios[scenario_id]

    def list_scenarios(self) -> list[ScenarioModel]:
        """Return a sorted list of all registered scenarios."""
        return [self._scenarios[sid] for sid in sorted(self._scenarios.keys())]

    def get_scenarios_map(self) -> dict[str, ScenarioModel]:
        """Return a copy of the registered scenarios map."""
        return dict(self._scenarios)

    # --- Task Methods ---

    def register_task(self, task: BenchmarkTask, overwrite: bool = False) -> None:
        """Register a BenchmarkTask in the benchmark registry."""
        if task.task_id in self._tasks and not overwrite:
            raise DuplicateEntityError(f"Task '{task.task_id}' is already registered.")
        self._tasks[task.task_id] = task
        logger.debug("Registered task: %s", task.task_id)

    def get_task(self, task_id: str) -> BenchmarkTask:
        """Retrieve a registered BenchmarkTask by its unique ID."""
        if task_id not in self._tasks:
            raise TaskNotFoundError(
                f"Benchmark task '{task_id}' not found in registry. "
                f"Available: {sorted(self._tasks.keys())}"
            )
        return self._tasks[task_id]

    def list_tasks(
        self,
        category: Optional[TaskCategory] = None,
        difficulty: Optional[DifficultyLevel] = None,
        tag: Optional[str] = None,
    ) -> list[BenchmarkTask]:
        """List and filter registered benchmark tasks."""
        results = list(self._tasks.values())

        if category is not None:
            results = [t for t in results if t.task_category == category]
        if difficulty is not None:
            results = [t for t in results if t.difficulty == difficulty]
        if tag is not None:
            results = [t for t in results if tag in t.tags]

        return sorted(results, key=lambda t: t.task_id)

    def get_tasks_map(self) -> dict[str, BenchmarkTask]:
        """Return a copy of the registered tasks map."""
        return dict(self._tasks)

    # --- Discovery and Validation ---

    def discover_and_load(
        self,
        project_paths: Optional[ProjectPaths] = None,
        include_generated: bool = False,
    ) -> dict[str, int]:
        """Scan benchmark directories and dynamically register scenarios and tasks.

        Args:
            project_paths: Optional custom ProjectPaths.
            include_generated: If True, also scan datasets/generated/ for scenarios and tasks.

        Returns:
            Dictionary with counts of loaded scenarios and tasks.
        """
        paths = project_paths or get_paths()
        loaded_scenarios = list(load_scenarios_from_dir(paths.scenarios_dir))
        if (
            include_generated
            and paths.generated_scenarios_dir
            and paths.generated_scenarios_dir.is_dir()
        ):
            loaded_scenarios.extend(load_scenarios_from_dir(paths.generated_scenarios_dir))

        for s in loaded_scenarios:
            self.register_scenario(s, overwrite=True)

        loaded_tasks = list(load_tasks_from_dir(paths.tasks_dir))
        if include_generated and paths.generated_tasks_dir and paths.generated_tasks_dir.is_dir():
            loaded_tasks.extend(load_tasks_from_dir(paths.generated_tasks_dir))

        for t in loaded_tasks:
            self.register_task(t, overwrite=True)

        summary = {
            "scenarios_loaded": len(loaded_scenarios),
            "tasks_loaded": len(loaded_tasks),
        }
        logger.info(
            "Benchmark discovery complete: %d scenarios, %d tasks.",
            summary["scenarios_loaded"],
            summary["tasks_loaded"],
        )
        return summary

    def validate_registry_integrity(self, ground_truth_ids: Optional[set[str]] = None) -> list[str]:
        """Validate cross-references between registered tasks, scenarios, and ground truths."""
        errors: list[str] = []

        # Check scenario references for all tasks
        for task_id, task in self._tasks.items():
            if task.scenario_reference not in self._scenarios:
                errors.append(
                    f"Task '{task_id}' references unknown scenario '{task.scenario_reference}'."
                )

        # If ground truth IDs are supplied by evaluator/admin context, check those too
        if ground_truth_ids is not None:
            errors.extend(
                validate_cross_artifact_integrity(
                    scenarios=self._scenarios,
                    tasks=self._tasks,
                    ground_truth_ids=ground_truth_ids,
                )
            )

        if errors:
            logger.error("Registry integrity violations detected: %s", errors)
        return sorted(set(errors))

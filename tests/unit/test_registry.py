"""Unit tests for BenchmarkRegistry discovery, registration, and integrity checks."""

import pytest

from phoenix_eval.benchmark.registry import BenchmarkRegistry
from phoenix_eval.core.exceptions import (
    DuplicateEntityError,
    EntityNotFoundError,
    TaskNotFoundError,
)
from phoenix_eval.core.paths import ProjectPaths
from phoenix_eval.data.serialization import write_json
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import BenchmarkTask, DifficultyLevel, TaskCategory


def test_registry_registration_and_lookup(
    sample_scenario: ScenarioModel,
    sample_task: BenchmarkTask,
) -> None:
    """Verify registration, duplicate rejection, and retrieval from BenchmarkRegistry."""
    registry = BenchmarkRegistry()
    registry.register_scenario(sample_scenario)
    registry.register_task(sample_task)

    assert (
        registry.get_scenario(sample_scenario.scenario_id).scenario_id
        == sample_scenario.scenario_id
    )
    assert registry.get_task(sample_task.task_id).task_id == sample_task.task_id

    # Duplicate registration without overwrite must raise DuplicateEntityError
    with pytest.raises(DuplicateEntityError):
        registry.register_scenario(sample_scenario, overwrite=False)

    with pytest.raises(DuplicateEntityError):
        registry.register_task(sample_task, overwrite=False)

    # Overwrite=True should succeed
    registry.register_scenario(sample_scenario, overwrite=True)
    registry.register_task(sample_task, overwrite=True)


def test_registry_missing_entity_raises() -> None:
    """Verify that looking up unregistered entities raises appropriate exceptions."""
    registry = BenchmarkRegistry()
    with pytest.raises(EntityNotFoundError):
        registry.get_scenario("scen-ghost")

    with pytest.raises(TaskNotFoundError):
        registry.get_task("task-ghost")


def test_registry_task_filtering(sample_task: BenchmarkTask) -> None:
    """Verify filtering tasks by category and difficulty."""
    registry = BenchmarkRegistry()
    registry.register_task(sample_task)

    matching_cat = registry.list_tasks(category=TaskCategory.MIGRATION_SEQUENCING)
    assert len(matching_cat) == 1

    non_matching_cat = registry.list_tasks(category=TaskCategory.DEPENDENCY_DISCOVERY)
    assert len(non_matching_cat) == 0

    matching_diff = registry.list_tasks(difficulty=DifficultyLevel.INTERMEDIATE)
    assert len(matching_diff) == 1


def test_registry_integrity_validation(
    sample_scenario: ScenarioModel,
    sample_task: BenchmarkTask,
) -> None:
    """Verify that registry integrity check detects missing scenario and missing ground truth references."""
    registry = BenchmarkRegistry()

    # Register task whose scenario and ground truth are not yet registered
    registry.register_task(sample_task)

    errors = registry.validate_registry_integrity(ground_truth_ids=set())
    assert len(errors) == 2
    assert any("references unknown scenario" in e for e in errors)
    assert any("references missing ground truth" in e for e in errors)

    # Register scenario and supply matching ground truth ID
    registry.register_scenario(sample_scenario)
    errors_after = registry.validate_registry_integrity(
        ground_truth_ids={sample_task.ground_truth_reference}
    )
    assert len(errors_after) == 0


def test_registry_has_no_ground_truth_interface() -> None:
    """Verify that BenchmarkRegistry exposes no ground truth storage or retrieval interfaces."""
    registry = BenchmarkRegistry()
    assert not hasattr(registry, "register_ground_truth")
    assert not hasattr(registry, "get_ground_truth")
    assert not hasattr(registry, "_ground_truths")


def test_registry_dynamic_discovery(
    mock_project_paths: ProjectPaths,
    sample_scenario: ScenarioModel,
    sample_task: BenchmarkTask,
) -> None:
    """Verify automatic filesystem discovery of scenarios and tasks."""
    write_json(mock_project_paths.scenarios_dir / "scen-test.json", sample_scenario)
    write_json(mock_project_paths.tasks_dir / "task-test.json", sample_task)

    registry = BenchmarkRegistry()
    summary = registry.discover_and_load(mock_project_paths)

    assert summary["scenarios_loaded"] == 1
    assert summary["tasks_loaded"] == 1

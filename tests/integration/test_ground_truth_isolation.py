"""Integration tests verifying architectural ground truth isolation."""

from phoenix_eval.benchmark.prompt_builder import PromptBuilder, build_model_prompt
from phoenix_eval.benchmark.registry import BenchmarkRegistry
from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.repository import GroundTruthRepository, ScenarioRepository, TaskRepository


def test_registry_does_not_store_or_expose_ground_truth() -> None:
    """Verify that BenchmarkRegistry contains no ground-truth storage or retrieval mechanisms."""
    paths = get_paths()
    registry = BenchmarkRegistry()
    summary = registry.discover_and_load(paths)

    # Registry discovers only model-facing scenarios and tasks
    assert "scenarios_loaded" in summary
    assert "tasks_loaded" in summary
    assert "ground_truths_loaded" not in summary

    # Structural verification: registry has no ground-truth methods or attributes
    assert not hasattr(registry, "_ground_truths")
    assert not hasattr(registry, "register_ground_truth")
    assert not hasattr(registry, "get_ground_truth")


def test_scenario_and_task_repositories_have_no_ground_truth_methods() -> None:
    """Verify that model-facing repositories have zero ground-truth access interfaces."""
    paths = get_paths()
    scen_repo = ScenarioRepository(paths.scenarios_dir)
    task_repo = TaskRepository(paths.tasks_dir)

    assert not hasattr(scen_repo, "load_ground_truth")
    assert not hasattr(scen_repo, "get_ground_truth")
    assert not hasattr(task_repo, "load_ground_truth")
    assert not hasattr(task_repo, "get_ground_truth")


def test_model_task_payload_excludes_ground_truth_reference() -> None:
    """Verify that model-facing task serialization explicitly excludes evaluator-only fields."""
    paths = get_paths()
    task_repo = TaskRepository(paths.tasks_dir)
    task = task_repo.load_task("task-seq-pqc-001")

    # The internal BenchmarkTask has the reference for evaluator orchestration
    assert task.ground_truth_reference == "gt-seq-pqc-001"

    # But the model-facing export strictly excludes ground_truth_reference
    model_payload = task.to_model_dict()
    assert "ground_truth_reference" not in model_payload
    assert "task_id" in model_payload
    assert "task_instructions" in model_payload


def test_prompt_builder_cannot_access_ground_truth() -> None:
    """Verify that prompt construction only receives task and scenario and leaks no ground truth."""
    paths = get_paths()
    registry = BenchmarkRegistry()
    registry.discover_and_load(paths)

    task = registry.get_task("task-seq-pqc-001")
    scenario = registry.get_scenario(task.scenario_reference)

    # Prompt builder accepts only task and scenario
    import inspect

    sig = inspect.signature(PromptBuilder.build_model_prompt)
    param_names = list(sig.parameters.keys())
    assert param_names == ["task", "scenario"]

    # Generated prompt does not contain ground truth artifact ID or answer blocks
    prompt_text = build_model_prompt(task, scenario)
    assert "gt-seq-pqc-001" not in prompt_text
    assert "expected_blockers" not in prompt_text
    assert "optimal_wave_order" not in prompt_text


def test_evaluator_retrieves_ground_truth_independently() -> None:
    """Verify that the evaluator retrieves ground truth separately via GroundTruthRepository."""
    paths = get_paths()
    gt_repo = GroundTruthRepository(paths.ground_truth_dir)

    # Evaluator queries repository using task's ground truth ID
    gt_data = gt_repo.load_ground_truth("gt-seq-pqc-001")
    assert gt_data["ground_truth_id"] == "gt-seq-pqc-001"
    assert "expected_blockers" in gt_data
    assert "optimal_wave_order" in gt_data

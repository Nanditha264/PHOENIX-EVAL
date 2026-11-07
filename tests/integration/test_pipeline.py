"""Integration test verifying end-to-end evaluation workflow."""

from phoenix_eval.benchmark.prompt_builder import build_model_prompt
from phoenix_eval.benchmark.registry import BenchmarkRegistry
from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.repository import GroundTruthRepository, ResultsRepository
from phoenix_eval.data.validators import analyze_scenario_graph
from phoenix_eval.evaluator.result import MockEvaluator
from phoenix_eval.providers.base import MockModelProvider, ProviderPromptRequest
from phoenix_eval.schemas.common import ExecutionStatus, SafetyGateStatus


def test_end_to_end_benchmark_pipeline() -> None:
    """Verify complete Phase 1 benchmark execution and evaluation lifecycle."""
    paths = get_paths()
    registry = BenchmarkRegistry()
    summary = registry.discover_and_load(paths)

    assert summary["scenarios_loaded"] >= 1
    assert summary["tasks_loaded"] >= 1

    # 1. Fetch benchmark task and corresponding scenario from registry
    task = registry.get_task("task-seq-pqc-001")
    scenario = registry.get_scenario(task.scenario_reference)

    assert task.scenario_reference == scenario.scenario_id

    # 2. Analyze scenario graph
    graph_analysis = analyze_scenario_graph(scenario)
    assert graph_analysis["node_count"] == len(scenario.system_components)
    assert graph_analysis["edge_count"] == len(scenario.dependencies)
    assert len(graph_analysis["identified_blockers"]) > 0

    # 3. Simulate Model Provider invocation using PromptBuilder
    prompt_text = build_model_prompt(task, scenario)
    request = ProviderPromptRequest(
        task_id=task.task_id,
        prompt=prompt_text,
        temperature=0.0,
        max_tokens=1000,
    )
    provider = MockModelProvider(model_identifier="mock-eval-bot")
    response = provider.generate_response(request)

    assert response.task_id == task.task_id
    assert response.execution_status == ExecutionStatus.COMPLETED
    assert response.token_usage is not None
    assert response.token_usage.total_tokens > 0

    # 4. Evaluator retrieves ground truth via GroundTruthRepository and evaluates response
    gt_repo = GroundTruthRepository(paths.ground_truth_dir)
    ground_truth = gt_repo.load_ground_truth(task.ground_truth_reference)

    evaluator = MockEvaluator()
    eval_result = evaluator.evaluate(task, response, ground_truth)

    assert eval_result.task_id == task.task_id
    assert eval_result.response_id == response.response_id
    assert eval_result.safety_gate_status == SafetyGateStatus.PASSED
    assert eval_result.final_status == "PASSED"
    assert eval_result.raw_score == 100.0

    # 5. Persist results in repository and re-load
    results_repo = ResultsRepository(paths)
    resp_path = results_repo.save_model_response(response)
    eval_path = results_repo.save_evaluation_result(eval_result)

    assert resp_path.exists()
    assert eval_path.exists()

    loaded_resp = results_repo.load_model_response(response.response_id)
    loaded_eval = results_repo.load_evaluation_result(eval_result.evaluation_id)

    assert loaded_resp.response_id == response.response_id
    assert loaded_eval.evaluation_id == eval_result.evaluation_id

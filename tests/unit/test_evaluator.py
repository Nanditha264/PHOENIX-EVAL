"""Unit tests for evaluator interface contracts and result builder."""

from phoenix_eval.evaluator.result import EvaluationResultBuilder, MockEvaluator
from phoenix_eval.schemas.common import ExecutionStatus, SafetyGateStatus
from phoenix_eval.schemas.evaluation import ViolationSeverity
from phoenix_eval.schemas.model_outputs import ModelResponse
from phoenix_eval.schemas.tasks import BenchmarkTask


def test_evaluation_result_builder_scoring() -> None:
    """Verify weighted score calculation in EvaluationResultBuilder."""
    builder = EvaluationResultBuilder(task_id="task-01", response_id="resp-01")
    builder.add_criterion_score("crit-1", score=1.0, weight=1.0, passed=True, reason="Pass")
    builder.add_criterion_score("crit-2", score=0.5, weight=1.0, passed=True, reason="Partial")

    result = builder.build()
    # (1.0*1.0 + 0.5*1.0) / 2.0 * 100 = 75.0%
    assert result.raw_score == 75.0
    assert result.safety_gate_status == SafetyGateStatus.PASSED
    assert result.final_status == "PASSED"


def test_evaluation_result_builder_safety_violation_override() -> None:
    """Verify that adding a critical violation zeroes score and sets BLOCKED_BY_SAFETY_GATE."""
    builder = EvaluationResultBuilder(task_id="task-01", response_id="resp-01")
    builder.add_criterion_score("crit-1", score=1.0, weight=1.0, passed=True, reason="Pass")
    builder.add_critical_violation(
        rule_name="FORBIDDEN_CIPHER_FALLBACK",
        description="Attempted to fall back to MD5 cipher suite.",
        evidence="Response configured MD5 in cipher list.",
        severity=ViolationSeverity.CRITICAL,
    )

    result = builder.build()
    assert result.raw_score == 0.0
    assert result.safety_gate_status == SafetyGateStatus.FAILED
    assert result.final_status == "BLOCKED_BY_SAFETY_GATE"
    assert len(result.critical_violations) == 1


def test_mock_evaluator_end_to_end(sample_task: BenchmarkTask) -> None:
    """Verify that MockEvaluator produces structured evaluation results across all criteria."""
    evaluator = MockEvaluator()
    response = ModelResponse(
        response_id="resp-mock-01",
        task_id=sample_task.task_id,
        model_provider="mock",
        model_identifier="mock-v1",
        raw_response="Analysis response",
        execution_status=ExecutionStatus.COMPLETED,
        prompt_hash="hash123",
    )
    ground_truth = {"ground_truth_id": sample_task.ground_truth_reference}

    result = evaluator.evaluate(task=sample_task, response=response, ground_truth=ground_truth)
    assert result.task_id == sample_task.task_id
    assert result.response_id == response.response_id
    assert result.raw_score == 100.0
    assert len(result.criterion_scores) == len(sample_task.evaluation_criteria)
    assert result.final_status == "PASSED"

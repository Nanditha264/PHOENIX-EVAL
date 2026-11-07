"""Evaluation result builder and Phase 1 reference evaluator implementation."""

from typing import Any, Literal

from phoenix_eval.core.constants import SAFETY_GATE_PASS_THRESHOLD
from phoenix_eval.evaluator.base import BaseEvaluator
from phoenix_eval.schemas.common import SafetyGateStatus
from phoenix_eval.schemas.evaluation import (
    CriterionScore,
    CriticalViolation,
    EvaluationResult,
    ViolationSeverity,
)
from phoenix_eval.schemas.model_outputs import ModelResponse
from phoenix_eval.schemas.tasks import BenchmarkTask
from phoenix_eval.utils.identifiers import generate_id


class EvaluationResultBuilder:
    """Fluent builder for constructing validated EvaluationResult instances."""

    def __init__(self, task_id: str, response_id: str) -> None:
        self.task_id = task_id
        self.response_id = response_id
        self.criterion_scores: list[CriterionScore] = []
        self.critical_violations: list[CriticalViolation] = []
        self.false_positive_count: int = 0
        self.metadata: dict[str, Any] = {}

    def add_criterion_score(
        self,
        criterion_id: str,
        score: float,
        passed: bool,
        reason: str,
        weight: float = 1.0,
    ) -> "EvaluationResultBuilder":
        """Add an evaluated score for a single criterion."""
        self.criterion_scores.append(
            CriterionScore(
                criterion_id=criterion_id,
                score=score,
                weight=weight,
                passed=passed,
                reason=reason,
            )
        )
        return self

    def add_critical_violation(
        self,
        rule_name: str,
        description: str,
        evidence: str,
        severity: ViolationSeverity = ViolationSeverity.CRITICAL,
    ) -> "EvaluationResultBuilder":
        """Record a safety gate violation."""
        self.critical_violations.append(
            CriticalViolation(
                violation_id=generate_id("viol", rule_name),
                rule_name=rule_name,
                description=description,
                evidence=evidence,
                severity=severity,
            )
        )
        return self

    def set_false_positives(self, count: int) -> "EvaluationResultBuilder":
        """Record count of false positive claims."""
        self.false_positive_count = max(0, count)
        return self

    def add_metadata(self, key: str, value: Any) -> "EvaluationResultBuilder":
        """Attach audit metadata."""
        self.metadata[key] = value
        return self

    def build(self) -> EvaluationResult:
        """Calculate weighted score, evaluate safety gates, and return EvaluationResult."""
        total_weight = sum(c.weight for c in self.criterion_scores)
        weighted_sum = sum(c.weighted_score for c in self.criterion_scores)

        raw_score = (weighted_sum / total_weight * 100.0) if total_weight > 0 else 0.0

        final_status: Literal["PASSED", "FAILED", "BLOCKED_BY_SAFETY_GATE", "INCOMPLETE"]
        # Safety gate evaluation:
        # If critical violations exist, safety gate fails regardless of raw score!
        if self.critical_violations:
            safety_status = SafetyGateStatus.FAILED
            final_status = "BLOCKED_BY_SAFETY_GATE"
            raw_score = 0.0  # Zero out score on safety gate breach
        elif raw_score >= SAFETY_GATE_PASS_THRESHOLD:
            safety_status = SafetyGateStatus.PASSED
            final_status = "PASSED"
        else:
            safety_status = SafetyGateStatus.PASSED
            final_status = "FAILED"

        return EvaluationResult(
            evaluation_id=generate_id("eval", self.task_id),
            task_id=self.task_id,
            response_id=self.response_id,
            criterion_scores=self.criterion_scores,
            raw_score=round(raw_score, 2),
            safety_gate_status=safety_status,
            critical_violations=self.critical_violations,
            false_positive_count=self.false_positive_count,
            final_status=final_status,
            evaluation_metadata=self.metadata,
        )


class MockEvaluator(BaseEvaluator):
    """Reference evaluator for testing Phase 1 workflows without full grading algorithms."""

    def __init__(self) -> None:
        super().__init__(evaluator_name="mock-evaluator", evaluator_version="0.1.0")

    def evaluate(
        self,
        task: BenchmarkTask,
        response: ModelResponse,
        ground_truth: dict[str, Any],
    ) -> EvaluationResult:
        """Simulate rubric evaluation based on task criteria and ground truth presence."""
        builder = EvaluationResultBuilder(task_id=task.task_id, response_id=response.response_id)

        builder.add_metadata("evaluator_name", self.evaluator_name)
        builder.add_metadata("evaluator_version", self.evaluator_version)
        builder.add_metadata("ground_truth_id", ground_truth.get("ground_truth_id", "unknown"))

        # Score each criterion defined in the task
        for crit in task.evaluation_criteria:
            builder.add_criterion_score(
                criterion_id=crit.criterion_id,
                score=1.0,
                weight=crit.weight,
                passed=True,
                reason=f"Mock evaluation passed criterion '{crit.name}'.",
            )

        return builder.build()

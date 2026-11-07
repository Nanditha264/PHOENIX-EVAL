"""Abstract evaluator interface defining evaluation and grading contracts."""

import abc
from typing import Any

from phoenix_eval.core.logging import get_logger
from phoenix_eval.schemas.evaluation import EvaluationResult
from phoenix_eval.schemas.model_outputs import ModelResponse
from phoenix_eval.schemas.tasks import BenchmarkTask

logger = get_logger("evaluator.base")


class BaseEvaluator(abc.ABC):
    """Abstract base class for benchmark evaluation engines.

    Phase 3 will implement comprehensive automated grading rubrics,
    dependency path verification, and safety-gate rule engines.
    """

    def __init__(self, evaluator_name: str, evaluator_version: str = "1.0.0") -> None:
        self.evaluator_name = evaluator_name
        self.evaluator_version = evaluator_version

    @abc.abstractmethod
    def evaluate(
        self,
        task: BenchmarkTask,
        response: ModelResponse,
        ground_truth: dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate a model response against benchmark task criteria and ground truth.

        Args:
            task: The benchmark challenge definition.
            response: The response captured from the AI model.
            ground_truth: Evaluator-only ground truth data.

        Returns:
            Structured EvaluationResult detailing scores and safety gate determinations.

        Raises:
            EvaluationError: If grading encounters unrecoverable errors.
        """
        pass

"""Evaluator interfaces and result builders for PHOENIX-EVAL."""

from phoenix_eval.evaluator.base import BaseEvaluator
from phoenix_eval.evaluator.result import EvaluationResultBuilder, MockEvaluator

__all__ = [
    "BaseEvaluator",
    "EvaluationResultBuilder",
    "MockEvaluator",
]

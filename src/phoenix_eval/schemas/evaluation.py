"""Evaluation result schemas capturing grading scores, safety gates, and violation reports."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from phoenix_eval.schemas.common import SafetyGateStatus, StrEnum
from phoenix_eval.utils.identifiers import ensure_valid_identifier


class ViolationSeverity(StrEnum):
    """Severity classification of an evaluation safety violation."""

    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CriterionScore(BaseModel):
    """Evaluated score for an individual rubric criterion."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    criterion_id: str = Field(..., description="ID of the evaluation criterion being scored.")
    score: float = Field(..., ge=0.0, le=1.0, description="Normalized score between 0.0 and 1.0.")
    weight: float = Field(default=1.0, ge=0.0, description="Weight factor for this criterion.")
    passed: bool = Field(
        ..., description="Whether the response met the pass threshold for this criterion."
    )
    reason: str = Field(
        ..., min_length=1, description="Evaluator justification for the assigned score."
    )

    @field_validator("criterion_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="criterion_id")

    @property
    def weighted_score(self) -> float:
        """Calculate weighted score contribution."""
        return self.score * self.weight


class CriticalViolation(BaseModel):
    """A serious cryptographic or architectural migration safety violation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    violation_id: str = Field(..., description="Unique ID for this violation instance.")
    rule_name: str = Field(..., min_length=1, description="Name of the safety gate rule violated.")
    description: str = Field(
        ..., min_length=1, description="Explanation of why the model response violated safety."
    )
    severity: ViolationSeverity = Field(
        default=ViolationSeverity.CRITICAL,
        description="Severity level of the violation.",
    )
    evidence: str = Field(
        ...,
        min_length=1,
        description="Evidence or snippet from the model response that triggered the violation.",
    )

    @field_validator("violation_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="violation_id")


class EvaluationResult(BaseModel):
    """Complete structured evaluation outcome for an AI model response."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_id: str = Field(
        ...,
        description="Unique identifier for the evaluation result (e.g. 'eval-task-001-mock-1').",
    )
    task_id: str = Field(..., description="ID of the evaluated benchmark task.")
    response_id: str = Field(..., description="ID of the evaluated model response.")
    criterion_scores: list[CriterionScore] = Field(
        default_factory=list,
        description="Granular scores across individual rubric criteria.",
    )
    raw_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Aggregate percentage score (0.0 to 100.0).",
    )
    safety_gate_status: SafetyGateStatus = Field(
        default=SafetyGateStatus.PASSED,
        description="Outcome of mandatory safety gate checks.",
    )
    critical_violations: list[CriticalViolation] = Field(
        default_factory=list,
        description="List of critical safety violations detected, if any.",
    )
    false_positive_count: int = Field(
        default=0,
        ge=0,
        description="Count of false-positive claims (e.g. claiming unsupported components are supported).",
    )
    final_status: Literal["PASSED", "FAILED", "BLOCKED_BY_SAFETY_GATE", "INCOMPLETE"] = Field(
        ...,
        description="Final benchmark evaluation determination.",
    )
    evaluation_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Auditing information (evaluator version, execution duration, ground truth hash).",
    )

    @field_validator("evaluation_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="evaluation_id")

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="task_id")

    @field_validator("response_id")
    @classmethod
    def validate_response_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="response_id")

"""Benchmark task schema defining model evaluation challenges."""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from phoenix_eval.schemas.common import StrEnum
from phoenix_eval.utils.identifiers import ensure_valid_identifier


class TaskCategory(StrEnum):
    """Core evaluation categories of the PHOENIX-EVAL benchmark."""

    DEPENDENCY_DISCOVERY = "DEPENDENCY_DISCOVERY"
    COMPATIBILITY_ASSESSMENT = "COMPATIBILITY_ASSESSMENT"
    MIGRATION_SEQUENCING = "MIGRATION_SEQUENCING"
    BLOCKER_IDENTIFICATION = "BLOCKER_IDENTIFICATION"
    EVIDENCE_VERIFICATION = "EVIDENCE_VERIFICATION"
    RISK_ASSESSMENT = "RISK_ASSESSMENT"


class DifficultyLevel(StrEnum):
    """Complexity classification of a benchmark task."""

    INTRODUCTORY = "INTRODUCTORY"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"
    EXPERT = "EXPERT"


class EvaluationCriterion(BaseModel):
    """Rubric criterion for grading model responses against ground truth."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    criterion_id: str = Field(
        ..., description="Unique ID for criterion (e.g. 'crit-seq-correctness')."
    )
    name: str = Field(..., min_length=1, description="Short title of the rubric criterion.")
    description: str = Field(
        ..., min_length=1, description="Detailed explanation of the grading expectation."
    )
    weight: float = Field(
        default=1.0, ge=0.0, le=100.0, description="Relative weighting of this criterion."
    )
    is_safety_critical: bool = Field(
        default=False,
        description="If True, failure of this criterion triggers an automatic safety gate violation.",
    )

    @field_validator("criterion_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="criterion_id")


class BenchmarkTask(BaseModel):
    """A standardized cryptographic migration benchmark challenge presented to an AI model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str = Field(
        ...,
        description="Unique identifier for the benchmark task (e.g. 'task-seq-pqc-001').",
    )
    task_name: str = Field(
        ...,
        min_length=1,
        description="Descriptive title of the benchmark task.",
    )
    task_category: TaskCategory = Field(
        ...,
        description="Primary benchmark reasoning capability evaluated by this task.",
    )
    task_family: Optional[str] = Field(
        default=None,
        description="Benchmark task family classification (e.g. 'T01', 'T02', ..., 'T10').",
    )
    difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.INTERMEDIATE,
        description="Graded difficulty tier.",
    )
    description: str = Field(
        ...,
        min_length=1,
        description="Narrative context of the evaluation problem.",
    )
    scenario_reference: str = Field(
        ...,
        description="ID of the ScenarioModel that provides architectural context for this task.",
    )
    task_instructions: str = Field(
        ...,
        min_length=1,
        description="Explicit instructions and prompt guidance provided to the AI model.",
    )
    expected_output_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema or structured specification defining expected response format.",
    )
    evaluation_criteria: list[EvaluationCriterion] = Field(
        default_factory=list,
        description="Rubric criteria used by the evaluator to grade the model's response.",
    )
    ground_truth_reference: str = Field(
        ...,
        description="Identifier of the evaluator-only ground truth artifact used for grading.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Taxonomy and search tags.",
    )
    version: str = Field(
        default="1.0.0",
        description="Version string for task specification.",
    )

    @field_validator("task_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="task_id")

    @field_validator("scenario_reference")
    @classmethod
    def validate_scen_ref(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="scenario_reference")

    @field_validator("ground_truth_reference")
    @classmethod
    def validate_gt_ref(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="ground_truth_reference")

    def to_model_dict(self) -> dict[str, Any]:
        """Export public task payload for model consumption, strictly excluding evaluator-only fields."""
        return self.model_dump(mode="json", exclude={"ground_truth_reference"})

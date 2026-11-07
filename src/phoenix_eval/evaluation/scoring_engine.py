"""Weighted scoring engine with configurable rubrics and separate safety gate reporting.

Preserves raw performance scores alongside safety gate outcomes, ensuring
that safety-critical failures are highlighted without erasing granular telemetry.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScoringWeights(BaseModel):
    """Configurable weights across the six benchmark evaluation dimensions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dependency_identification: float = Field(default=20.0, ge=0.0)
    compatibility_reasoning: float = Field(default=20.0, ge=0.0)
    migration_plan_correctness: float = Field(default=20.0, ge=0.0)
    evidence_and_uncertainty: float = Field(default=15.0, ge=0.0)
    validation_and_safety_gates: float = Field(default=15.0, ge=0.0)
    explanation_and_traceability: float = Field(default=10.0, ge=0.0)

    @model_validator(mode="after")
    def validate_total_weight(self) -> "ScoringWeights":
        total = (
            self.dependency_identification
            + self.compatibility_reasoning
            + self.migration_plan_correctness
            + self.evidence_and_uncertainty
            + self.validation_and_safety_gates
            + self.explanation_and_traceability
        )
        if abs(total - 100.0) > 1e-4:
            raise ValueError(f"Scoring weights must sum to exactly 100.0, got {round(total, 4)}.")
        return self


@dataclass(frozen=True)
class DimensionScoreSummary:
    """Summary of score and deductions for an individual dimension."""

    dimension_name: str
    weight: float
    raw_score: float
    max_score: float
    normalized_score: float  # 0.0 to 1.0
    weighted_contribution: float  # (raw_score / max_score) * weight
    deductions: list[tuple[float, str]]


@dataclass(frozen=True)
class ScoreResult:
    """Overall scoring outcome detailing raw scores, effective scores, and status."""

    raw_weighted_score: float  # 0.0 to 100.0 (net raw score after cross-cutting adjustments)
    effective_score: float  # 0.0 if safety gate failed, else raw_weighted_score
    safety_gate_passed: bool
    overall_status: str  # "PASSED", "FAILED", "BLOCKED_BY_SAFETY_GATE"
    pass_threshold: float
    dimension_summaries: list[DimensionScoreSummary]
    raw_dimension_score: float = 0.0  # unadjusted sum across 6 dimensions
    constraint_deductions: float = 0.0  # cross-cutting deductions from constraint grader
    constraint_deduction_details: list[tuple[float, str]] = field(default_factory=list)


class ScoringEngine:
    """Computes reproducible weighted scores across evaluation dimensions.

    Operational Policy on Constraints:
    Migration constraints and step preconditions act as cross-cutting architectural
    and safety adjustments. The 6 core dimensions establish the baseline capability
    score (summing to 100.0 points). Non-critical constraint and precondition
    deductions are applied directly as cross-cutting penalties against the raw score.
    Critical constraint violations trigger an immediate safety gate veto, driving the
    effective operational score to 0.0 without double-counting dimensional deductions.
    """

    def __init__(
        self,
        weights: Optional[ScoringWeights] = None,
        pass_threshold: float = 70.0,
    ) -> None:
        self.weights = weights or ScoringWeights()
        self.pass_threshold = pass_threshold

    def calculate_score(
        self,
        dimension_results: dict[str, Any],
        safety_gate_passed: bool,
        constraint_result: Optional[Any] = None,
    ) -> ScoreResult:
        """Calculate weighted score, preserve raw score, apply cross-cutting constraint deductions, and determine overall status."""
        summaries: list[DimensionScoreSummary] = []
        weighted_sum = 0.0

        weight_dict = {
            "dependency_identification": self.weights.dependency_identification,
            "compatibility_reasoning": self.weights.compatibility_reasoning,
            "migration_plan_correctness": self.weights.migration_plan_correctness,
            "evidence_and_uncertainty": self.weights.evidence_and_uncertainty,
            "validation_and_safety_gates": self.weights.validation_and_safety_gates,
            "explanation_and_traceability": self.weights.explanation_and_traceability,
        }

        for dim_name, target_weight in weight_dict.items():
            res = dimension_results.get(dim_name)
            if res:
                raw_score = res.raw_score
                max_score = res.max_score
                norm = res.normalized_score
                deductions = res.deductions
            else:
                raw_score = 0.0
                max_score = target_weight
                norm = 0.0
                deductions = [(target_weight, f"Dimension '{dim_name}' not evaluated.")]

            # Compute contribution proportional to target weight
            contribution = (norm * target_weight) if max_score > 0 else 0.0
            weighted_sum += contribution

            summaries.append(
                DimensionScoreSummary(
                    dimension_name=dim_name,
                    weight=target_weight,
                    raw_score=round(raw_score, 2),
                    max_score=round(max_score, 2),
                    normalized_score=round(norm, 4),
                    weighted_contribution=round(contribution, 2),
                    deductions=deductions,
                )
            )

        raw_dimension_score = round(weighted_sum, 2)

        # Cross-cutting constraint deductions
        constraint_deds = 0.0
        constraint_details: list[tuple[float, str]] = []
        if constraint_result is not None:
            # Non-critical constraint check deductions
            for check in getattr(constraint_result, "constraint_checks", []):
                if (
                    not getattr(check, "is_critical", False)
                    and getattr(check, "score_impact", 0.0) > 0
                ):
                    constraint_deds += check.score_impact
                    constraint_details.append((check.score_impact, check.reason))

            # Precondition findings deductions
            for pf in getattr(constraint_result, "precondition_findings", []):
                if getattr(pf, "deduction", 0.0) > 0:
                    constraint_deds += pf.deduction
                    constraint_details.append((pf.deduction, pf.description))

        raw_weighted_score = max(0.0, round(raw_dimension_score - constraint_deds, 2))

        # Critical Safety Policy:
        # If safety gate failed, effective_score is 0.0, but raw_weighted_score is PRESERVED
        if not safety_gate_passed:
            effective_score = 0.0
            overall_status = "BLOCKED_BY_SAFETY_GATE"
        elif raw_weighted_score >= self.pass_threshold:
            effective_score = raw_weighted_score
            overall_status = "PASSED"
        else:
            effective_score = raw_weighted_score
            overall_status = "FAILED"

        return ScoreResult(
            raw_weighted_score=raw_weighted_score,
            effective_score=effective_score,
            safety_gate_passed=safety_gate_passed,
            overall_status=overall_status,
            pass_threshold=self.pass_threshold,
            dimension_summaries=summaries,
            raw_dimension_score=raw_dimension_score,
            constraint_deductions=round(constraint_deds, 2),
            constraint_deduction_details=constraint_details,
        )

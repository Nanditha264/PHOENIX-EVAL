"""Authoritative evaluation report schema, serialization, and analysis export engine."""

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from phoenix_eval.data.serialization import read_json, write_json
from phoenix_eval.utils.time import current_utc_timestamp


class DetailedEvaluationReport(BaseModel):
    """Complete machine-readable evaluation report capturing all scores, facts, and safety vetos."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_id: str = Field(..., description="Unique evaluation result identifier.")
    task_id: str = Field(..., description="Benchmark task ID evaluated.")
    scenario_id: str = Field(..., description="Scenario ID evaluated.")
    model_identifier: str = Field(default="unknown", description="Name/ID of the model evaluated.")
    model_version: str = Field(default="unknown", description="Model version evaluated.")
    contract_version: str = Field(default="1.0.0", description="Response contract version.")
    evaluator_version: str = Field(default="3.0.0", description="Evaluator engine version.")
    timestamp: datetime = Field(
        default_factory=current_utc_timestamp, description="UTC evaluation timestamp."
    )

    # Response Validity
    is_valid_json: bool = Field(..., description="Whether model output parsed as valid JSON.")
    is_valid_contract: bool = Field(
        ..., description="Whether output satisfied strict response contract schema."
    )
    parsing_errors: list[str] = Field(default_factory=list, description="JSON or syntax errors.")
    validation_errors: list[str] = Field(
        default_factory=list, description="Schema contract validation errors."
    )

    # Scores
    raw_weighted_score: float = Field(
        ..., ge=0.0, le=100.0, description="Raw weighted rubric score."
    )
    effective_score: float = Field(
        ..., ge=0.0, le=100.0, description="Effective score (0 on safety failure)."
    )
    safety_gate_passed: bool = Field(..., description="Whether all critical safety gates passed.")
    overall_status: str = Field(..., description="PASSED, FAILED, or BLOCKED_BY_SAFETY_GATE.")

    # Dimension Breakdown
    dimension_scores: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Granular scores, maximums, and deductions by dimension.",
    )

    # Violations & Safety
    critical_violations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Critical safety violations that caused safety gate failure.",
    )
    non_critical_violations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="High-severity non-critical reasoning violations.",
    )

    # Specific Findings by Dimension
    dependency_findings: dict[str, Any] = Field(default_factory=dict)
    compatibility_findings: dict[str, Any] = Field(default_factory=dict)
    migration_order_findings: dict[str, Any] = Field(default_factory=dict)
    evidence_findings: dict[str, Any] = Field(default_factory=dict)
    verification_gate_findings: dict[str, Any] = Field(default_factory=dict)
    constraint_findings: dict[str, Any] = Field(
        default_factory=dict,
        description="Constraint evaluation breakdown, check details, and precondition findings.",
    )
    cross_cutting_deductions: float = Field(
        default=0.0,
        description="Total cross-cutting deductions from non-critical constraints and preconditions.",
    )

    # Authoritative Readiness
    authoritative_readiness_decision: str = Field(
        ...,
        description="Authoritative benchmark determination: MIGRATION_READY, MIGRATION_BLOCKED, CONDITIONAL.",
    )
    model_reported_decision: Optional[str] = Field(
        default=None,
        description="Decision reported by the model.",
    )

    evaluation_trace: list[str] = Field(
        default_factory=list, description="Step-by-step reasoning trace."
    )
    rubric_weights: dict[str, float] = Field(
        default_factory=dict, description="Rubric weights used."
    )

    def save(self, output_dir: Path) -> Path:
        """Persist evaluation report as deterministic JSON."""
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / f"{self.evaluation_id}.json"
        write_json(file_path, self.model_dump(mode="json"), indent=2)
        return file_path

    @classmethod
    def load(cls, file_path: Path) -> "DetailedEvaluationReport":
        """Load evaluation report from JSON file."""
        data = read_json(file_path)
        return cls.model_validate(data)


def save_evaluation_report(report: DetailedEvaluationReport, output_dir: Path) -> Path:
    """Save evaluation report to disk."""
    return report.save(output_dir)


def load_evaluation_report(file_path: Path) -> DetailedEvaluationReport:
    """Load evaluation report from disk."""
    return DetailedEvaluationReport.load(file_path)


def export_reports_to_csv(reports: list[DetailedEvaluationReport], output_csv: Path) -> Path:
    """Export multiple evaluation reports to CSV for empirical experiment analysis."""
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "evaluation_id",
        "task_id",
        "scenario_id",
        "model_identifier",
        "raw_weighted_score",
        "effective_score",
        "safety_gate_passed",
        "overall_status",
        "authoritative_readiness_decision",
        "model_reported_decision",
        "critical_violations_count",
        "dependency_score",
        "compatibility_score",
        "plan_score",
        "evidence_score",
        "gate_score",
        "explanation_score",
        "timestamp",
    ]

    with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in reports:
            writer.writerow(
                {
                    "evaluation_id": r.evaluation_id,
                    "task_id": r.task_id,
                    "scenario_id": r.scenario_id,
                    "model_identifier": r.model_identifier,
                    "raw_weighted_score": r.raw_weighted_score,
                    "effective_score": r.effective_score,
                    "safety_gate_passed": r.safety_gate_passed,
                    "overall_status": r.overall_status,
                    "authoritative_readiness_decision": r.authoritative_readiness_decision,
                    "model_reported_decision": r.model_reported_decision,
                    "critical_violations_count": len(r.critical_violations),
                    "dependency_score": r.dimension_scores.get("dependency_identification", {}).get(
                        "raw_score", 0.0
                    ),
                    "compatibility_score": r.dimension_scores.get(
                        "compatibility_reasoning", {}
                    ).get("raw_score", 0.0),
                    "plan_score": r.dimension_scores.get("migration_plan_correctness", {}).get(
                        "raw_score", 0.0
                    ),
                    "evidence_score": r.dimension_scores.get("evidence_and_uncertainty", {}).get(
                        "raw_score", 0.0
                    ),
                    "gate_score": r.dimension_scores.get("validation_and_safety_gates", {}).get(
                        "raw_score", 0.0
                    ),
                    "explanation_score": r.dimension_scores.get(
                        "explanation_and_traceability", {}
                    ).get("raw_score", 0.0),
                    "timestamp": r.timestamp.isoformat(),
                }
            )
    return output_csv

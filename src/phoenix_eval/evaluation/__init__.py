"""PHOENIX-EVAL Phase 3: Deterministic evaluation and constraint-based grading engine."""

from phoenix_eval.evaluation.calibration import CalibrationRunner, CalibrationSummary
from phoenix_eval.evaluation.compatibility_grader import CompatibilityGrader
from phoenix_eval.evaluation.constraint_grader import (
    ConstraintCheckResult,
    ConstraintGrader,
    ConstraintGradingResult,
    ConstraintStatus,
    PreconditionFinding,
)
from phoenix_eval.evaluation.dependency_grader import DependencyGrader
from phoenix_eval.evaluation.evaluation_report import (
    DetailedEvaluationReport,
    export_reports_to_csv,
    load_evaluation_report,
    save_evaluation_report,
)
from phoenix_eval.evaluation.evaluator import DeterministicEvaluator
from phoenix_eval.evaluation.evidence_grader import EvidenceGrader
from phoenix_eval.evaluation.explanation_grader import ExplanationGrader
from phoenix_eval.evaluation.independent_graph_verifier import (
    IndependentGraphVerifier,
    PlanVerificationResult,
)
from phoenix_eval.evaluation.migration_plan_grader import MigrationPlanGrader
from phoenix_eval.evaluation.response_parser import ParsedResponse, parse_model_response
from phoenix_eval.evaluation.response_validator import (
    SemanticValidationResult,
    validate_response_semantics,
)
from phoenix_eval.evaluation.safety_gate import SafetyGateEngine, SafetyGateResult
from phoenix_eval.evaluation.scoring_engine import (
    DimensionScoreSummary,
    ScoreResult,
    ScoringEngine,
    ScoringWeights,
)
from phoenix_eval.evaluation.verification_gate_grader import VerificationGateGrader
from phoenix_eval.evaluation.violation_catalog import (
    VIOLATION_CATALOG,
    VIOLATIONS_BY_CODE,
    ViolationDefinition,
)
from phoenix_eval.schemas.response_contract import (
    MigrationActionType,
    ModelDecision,
    ModelResponseContract,
    ReportedCompatibility,
    ReportedCompatibilityStatus,
    ReportedDependency,
    ReportedMigrationStep,
    ReportedTestResult,
    ReportedTestStatus,
)

ParsedModelResponse = ParsedResponse
SafetyGateEvaluationResult = SafetyGateResult
DimensionGradingResult = DimensionScoreSummary
DimensionSummary = DimensionScoreSummary
ScoringResult = ScoreResult

__all__ = [
    # Evaluator & Reporting
    "DeterministicEvaluator",
    "DetailedEvaluationReport",
    "save_evaluation_report",
    "load_evaluation_report",
    "export_reports_to_csv",
    # Response Contract
    "ModelResponseContract",
    "ModelDecision",
    "MigrationActionType",
    "ReportedCompatibilityStatus",
    "ReportedTestStatus",
    "ReportedDependency",
    "ReportedCompatibility",
    "ReportedMigrationStep",
    "ReportedTestResult",
    # Parser & Validator
    "parse_model_response",
    "ParsedResponse",
    "ParsedModelResponse",
    "validate_response_semantics",
    "SemanticValidationResult",
    # Verification
    "IndependentGraphVerifier",
    "PlanVerificationResult",
    # Safety Gates & Catalog
    "SafetyGateEngine",
    "SafetyGateResult",
    "SafetyGateEvaluationResult",
    "VIOLATION_CATALOG",
    "VIOLATIONS_BY_CODE",
    "ViolationDefinition",
    # Scoring
    "ScoringEngine",
    "ScoringWeights",
    "ScoreResult",
    "ScoringResult",
    "DimensionScoreSummary",
    "DimensionGradingResult",
    "DimensionSummary",
    # Graders
    "DependencyGrader",
    "CompatibilityGrader",
    "MigrationPlanGrader",
    "EvidenceGrader",
    "VerificationGateGrader",
    "ExplanationGrader",
    "ConstraintGrader",
    "ConstraintGradingResult",
    "ConstraintCheckResult",
    "ConstraintStatus",
    "PreconditionFinding",
    # Calibration
    "CalibrationRunner",
    "CalibrationSummary",
]

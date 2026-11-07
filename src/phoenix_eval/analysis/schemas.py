"""Analysis schemas for PHOENIX-EVAL Phase 5 Benchmark Execution, Results & Failure Intelligence."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from phoenix_eval.utils.identifiers import generate_id
from phoenix_eval.utils.time import current_utc_timestamp

# -----------------------------------------------------------------------------
# Ingestion and Data Integrity Schemas
# -----------------------------------------------------------------------------


class IngestionRecordStatus(StrEnum):
    """Validation and integrity status of an ingested experiment."""

    VALID = "VALID"
    VALID_WITH_WARNINGS = "VALID_WITH_WARNINGS"
    LEGACY_UNVERIFIABLE = "LEGACY_UNVERIFIABLE"
    CORRUPTED = "CORRUPTED"
    QUARANTINED = "QUARANTINED"
    FAILED = "FAILED"


class RunValidationIssue(BaseModel):
    """A specific data integrity or provenance defect found in an experiment run record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    issue_type: str  # e.g. MISSING_RAW_RESPONSE, HASH_MISMATCH, PROMPT_MISMATCH, EVAL_MISSING
    severity: str  # CRITICAL, WARNING, ERROR
    description: str


class IngestionReport(BaseModel):
    """Detailed audit report for an ingested experiment directory."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ingestion_id: str = Field(default_factory=lambda: generate_id("ingest"))
    experiment_id: str
    timestamp: datetime = Field(default_factory=current_utc_timestamp)
    import_status: IngestionRecordStatus
    total_scheduled_runs: int
    total_attempts: int
    completed_runs: int
    failed_runs: int
    missing_raw_responses_count: int = 0
    missing_eval_reports_count: int = 0
    response_hash_mismatches_count: int = 0
    prompt_hash_mismatches_count: int = 0
    dataset_fingerprint_match: bool = True
    recorded_dataset_fingerprint: Optional[str] = None
    active_dataset_fingerprint: Optional[str] = None
    recorded_model_visible_fingerprint: Optional[str] = None
    active_model_visible_fingerprint: Optional[str] = None
    recorded_evaluator_fingerprint: Optional[str] = None
    active_evaluator_fingerprint: Optional[str] = None
    fingerprint_algorithm: Optional[str] = None
    dataset_manifest_version: Optional[str] = None
    is_mock: bool = False
    issues: list[RunValidationIssue] = Field(default_factory=list)
    valid_run_ids: list[str] = Field(default_factory=list)
    corrupted_run_ids: list[str] = Field(default_factory=list)
    summary: str


# -----------------------------------------------------------------------------
# Comparability Schemas
# -----------------------------------------------------------------------------


class ComparabilityClassification(StrEnum):
    """Classification of whether two models or experiment runs can be scientifically compared."""

    COMPARABLE = "COMPARABLE"
    COMPARABLE_WITH_LIMITATIONS = "COMPARABLE_WITH_LIMITATIONS"
    NOT_COMPARABLE = "NOT_COMPARABLE"


class ComparabilityCriterion(BaseModel):
    """Assessment of a single dimension of experimental comparability."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    criterion_name: str
    satisfied: bool
    details: str


class ModelPairComparability(BaseModel):
    """Scientific comparability evaluation between a pair of models."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_a: str
    model_b: str
    classification: ComparabilityClassification
    reasons: list[str] = Field(default_factory=list)
    common_task_count: int
    disjoint_task_count: int
    criteria: list[ComparabilityCriterion] = Field(default_factory=list)


class ComparabilityAssessment(BaseModel):
    """System-wide comparability matrix across all models in imported experiments."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    assessment_id: str = Field(default_factory=lambda: generate_id("comp"))
    timestamp: datetime = Field(default_factory=current_utc_timestamp)
    experiment_ids: list[str] = Field(default_factory=list)
    model_pairs: list[ModelPairComparability] = Field(default_factory=list)
    summary: str


# -----------------------------------------------------------------------------
# Benchmark Performance Metrics Schemas
# -----------------------------------------------------------------------------


class OverallModelMetrics(BaseModel):
    """Comprehensive performance telemetry for a single evaluated model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_identifier: str
    model_version: str
    is_mock: bool
    scheduled_runs: int
    provider_attempts: int
    successful_responses: int
    evaluated_responses: int
    completion_rate: float
    mean_raw_score: float
    median_raw_score: float
    std_raw_score: float
    mean_effective_score: float
    median_effective_score: float
    std_effective_score: float
    safety_gate_passed_count: int
    safety_gate_failed_count: int
    safety_gate_failure_rate: float
    safety_gate_failure_rate_ci: tuple[float, float] = (0.0, 0.0)  # Wilson 95% interval
    critical_violation_count: int
    mean_latency_seconds: float
    prompt_tokens_total: int = 0
    completion_tokens_total: int = 0
    total_tokens_total: int = 0
    estimated_cost_usd_total: Optional[float] = None
    parsing_failures_count: int = 0
    provider_failures_count: int = 0
    evaluation_failures_count: int = 0


class DimensionMetrics(BaseModel):
    """Evaluation outcomes across one of the six benchmark dimensions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dimension_name: str
    model_identifier: str
    valid_response_count: int
    mean_score: float
    median_score: float
    std_score: float
    max_score: float
    mean_normalized_score: float
    lowest_performing_family: Optional[str] = None
    highest_performing_family: Optional[str] = None


class TaskFamilyMetrics(BaseModel):
    """Performance breakdown for a single model on one of the 10 benchmark task families (T01-T10)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    family_id: str
    family_name: str
    model_identifier: str
    evaluated_response_count: int
    mean_raw_score: float
    mean_effective_score: float
    safety_gate_failure_rate: float
    critical_violations_count: int
    common_error_types: list[str] = Field(default_factory=list)


class DomainMetrics(BaseModel):
    """Performance breakdown for a single model across a synthetic enterprise domain."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    domain_name: str
    model_identifier: str
    sample_count: int
    mean_raw_score: float
    mean_effective_score: float
    safety_gate_failure_rate: float
    common_error_categories: list[str] = Field(default_factory=list)


class DifficultyMetrics(BaseModel):
    """Performance breakdown for a model stratified by scenario difficulty level."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    difficulty_level: str
    model_identifier: str
    sample_count: int
    mean_raw_score: float
    mean_effective_score: float
    safety_gate_failure_rate: float


# -----------------------------------------------------------------------------
# Failure Intelligence & Taxonomy Schemas
# -----------------------------------------------------------------------------


class FailureCategory(StrEnum):
    """Authoritative six-category taxonomy of cryptographic migration failure modes (+ parsing and unclassified)."""

    DEPENDENCY = "DEPENDENCY"
    COMPATIBILITY = "COMPATIBILITY"
    EVIDENCE = "EVIDENCE"
    SAFETY = "SAFETY"
    PLANNING = "PLANNING"
    UNCERTAINTY = "UNCERTAINTY"
    PARSING = "PARSING"
    UNCLASSIFIED = "UNCLASSIFIED"


class FailureSeverity(StrEnum):
    """Severity classification of identified reasoning and safety failures."""

    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class FailureIncident(BaseModel):
    """A granular failure incident grounded in deterministic evaluator violations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    incident_id: str
    run_id: str
    task_id: str
    model_identifier: str
    category: FailureCategory
    violation_code: str
    violation_name: str
    severity: FailureSeverity
    description: str
    evidence: str


class FailurePatternScope(StrEnum):
    """Evidence scope defining repeated failure patterns."""

    SINGLE_OCCURRENCE = "SINGLE_OCCURRENCE"
    TASK_REPEATED = "TASK_REPEATED"
    CROSS_TASK_RECURRING = "CROSS_TASK_RECURRING"
    CROSS_DOMAIN_RECURRING = "CROSS_DOMAIN_RECURRING"


class FailurePattern(BaseModel):
    """A scientifically verified recurring failure pattern backed by run artifacts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: str
    pattern_name: str
    description: str
    model_identifier: str
    category: FailureCategory
    scope: FailurePatternScope
    severity: FailureSeverity
    confidence: float = Field(..., ge=0.0, le=1.0)
    supporting_run_ids: list[str] = Field(default_factory=list)
    supporting_task_ids: list[str] = Field(default_factory=list)
    supporting_violation_codes: list[str] = Field(default_factory=list)
    number_of_affected_runs: int
    number_of_affected_trials: int
    relevant_dimension: str
    suggested_interpretation: str


# -----------------------------------------------------------------------------
# Paired-Case and Metamorphic Analysis Schemas
# -----------------------------------------------------------------------------


class PairedSensitivityOutcome(StrEnum):
    """Classification of model decision sensitivity under single-fact perturbations."""

    CORRECT_SENSITIVITY = "CORRECT_SENSITIVITY"
    MISSED_CHANGE = "MISSED_CHANGE"
    UNJUSTIFIED_CHANGE = "UNJUSTIFIED_CHANGE"
    PARTIAL_SENSITIVITY = "PARTIAL_SENSITIVITY"
    INCONCLUSIVE = "INCONCLUSIVE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class PairedCaseAnalysisItem(BaseModel):
    """Evaluation of a model's response pair across Scenario A and Scenario B."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pair_id: str
    pair_type: str
    model_identifier: str
    task_a_id: str
    task_b_id: str
    decision_a: Optional[str] = None
    decision_b: Optional[str] = None
    safety_gate_passed_a: Optional[bool] = None
    safety_gate_passed_b: Optional[bool] = None
    effective_score_a: Optional[float] = None
    effective_score_b: Optional[float] = None
    perturbed_property: str
    classification: PairedSensitivityOutcome
    reasoning: str


class MetamorphicOutcome(StrEnum):
    """Outcome of testing a metamorphic relation invariant."""

    PRESERVED = "PRESERVED"
    VIOLATED = "VIOLATED"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class MetamorphicAnalysisItem(BaseModel):
    """Verification of metamorphic relation invariants (MR1-MR6) on evaluated model outputs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    relation_type: str
    model_identifier: str
    test_id: str
    description: str
    outcome: MetamorphicOutcome
    baseline_run_id: Optional[str] = None
    transformed_run_id: Optional[str] = None
    details: str


# -----------------------------------------------------------------------------
# Trial Consistency & Stability Schemas
# -----------------------------------------------------------------------------


class TrialConsistencyOutcome(StrEnum):
    """Classification of model stability across repeated trials."""

    STABLE_CORRECT = "STABLE_CORRECT"
    STABLE_UNSAFE = "STABLE_UNSAFE"
    INCONSISTENT = "INCONSISTENT"
    HIGH_VARIANCE = "HIGH_VARIANCE"
    SINGLE_TRIAL_ONLY = "SINGLE_TRIAL_ONLY"


class ModelTaskTrialConsistency(BaseModel):
    """Telemetry measuring decision and score consistency across trials for a single task."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_identifier: str
    task_id: str
    trial_count: int
    effective_scores: list[float] = Field(default_factory=list)
    score_variance: float
    decision_set: list[str] = Field(default_factory=list)
    safety_gate_passed_set: list[bool] = Field(default_factory=list)
    outcome: TrialConsistencyOutcome
    interpretation: str


# -----------------------------------------------------------------------------
# Statistical Analysis Schemas
# -----------------------------------------------------------------------------


class DescriptiveStats(BaseModel):
    """Standard descriptive statistical parameters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    count: int
    mean: float
    median: float
    std_dev: float
    min_val: float
    max_val: float


class WilsonScoreInterval(BaseModel):
    """Binomial confidence interval using Wilson score formula."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    count: int
    successes: int
    proportion: float
    lower_bound: float
    upper_bound: float
    confidence_level: float = 0.95


class BootstrapConfidenceInterval(BaseModel):
    """Non-parametric percentile bootstrap confidence interval with task-level resampling."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_name: str
    mean: float
    lower_bound: float
    upper_bound: float
    confidence_level: float = 0.95
    resamples: int = 1000


class PairedModelComparison(BaseModel):
    """Statistical comparison of two models evaluated over the same task set."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_a: str
    model_b: str
    common_tasks_count: int
    model_a_trial_count: int = 0
    model_b_trial_count: int = 0
    mean_difference: float  # score(A) - score(B)
    std_difference: float
    t_statistic: Optional[float] = None
    p_value: Optional[float] = None
    bootstrap_ci: Optional[tuple[float, float]] = None
    interpretation: str


# -----------------------------------------------------------------------------
# Analysis Manifest & Provenance
# -----------------------------------------------------------------------------


class AnalysisManifest(BaseModel):
    """Provenance tracking for a complete Phase 5 analysis run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis_id: str
    source_experiment_ids: list[str]
    dataset_fingerprints: list[str]
    benchmark_version: str = "5.0.0"
    evaluator_version: str = "3.0.0"
    analysis_timestamp: datetime = Field(default_factory=current_utc_timestamp)
    analysis_code_version: str = "5.0.0"
    input_artifact_hashes: dict[str, str] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)

"""Experiment schemas tracking multi-model multi-task benchmark campaigns, run records, and manifests."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from phoenix_eval.schemas.common import ExecutionStatus
from phoenix_eval.utils.identifiers import ensure_valid_identifier
from phoenix_eval.utils.time import current_utc_timestamp


class ExperimentLifecycleStatus(StrEnum):
    """Authoritative lifecycle status for an experiment campaign."""

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_FAILURES = "COMPLETED_WITH_FAILURES"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


class ExperimentConfig(BaseModel):
    """Validated configuration for a benchmark evaluation campaign."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment_id: str = Field(
        ...,
        description="Unique identifier for the experiment campaign (e.g. 'exp-phase4-baseline-001').",
    )
    experiment_name: str = Field(
        ...,
        min_length=1,
        description="Human-readable title of the experiment run.",
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional scientific description and hypothesis for the experiment.",
    )
    selected_models: list[str] = Field(
        ...,
        min_length=1,
        description="Identifiers of models to evaluate (must be registered in ModelRegistry).",
    )
    selected_tasks: list[str] = Field(
        ...,
        min_length=1,
        description="Identifiers of benchmark tasks included in the experiment run.",
    )
    number_of_trials: int = Field(
        default=1,
        ge=1,
        description="Number of evaluation repetitions per model/task pair.",
    )
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for model invocations.",
    )
    max_output_tokens: int = Field(
        default=2048,
        ge=64,
        description="Maximum generation token budget.",
    )
    timeout_seconds: float = Field(
        default=60.0,
        gt=0.0,
        description="Per-request timeout limit.",
    )
    retry_count: int = Field(
        default=3,
        ge=0,
        description="Number of retries on transient errors.",
    )
    request_delay_seconds: float = Field(
        default=0.0,
        ge=0.0,
        description="Rate limiting delay between requests in seconds.",
    )
    dataset_run_id: Optional[str] = Field(
        default=None,
        description="Optional dataset generation run ID for traceability.",
    )
    output_dir: Optional[str] = Field(
        default=None,
        description="Optional custom directory for persisting experiment results.",
    )
    resume: bool = Field(
        default=True,
        description="Whether to resume existing experiment runs without duplicating completed tasks.",
    )
    mode: Literal["mock", "real", "mixed", "auto"] = Field(
        default="auto",
        description="Execution mode: 'mock' (offline), 'real' (API calls), 'mixed' (explicit), or 'auto' (inferred).",
    )
    allow_mixed_mode: bool = Field(
        default=False,
        description="Explicit opt-in to evaluate both real and mock models in the same campaign.",
    )
    ignore_dataset_mismatch: bool = Field(
        default=False,
        description="Explicit opt-in to allow resuming an experiment even if the dataset fingerprint differs.",
    )

    @field_validator("experiment_id")
    @classmethod
    def validate_exp_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="experiment_id")

    @field_validator("selected_models")
    @classmethod
    def validate_models_non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("selected_models cannot be empty")
        for m in v:
            if not m or not m.strip():
                raise ValueError("Model identifier cannot be blank")
        return [m.strip() for m in v]

    @field_validator("selected_tasks")
    @classmethod
    def validate_tasks_non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("selected_tasks cannot be empty")
        for t in v:
            if not t or not t.strip():
                raise ValueError("Task identifier cannot be blank")
        return [t.strip() for t in v]


class ExperimentRunRecord(BaseModel):
    """Execution telemetry and outcome for a single model/task/trial run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment_id: str = Field(..., description="Parent experiment ID.")
    run_id: str = Field(..., description="Unique deterministic run identifier.")
    task_id: str = Field(..., description="Benchmark task ID.")
    scenario_id: str = Field(..., description="Scenario ID associated with task.")
    provider_name: str = Field(
        ..., description="Provider adapter used ('mock', 'openai', 'google')."
    )
    model_identifier: str = Field(..., description="Configured model identifier.")
    model_version: str = Field(default="default", description="Model version or snapshot.")
    configured_model_identifier: str = Field(
        default="",
        description="Model identifier specified in experiment configuration.",
    )
    configured_model_version: str = Field(
        default="",
        description="Model version specified in experiment configuration.",
    )
    returned_model_identifier: Optional[str] = Field(
        default=None,
        description="Exact model identifier returned by provider API (e.g. from response payload).",
    )
    returned_model_version: Optional[str] = Field(
        default=None,
        description="Exact model version returned by provider API (None if omitted).",
    )
    provider_request_id: Optional[str] = Field(
        default=None,
        description="Unique request ID returned by provider API or headers.",
    )

    @model_validator(mode="before")
    @classmethod
    def populate_configured_model_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Ensure configured_model_identifier and model_identifier are in sync
            if not data.get("configured_model_identifier") and data.get("model_identifier"):
                data["configured_model_identifier"] = data["model_identifier"]
            elif not data.get("model_identifier") and data.get("configured_model_identifier"):
                data["model_identifier"] = data["configured_model_identifier"]

            # Ensure configured_model_version and model_version are in sync
            if not data.get("configured_model_version") and data.get("model_version"):
                data["configured_model_version"] = data["model_version"]
            elif not data.get("model_version") and data.get("configured_model_version"):
                data["model_version"] = data["configured_model_version"]
        return data

    trial_number: int = Field(default=1, ge=1, description="Trial sequence index (1-indexed).")

    execution_status: ExecutionStatus = Field(
        default=ExecutionStatus.PENDING,
        description="Status of model invocation and evaluation.",
    )
    timestamp_started: datetime = Field(
        default_factory=current_utc_timestamp,
        description="UTC time when run commenced.",
    )
    timestamp_completed: Optional[datetime] = Field(
        default=None,
        description="UTC time when run concluded.",
    )
    latency_seconds: float = Field(
        default=0.0,
        ge=0.0,
        description="Total duration of provider invocation.",
    )

    attempt_number: int = Field(
        default=1,
        ge=1,
        description="Execution attempt sequence for this scheduled run.",
    )
    prompt_hash: str = Field(..., description="SHA-256 hash of the exact model prompt.")
    full_input_hash: Optional[str] = Field(
        default=None,
        description="SHA-256 hash covering system prompt, prompt text, and generation parameters.",
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="Benchmark system instruction presented to the model.",
    )
    response_hash: Optional[str] = Field(
        default=None, description="SHA-256 hash of the raw response."
    )
    raw_response_file: Optional[str] = Field(
        default=None, description="Path to persisted raw response JSON."
    )
    evaluation_report_file: Optional[str] = Field(
        default=None,
        description="Path to persisted detailed evaluation report JSON.",
    )

    # Token usage & Cost
    prompt_tokens: Optional[int] = Field(default=None, ge=0)
    completion_tokens: Optional[int] = Field(default=None, ge=0)
    total_tokens: Optional[int] = Field(default=None, ge=0)
    estimated_cost_usd: Optional[float] = Field(default=None, ge=0.0)

    retry_count: int = Field(
        default=0, ge=0, description="Number of retries attempted before completion."
    )
    error_type: Optional[str] = Field(
        default=None, description="Normalized error category if failed."
    )
    error_message: Optional[str] = Field(default=None, description="Sanitized error description.")
    is_mock: bool = Field(
        default=False, description="Whether this run was executed against a mock provider."
    )

    # Evaluator summary metrics (None if invocation failed)
    raw_weighted_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    effective_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    safety_gate_passed: Optional[bool] = Field(default=None)
    critical_violations_count: int = Field(default=0, ge=0)
    overall_status: Optional[str] = Field(default=None)

    execution_metadata: dict[str, Any] = Field(default_factory=dict)


class ExperimentManifest(BaseModel):
    """Comprehensive manifest recording experiment state, runs index, and summary metrics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment_id: str = Field(...)
    experiment_name: str = Field(...)
    config: ExperimentConfig = Field(...)
    started_at: datetime = Field(default_factory=current_utc_timestamp)
    completed_at: Optional[datetime] = Field(default=None)
    execution_status: ExperimentLifecycleStatus = Field(
        default=ExperimentLifecycleStatus.CREATED,
        description="Authoritative lifecycle status of the experiment campaign.",
    )

    # Dataset Content Fingerprinting
    dataset_fingerprint: Optional[str] = Field(
        default=None,
        description="SHA-256 fingerprint of the complete benchmark dataset used in the campaign.",
    )
    model_visible_dataset_fingerprint: Optional[str] = Field(
        default=None,
        description="Fingerprint of model-visible tasks, scenarios, and configuration artifacts.",
    )
    evaluator_dataset_fingerprint: Optional[str] = Field(
        default=None,
        description="Fingerprint of evaluator-only ground truth artifacts.",
    )
    dataset_manifest_version: Optional[str] = Field(
        default="1.0.0",
        description="Dataset manifest version.",
    )
    fingerprint_algorithm: str = Field(
        default="sha256-canonical-json-v1",
        description="Canonical JSON SHA-256 fingerprinting algorithm.",
    )
    fingerprint_created_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp when dataset fingerprint was calculated.",
    )

    total_scheduled_runs: int = Field(default=0, ge=0)
    total_attempts_count: int = Field(
        default=0, ge=0, description="Total execution attempts executed."
    )
    completed_runs_count: int = Field(default=0, ge=0)
    failed_runs_count: int = Field(default=0, ge=0)
    skipped_resumed_runs_count: int = Field(default=0, ge=0)

    runs: list[ExperimentRunRecord] = Field(default_factory=list)
    summary_metrics: Optional[dict[str, Any]] = Field(default=None)
    reproducibility_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("execution_status", mode="before")
    @classmethod
    def validate_execution_status(cls, v: Any) -> ExperimentLifecycleStatus:
        if isinstance(v, str):
            return ExperimentLifecycleStatus(v)
        if isinstance(v, ExecutionStatus):
            return ExperimentLifecycleStatus(v.value)
        if isinstance(v, ExperimentLifecycleStatus):
            return v
        return ExperimentLifecycleStatus(str(v))


class ExperimentRecord(BaseModel):
    """Legacy manifest and run summary for backward compatibility."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment_id: str = Field(
        ...,
        description="Unique identifier for the experiment campaign (e.g. 'exp-phase1-baseline-001').",
    )
    experiment_name: str = Field(
        ...,
        min_length=1,
        description="Human-readable title of the experiment run.",
    )
    selected_models: list[str] = Field(
        ...,
        min_length=1,
        description="Identifiers of models included in the experiment run.",
    )
    selected_tasks: list[str] = Field(
        ...,
        min_length=1,
        description="Identifiers of benchmark tasks included in the experiment run.",
    )
    number_of_trials: int = Field(
        default=1,
        ge=1,
        description="Number of evaluation repetitions per model/task pair.",
    )
    configuration: dict[str, Any] = Field(
        default_factory=dict,
        description="Snapshot of execution configuration (seeds, temperature, timeouts).",
    )
    start_time: datetime = Field(
        default_factory=current_utc_timestamp,
        description="UTC timestamp when the experiment commenced.",
    )
    completion_time: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp when the experiment finished.",
    )
    execution_status: ExecutionStatus = Field(
        default=ExecutionStatus.PENDING,
        description="Lifecycle status of the experiment.",
    )
    summary_metrics: Optional[dict[str, Any]] = Field(
        default=None,
        description="Aggregated performance, pass-rates, and safety metrics across all runs.",
    )

    @field_validator("experiment_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="experiment_id")

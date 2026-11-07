"""AI model response schemas capturing raw and parsed outputs."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from phoenix_eval.schemas.common import ExecutionStatus, TokenUsage
from phoenix_eval.utils.identifiers import ensure_valid_identifier
from phoenix_eval.utils.time import current_utc_timestamp


class ModelResponse(BaseModel):
    """Execution output captured from an AI model responding to a BenchmarkTask."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    response_id: str = Field(
        ...,
        description="Unique identifier for this response record (e.g. 'resp-task-001-mock-1').",
    )
    task_id: str = Field(
        ...,
        description="ID of the benchmark task evaluated.",
    )
    model_provider: str = Field(
        ...,
        min_length=1,
        description="Provider name (e.g. 'openai', 'anthropic', 'google', 'mock').",
    )
    model_identifier: str = Field(
        ...,
        min_length=1,
        description="Model identifier (e.g. 'gpt-4o', 'claude-3-5-sonnet', 'gemini-1.5-pro', 'mock-v1').",
    )
    model_version: str = Field(
        default="unknown",
        description="Exact model release version or snapshot.",
    )
    returned_model_identifier: Optional[str] = Field(
        default=None,
        description="Exact model identifier returned by provider API (e.g. 'gpt-4o-2024-08-06').",
    )
    returned_model_version: Optional[str] = Field(
        default=None,
        description="Exact model version returned by provider API (None if omitted/absent).",
    )
    provider_request_id: Optional[str] = Field(
        default=None,
        description="Unique request ID returned by provider API/headers (e.g. 'chatcmpl-...').",
    )
    raw_response: str = Field(
        ...,
        description="Unmodified text output returned by the model.",
    )
    parsed_response: Optional[dict[str, Any]] = Field(
        default=None,
        description="Structured JSON or dictionary extracted from the raw response, if applicable.",
    )
    execution_status: ExecutionStatus = Field(
        default=ExecutionStatus.COMPLETED,
        description="Status of the model invocation.",
    )
    token_usage: Optional[TokenUsage] = Field(
        default=None,
        description="Input and output token accounting.",
    )
    execution_duration: float = Field(
        default=0.0,
        ge=0.0,
        description="Duration of model invocation in seconds.",
    )
    timestamp: datetime = Field(
        default_factory=current_utc_timestamp,
        description="UTC timestamp of the model execution.",
    )
    prompt_hash: str = Field(
        ...,
        description="SHA-256 hash of the exact prompt presented to the model.",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error details if execution_status is FAILED, TIMED_OUT, or REFUSED.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Auxiliary provider execution metadata (temperature, seed, finish_reason).",
    )

    @field_validator("response_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="response_id")

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="task_id")

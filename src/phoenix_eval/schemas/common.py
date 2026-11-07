"""Common enums, base models, and shared types for PHOENIX-EVAL schemas."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from phoenix_eval.utils.time import current_utc_timestamp


class StrEnum(str, Enum):
    """Base string enum for clean serialization and comparison."""

    def __str__(self) -> str:
        return str(self.value)


class EnvironmentType(StrEnum):
    """Runtime execution environment."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class ExecutionStatus(StrEnum):
    """Status of model or benchmark execution."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    REFUSED = "REFUSED"


class SafetyGateStatus(StrEnum):
    """Status of safety gate evaluations.

    A failed safety gate overrides standard scores because of severe security or architectural violations.
    """

    PASSED = "PASSED"
    FAILED = "FAILED"
    BYPASSED_VIOLATION = "BYPASSED_VIOLATION"
    INDETERMINATE = "INDETERMINATE"


class TokenUsage(BaseModel):
    """Token consumption and accounting metrics for a model interaction."""

    model_config = ConfigDict(frozen=True)

    prompt_tokens: int = Field(ge=0, default=0, description="Tokens in input prompt.")
    completion_tokens: int = Field(ge=0, default=0, description="Tokens generated in response.")
    total_tokens: int = Field(ge=0, default=0, description="Sum of prompt and completion tokens.")
    estimated_cost_usd: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Estimated financial cost in USD.",
    )

    @field_validator("total_tokens", mode="before")
    @classmethod
    def compute_total(cls, v: Any, info: Any) -> Any:
        # If total_tokens is not passed explicitly, sum prompt and completion
        return v


class MetadataModel(BaseModel):
    """Audit and provenance metadata attached to benchmark artifacts."""

    model_config = ConfigDict(extra="allow", frozen=True)

    created_at: datetime = Field(
        default_factory=current_utc_timestamp,
        description="Creation UTC timestamp.",
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Last update UTC timestamp.",
    )
    author: Optional[str] = Field(default=None, description="Author or generating system.")
    version: str = Field(default="1.0.0", description="Semantic version of the artifact.")
    tags: list[str] = Field(default_factory=list, description="Categorization tags.")
    custom: dict[str, Any] = Field(
        default_factory=dict,
        description="Custom audit or provenance metadata attributes.",
    )

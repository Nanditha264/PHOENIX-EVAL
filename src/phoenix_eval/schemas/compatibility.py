"""Compatibility record schema for cryptographic migration targets."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from phoenix_eval.schemas.common import StrEnum
from phoenix_eval.utils.identifiers import ensure_valid_identifier


class CompatibilityStatus(StrEnum):
    """Explicit cryptographic target compatibility status.

    CRITICAL RULE: UNKNOWN represents absence of verified support and must NEVER
    be treated or converted to SUPPORTED without explicit verified evidence.
    """

    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class CompatibilityRecord(BaseModel):
    """Assessment of whether a component supports a proposed cryptographic target algorithm or protocol."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    component_id: str = Field(
        ...,
        description="ID of the component being assessed.",
    )
    proposed_target: str = Field(
        ...,
        min_length=1,
        description="Proposed cryptographic upgrade target (e.g. 'ML-KEM-768', 'TLS_1_3', 'FIPS_204_ML_DSA').",
    )
    status: CompatibilityStatus = Field(
        ...,
        description="Compatibility status: SUPPORTED, UNSUPPORTED, or UNKNOWN.",
    )
    evidence_references: list[str] = Field(
        default_factory=list,
        description="EvidenceRecord IDs backing this compatibility assessment.",
    )
    reason: str = Field(
        ...,
        min_length=1,
        description="Technical justification or explanation for the assessed status.",
    )
    assessment_source: str = Field(
        ...,
        min_length=1,
        description="Origin of assessment (e.g. 'vendor-spec-v3.1', 'cipher-test-harness', 'unverified-claim').",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional technical notes (e.g. firmware version limits).",
    )

    @field_validator("component_id")
    @classmethod
    def validate_comp_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="component_id")

    @model_validator(mode="after")
    def validate_unknown_safety(self) -> "CompatibilityRecord":
        """Enforce strict semantic rules around compatibility statuses."""
        if self.status == CompatibilityStatus.UNKNOWN:
            # When status is UNKNOWN, evidence cannot claim definitive support
            if any("verified_support" in ref.lower() for ref in self.evidence_references):
                raise ValueError(
                    f"Contradiction: Status is UNKNOWN but evidence references claim verified support for {self.component_id}."
                )
        elif self.status == CompatibilityStatus.UNSUPPORTED and not self.reason.strip():
            raise ValueError(
                f"UNSUPPORTED compatibility for {self.component_id} must have a non-empty explanation reason."
            )
        return self

    @property
    def is_safe_to_migrate(self) -> bool:
        """Helper property. Returns True ONLY if compatibility is explicitly SUPPORTED."""
        return self.status == CompatibilityStatus.SUPPORTED

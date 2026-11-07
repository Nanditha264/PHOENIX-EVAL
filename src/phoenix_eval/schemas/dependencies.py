"""Dependency relationship schema representing cryptographic links between components."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from phoenix_eval.schemas.common import StrEnum
from phoenix_eval.utils.identifiers import ensure_valid_identifier


class RelationshipType(StrEnum):
    """Cryptographic and architectural dependency relationship types."""

    CALLS = "CALLS"
    ENCRYPTS_WITH = "ENCRYPTS_WITH"
    STORES_DATA_IN = "STORES_DATA_IN"
    SHARES_KEY_WITH = "SHARES_KEY_WITH"
    VERIFIES_SIGNATURE_FROM = "VERIFIES_SIGNATURE_FROM"
    CERTIFICATE_ISSUED_BY = "CERTIFICATE_ISSUED_BY"
    USES_LIBRARY = "USES_LIBRARY"
    WRAPS_SERVICE = "WRAPS_SERVICE"
    HARDWARE_DEPENDENCY = "HARDWARE_DEPENDENCY"
    EXCHANGES_KEYS_WITH = "EXCHANGES_KEYS_WITH"


class DependencyCriticality(StrEnum):
    """Operational criticality of the dependency relationship."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DependencyRelationship(BaseModel):
    """A directed dependency relationship between two cryptographic components."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_id: str = Field(
        ...,
        description="Unique identifier for the dependency relationship (e.g. 'edge-auth-to-hsm-01').",
    )
    source_component_id: str = Field(
        ...,
        description="Component ID of the dependent component (caller / consumer).",
    )
    target_component_id: str = Field(
        ...,
        description="Component ID of the dependency component (callee / provider).",
    )
    relationship_type: RelationshipType = Field(
        ...,
        description="Specific cryptographic or architectural interaction type.",
    )
    evidence_references: list[str] = Field(
        default_factory=list,
        description="List of EvidenceRecord IDs validating this relationship.",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence level in the existence of this dependency (0.0 to 1.0).",
    )
    description: str = Field(
        default="",
        description="Technical context of the interaction.",
    )
    is_bidirectional: bool = Field(
        default=False,
        description="Whether interaction is strictly mutual/bidirectional.",
    )
    criticality: DependencyCriticality = Field(
        default=DependencyCriticality.HIGH,
        description="Impact if this dependency fails during migration.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Auxiliary relationship attributes.",
    )

    @field_validator("edge_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="edge_id")

    @field_validator("source_component_id")
    @classmethod
    def validate_source(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="source_component_id")

    @field_validator("target_component_id")
    @classmethod
    def validate_target(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="target_component_id")

    @model_validator(mode="after")
    def check_non_self_referential(self) -> "DependencyRelationship":
        if self.source_component_id == self.target_component_id:
            raise ValueError(
                f"Self-referential dependency not allowed: source '{self.source_component_id}' "
                f"equals target '{self.target_component_id}'."
            )
        return self

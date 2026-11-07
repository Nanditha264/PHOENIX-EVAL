"""Evidence record schema representing cryptographic discovery and audit findings."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from phoenix_eval.schemas.common import StrEnum
from phoenix_eval.utils.identifiers import ensure_valid_identifier
from phoenix_eval.utils.time import current_utc_timestamp


class EvidenceType(StrEnum):
    """Categorization of cryptographic evidence discovery methods."""

    STATIC_CODE_ANALYSIS = "STATIC_CODE_ANALYSIS"
    NETWORK_TRAFFIC_CAPTURE = "NETWORK_TRAFFIC_CAPTURE"
    CONFIGURATION_AUDIT = "CONFIGURATION_AUDIT"
    SBOM_INSPECTION = "SBOM_INSPECTION"
    CIPHER_SCAN = "CIPHER_SCAN"
    CERTIFICATE_INSPECTION = "CERTIFICATE_INSPECTION"
    HARDWARE_ATTESTATION = "HARDWARE_ATTESTATION"
    RUNTIME_TELEMETRY = "RUNTIME_TELEMETRY"
    MANUAL_ATTESTATION = "MANUAL_ATTESTATION"
    INTEGRATION_TEST_REPORT = "INTEGRATION_TEST_REPORT"
    VENDOR_CAPABILITY_STATEMENT = "VENDOR_CAPABILITY_STATEMENT"
    ARCHITECTURE_DOCUMENTATION = "ARCHITECTURE_DOCUMENTATION"
    DEPLOYMENT_MANIFEST = "DEPLOYMENT_MANIFEST"
    LEGACY_INVENTORY = "LEGACY_INVENTORY"


class VerificationStatus(StrEnum):
    """Integrity and verification status of a piece of discovery evidence."""

    VERIFIED = "VERIFIED"
    CONTRADICTED = "CONTRADICTED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INFERRED = "INFERRED"
    UNVERIFIED = "UNVERIFIED"
    CONFLICTING = "CONFLICTING"
    DISPROVEN = "DISPROVEN"
    ASSUMED = "ASSUMED"


class EvidenceCategory(StrEnum):
    """Epistemic classification distinguishing direct observations from assumptions."""

    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    ASSUMPTION = "ASSUMPTION"


class EvidenceRecord(BaseModel):
    """A cryptographic discovery evidence record observed or inferred from enterprise systems."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str = Field(
        ...,
        description="Unique identifier for the evidence record (e.g. 'evid-tls-scan-001').",
    )
    evidence_type: EvidenceType = Field(
        ...,
        description="Method through which this evidence was discovered.",
    )
    source: str = Field(
        ...,
        description="Originating tool, scanner, file, or human source of this evidence.",
    )
    description: str = Field(
        ...,
        description="Human-readable explanation of what was observed.",
    )
    observed_value: Any = Field(
        ...,
        description="Raw or structured value discovered (e.g. cipher suite string, certificate hash).",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score in the accuracy of this evidence (0.0 to 1.0).",
    )
    timestamp: datetime = Field(
        default_factory=current_utc_timestamp,
        description="UTC timestamp when evidence was observed or recorded.",
    )
    provenance: str = Field(
        ...,
        description="Audit trail, scan session ID, or commit hash where evidence was captured.",
    )
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.VERIFIED,
        description="Verification state of this evidence.",
    )
    evidence_category: EvidenceCategory = Field(
        default=EvidenceCategory.OBSERVED,
        description="Epistemic status: OBSERVED (direct fact), INFERRED (deduced), or ASSUMPTION (unverified premise).",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional auxiliary discovery metadata.",
    )
    target_component_id: Optional[str] = Field(
        default=None,
        description="Optional component ID targeted or described by this evidence.",
    )
    is_stale: bool = Field(
        default=False,
        description="Whether this evidence is considered stale or outdated.",
    )
    freshness_days: Optional[int] = Field(
        default=None,
        description="Age of the evidence observation in days.",
    )

    @field_validator("evidence_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="evidence_id")

    @property
    def is_observed_fact(self) -> bool:
        """Return True if evidence is a verified direct observation, not an assumption or inference."""
        return (
            self.evidence_category == EvidenceCategory.OBSERVED
            and self.verification_status == VerificationStatus.VERIFIED
        )
